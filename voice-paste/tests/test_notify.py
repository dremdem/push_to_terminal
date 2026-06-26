from voice_paste.notify import notify


def test_uses_notify_send_when_available(mocker):
    mocker.patch("shutil.which", return_value="/usr/bin/notify-send")
    mock_run = mocker.patch("subprocess.run")
    notify("Recording...")
    assert mock_run.called
    cmd = mock_run.call_args[0][0]
    assert "notify-send" in cmd[0]


def test_notify_send_receives_title_and_body(mocker):
    mocker.patch("shutil.which", return_value="/usr/bin/notify-send")
    mock_run = mocker.patch("subprocess.run")
    notify("Transcribing...", title="voice-paste")
    cmd = mock_run.call_args[0][0]
    assert "voice-paste" in cmd
    assert "Transcribing..." in cmd


def test_falls_back_to_stdout_when_missing(mocker, capsys):
    mocker.patch("shutil.which", return_value=None)
    notify("Copied to clipboard")
    captured = capsys.readouterr()
    assert "Copied to clipboard" in captured.out
