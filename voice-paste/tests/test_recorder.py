import pytest
from pathlib import Path
from voice_paste.recorder import find_recorder, record_fixed, RecordingStream


def test_find_recorder_prefers_pw_record(mocker):
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "pw-record" else None)
    assert find_recorder() == "pw-record"


def test_find_recorder_falls_back_to_parecord(mocker):
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "parecord" else None)
    assert find_recorder() == "parecord"


def test_find_recorder_raises_when_none_available(mocker):
    mocker.patch("shutil.which", return_value=None)
    mocker.patch.dict("sys.modules", {"sounddevice": None})
    with pytest.raises(RuntimeError, match="No audio recorder"):
        find_recorder()


def test_record_fixed_starts_and_terminates_process(mocker, tmp_path):
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "pw-record" else None)
    mocker.patch("time.sleep")
    mock_proc = mocker.MagicMock()
    mock_popen = mocker.patch("subprocess.Popen", return_value=mock_proc)
    wav = tmp_path / "test.wav"
    record_fixed(wav, duration=5)
    mock_popen.assert_called_once()
    cmd = mock_popen.call_args[0][0]
    assert "pw-record" in cmd[0]
    assert str(wav) in cmd
    mock_proc.terminate.assert_called_once()


def test_record_fixed_kills_if_terminate_hangs(mocker, tmp_path):
    import subprocess
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "pw-record" else None)
    mocker.patch("time.sleep")
    mock_proc = mocker.MagicMock()
    mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="pw-record", timeout=5)
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    wav = tmp_path / "test.wav"
    record_fixed(wav, duration=5)
    mock_proc.kill.assert_called_once()


def test_recording_stream_start_and_stop(mocker, tmp_path):
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "pw-record" else None)
    mock_proc = mocker.MagicMock()
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    wav = tmp_path / "stream.wav"
    stream = RecordingStream(wav)
    stream.start()
    mock_proc  # Popen was called
    stream.stop()
    mock_proc.terminate.assert_called_once()


def test_recording_stream_stop_is_idempotent(mocker, tmp_path):
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "pw-record" else None)
    mock_proc = mocker.MagicMock()
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    wav = tmp_path / "stream.wav"
    stream = RecordingStream(wav)
    stream.start()
    stream.stop()
    stream.stop()  # second stop should be a no-op
    assert mock_proc.terminate.call_count == 1
