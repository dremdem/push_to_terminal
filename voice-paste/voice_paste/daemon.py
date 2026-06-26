"""Push-to-talk daemon — issue #2.

Protocol:
  voice-paste start  → spawn _daemon subprocess (start_new_session=True)
  voice-paste stop   → connect to SOCK_PATH, send b"STOP\\n", read b"OK\\n"

State files live in ~/.local/state/voice-paste/:
  daemon.pid  — PID of the running daemon process
  daemon.sock — Unix domain socket for the STOP command
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

SOCK_PATH = Path.home() / ".local" / "state" / "voice-paste" / "daemon.sock"
PID_PATH = Path.home() / ".local" / "state" / "voice-paste" / "daemon.pid"


def is_running() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, 0)  # signal 0 = check existence without sending a real signal
        return True
    except (ProcessLookupError, PermissionError, ValueError, OSError):
        PID_PATH.unlink(missing_ok=True)
        SOCK_PATH.unlink(missing_ok=True)
        return False


def send_stop() -> None:
    if not is_running():
        raise RuntimeError("No recording in progress")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(str(SOCK_PATH))
        s.sendall(b"STOP\n")
        s.recv(1024)


def spawn(language: str = "auto", target: str = "clipboard") -> None:
    SOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [sys.argv[0], "_daemon", "--language", language, "--target", target],
        start_new_session=True,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run(config) -> None:
    """Daemon main loop — called by the hidden _daemon CLI command."""
    from voice_paste import clipboard, notify, postprocess, recorder
    from voice_paste import transcriber as trans_mod

    SOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()))

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = Path(f.name)

    notify.notify("Recording...", "voice-paste")
    stream = recorder.RecordingStream(wav_path)
    stream.start()

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(SOCK_PATH))
            server.listen(1)
            conn, _ = server.accept()
            with conn:
                conn.recv(1024)
                conn.sendall(b"OK\n")
    finally:
        stream.stop()

    notify.notify("Transcribing...", "voice-paste")
    t = trans_mod.create_transcriber(
        config.transcription.backend,
        config.transcription.model,
        config.transcription.device,
        config.transcription.compute_type,
        config.transcription.vad_method,
    )
    lang = config.language if config.language != "auto" else None
    text = t.transcribe(wav_path, lang)
    text = postprocess.process(text, terminal_mode=(config.target == "terminal"))

    clipboard.copy(text)
    preview = text[:60] + ("…" if len(text) > 60 else "")
    notify.notify(f'Copied: "{preview}"', "voice-paste")

    wav_path.unlink(missing_ok=True)
    SOCK_PATH.unlink(missing_ok=True)
    PID_PATH.unlink(missing_ok=True)
