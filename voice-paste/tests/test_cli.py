"""CLI integration tests."""
import pytest
from typer.testing import CliRunner

from voice_paste.cli import app

runner = CliRunner()


# ── config-path ──────────────────────────────────────────────────────────────

def test_config_path_prints_path():
    result = runner.invoke(app, ["config-path"])
    assert result.exit_code == 0
    assert "voice-paste" in result.output
    assert "config.toml" in result.output


# ── start ────────────────────────────────────────────────────────────────────

def test_start_errors_when_already_recording(mocker):
    mocker.patch("voice_paste.daemon.is_running", return_value=True)
    result = runner.invoke(app, ["start"])
    assert result.exit_code != 0
    assert "already" in result.output.lower()


def test_start_spawns_daemon_and_confirms(mocker):
    mocker.patch("voice_paste.daemon.is_running", side_effect=[False, False, True])
    mock_spawn = mocker.patch("voice_paste.daemon.spawn")
    mocker.patch("time.sleep")
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    mock_spawn.assert_called_once()


def test_start_passes_language_and_target_to_spawn(mocker):
    mocker.patch("voice_paste.daemon.is_running", side_effect=[False, True])
    mock_spawn = mocker.patch("voice_paste.daemon.spawn")
    mocker.patch("time.sleep")
    runner.invoke(app, ["start", "--language", "ru", "--target", "clipboard"])
    mock_spawn.assert_called_once_with(language="ru", target="clipboard")


def test_start_errors_if_daemon_never_starts(mocker):
    mocker.patch("voice_paste.daemon.is_running", return_value=False)
    mocker.patch("voice_paste.daemon.spawn")
    mocker.patch("time.sleep")
    result = runner.invoke(app, ["start"])
    assert result.exit_code != 0


# ── stop ─────────────────────────────────────────────────────────────────────

def test_stop_errors_when_not_recording(mocker):
    mocker.patch("voice_paste.daemon.is_running", return_value=False)
    result = runner.invoke(app, ["stop"])
    assert result.exit_code != 0
    assert "not" in result.output.lower() or "no recording" in result.output.lower()


def test_stop_calls_send_stop(mocker):
    mocker.patch("voice_paste.daemon.is_running", return_value=True)
    mock_send = mocker.patch("voice_paste.daemon.send_stop")
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    mock_send.assert_called_once()


# ── record (fixed-duration) ───────────────────────────────────────────────────

def test_record_runs_full_pipeline(mocker, tmp_path):
    mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    mocker.patch("voice_paste.recorder.find_recorder", return_value="pw-record")
    mocker.patch("voice_paste.recorder.record_fixed")
    mock_transcribe = mocker.patch("voice_paste.transcriber.OpenAITranscriber.transcribe", return_value="hello")
    mocker.patch("voice_paste.clipboard.copy")
    mocker.patch("voice_paste.notify.notify")
    result = runner.invoke(app, ["record", "--duration", "5"])
    assert result.exit_code == 0
    mock_transcribe.assert_called_once()


def test_record_never_executes_commands(mocker):
    """Safety: record must not press Enter or run shell commands."""
    mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    mocker.patch("voice_paste.recorder.find_recorder", return_value="pw-record")
    mocker.patch("voice_paste.recorder.record_fixed")
    mocker.patch("voice_paste.transcriber.OpenAITranscriber.transcribe", return_value="rm -rf /tmp")
    mock_copy = mocker.patch("voice_paste.clipboard.copy")
    mocker.patch("voice_paste.notify.notify")
    runner.invoke(app, ["record", "--duration", "5"])
    text = mock_copy.call_args[0][0]
    assert not text.endswith("\n")
