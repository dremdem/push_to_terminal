"""Tests for push-to-talk daemon (issue #2)."""
import os
import socket
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voice_paste import daemon
from voice_paste.config import Config


# ── is_running() ─────────────────────────────────────────────────────────────

def test_is_running_false_when_no_pid_file(tmp_path):
    with patch.object(daemon, "PID_PATH", tmp_path / "daemon.pid"):
        assert daemon.is_running() is False


def test_is_running_false_and_cleans_stale_pid(tmp_path):
    pid_path = tmp_path / "daemon.pid"
    sock_path = tmp_path / "daemon.sock"
    pid_path.write_text("999999999")  # non-existent PID
    sock_path.touch()
    with (
        patch.object(daemon, "PID_PATH", pid_path),
        patch.object(daemon, "SOCK_PATH", sock_path),
    ):
        assert daemon.is_running() is False
        assert not pid_path.exists()
        assert not sock_path.exists()


def test_is_running_true_when_own_pid_present(tmp_path):
    pid_path = tmp_path / "daemon.pid"
    pid_path.write_text(str(os.getpid()))  # current process is "the daemon"
    with patch.object(daemon, "PID_PATH", pid_path):
        assert daemon.is_running() is True


# ── send_stop() ───────────────────────────────────────────────────────────────

def test_send_stop_raises_when_not_running(tmp_path):
    with patch.object(daemon, "PID_PATH", tmp_path / "daemon.pid"):
        with pytest.raises(RuntimeError, match="No recording"):
            daemon.send_stop()


def test_send_stop_communicates_over_unix_socket(tmp_path):
    sock_path = tmp_path / "test.sock"
    pid_path = tmp_path / "daemon.pid"
    pid_path.write_text(str(os.getpid()))

    received = []

    def serve():
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock_path))
        server.listen(1)
        conn, _ = server.accept()
        data = conn.recv(1024)
        received.append(data)
        conn.sendall(b"OK\n")
        conn.close()
        server.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(0.05)

    with (
        patch.object(daemon, "SOCK_PATH", sock_path),
        patch.object(daemon, "PID_PATH", pid_path),
    ):
        daemon.send_stop()

    t.join(timeout=2)
    assert received and b"STOP" in received[0]


# ── spawn() ───────────────────────────────────────────────────────────────────

def test_spawn_launches_daemon_subprocess(mocker, tmp_path):
    mock_popen = mocker.patch("subprocess.Popen")
    mocker.patch.object(daemon, "SOCK_PATH", tmp_path / "daemon.sock")
    daemon.spawn(language="ru", target="clipboard")
    mock_popen.assert_called_once()
    args = mock_popen.call_args[0][0]
    assert "_daemon" in args
    assert "ru" in args


# ── run() — full push-to-talk pipeline ───────────────────────────────────────

def test_daemon_run_records_transcribes_copies(mocker, tmp_path):
    sock_path = tmp_path / "daemon.sock"
    pid_path = tmp_path / "daemon.pid"

    mocker.patch.object(daemon, "SOCK_PATH", sock_path)
    mocker.patch.object(daemon, "PID_PATH", pid_path)

    mock_stream = mocker.MagicMock()
    mocker.patch("voice_paste.recorder.RecordingStream", return_value=mock_stream)

    mock_transcriber = mocker.MagicMock()
    mock_transcriber.transcribe.return_value = "hello world"
    mocker.patch("voice_paste.transcriber.create_transcriber", return_value=mock_transcriber)

    mock_copy = mocker.patch("voice_paste.clipboard.copy")
    mocker.patch("voice_paste.notify.notify")

    errors: list[Exception] = []

    def run_daemon():
        try:
            daemon.run(Config())
        except Exception as exc:
            errors.append(exc)

    def send_stop_client():
        for _ in range(100):
            if sock_path.exists():
                break
            time.sleep(0.02)
        time.sleep(0.02)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(sock_path))
            s.sendall(b"STOP\n")
            s.recv(1024)

    t_daemon = threading.Thread(target=run_daemon)
    t_stop = threading.Thread(target=send_stop_client)

    t_daemon.start()
    time.sleep(0.05)
    t_stop.start()

    t_daemon.join(timeout=5)
    t_stop.join(timeout=5)

    assert not errors, f"Daemon raised: {errors}"
    mock_stream.start.assert_called_once()
    mock_stream.stop.assert_called_once()
    mock_transcriber.transcribe.assert_called_once()
    mock_copy.assert_called_once_with("hello world")


def test_daemon_run_cleans_up_files_after_stop(mocker, tmp_path):
    sock_path = tmp_path / "daemon.sock"
    pid_path = tmp_path / "daemon.pid"

    mocker.patch.object(daemon, "SOCK_PATH", sock_path)
    mocker.patch.object(daemon, "PID_PATH", pid_path)
    mocker.patch("voice_paste.recorder.RecordingStream")
    mocker.patch("voice_paste.transcriber.create_transcriber").return_value.transcribe.return_value = "x"
    mocker.patch("voice_paste.clipboard.copy")
    mocker.patch("voice_paste.notify.notify")

    def send_stop_client():
        for _ in range(100):
            if sock_path.exists():
                break
            time.sleep(0.02)
        time.sleep(0.02)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(sock_path))
            s.sendall(b"STOP\n")
            s.recv(1024)

    t_daemon = threading.Thread(target=lambda: daemon.run(Config()))
    t_stop = threading.Thread(target=send_stop_client)

    t_daemon.start()
    time.sleep(0.05)
    t_stop.start()

    t_daemon.join(timeout=5)
    t_stop.join(timeout=5)

    assert not sock_path.exists()
    assert not pid_path.exists()


def test_daemon_never_sends_enter(mocker, tmp_path):
    """Safety: daemon must not inject Enter/newline via paste."""
    sock_path = tmp_path / "daemon.sock"
    pid_path = tmp_path / "daemon.pid"

    mocker.patch.object(daemon, "SOCK_PATH", sock_path)
    mocker.patch.object(daemon, "PID_PATH", pid_path)
    mocker.patch("voice_paste.recorder.RecordingStream")
    mocker.patch("voice_paste.transcriber.create_transcriber").return_value.transcribe.return_value = "rm -rf /tmp/test"
    mock_copy = mocker.patch("voice_paste.clipboard.copy")
    mocker.patch("voice_paste.notify.notify")
    mock_paste = mocker.patch("voice_paste.paste.paste")

    def send_stop_client():
        for _ in range(100):
            if sock_path.exists():
                break
            time.sleep(0.02)
        time.sleep(0.02)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(sock_path))
            s.sendall(b"STOP\n")
            s.recv(1024)

    t_daemon = threading.Thread(target=lambda: daemon.run(Config()))
    t_stop = threading.Thread(target=send_stop_client)

    t_daemon.start()
    time.sleep(0.05)
    t_stop.start()
    t_daemon.join(timeout=5)
    t_stop.join(timeout=5)

    # Text must reach clipboard exactly as-is, no appended newline
    text_copied = mock_copy.call_args[0][0]
    assert not text_copied.endswith("\n")
    # paste() must NOT be called with auto-paste disabled (default)
    mock_paste.assert_not_called()
