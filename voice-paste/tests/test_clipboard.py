import pytest
from voice_paste.clipboard import copy


def test_wayland_uses_wl_copy(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "wl-copy" else None)
    mock_run = mocker.patch("subprocess.run")
    copy("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0].endswith("wl-copy")


def test_x11_uses_xclip(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "xclip" else None)
    mock_run = mocker.patch("subprocess.run")
    copy("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0].endswith("xclip")


def test_x11_falls_back_to_xsel(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda cmd: f"/usr/bin/{cmd}" if cmd == "xsel" else None)
    mock_run = mocker.patch("subprocess.run")
    copy("hello")
    cmd = mock_run.call_args[0][0]
    assert cmd[0].endswith("xsel")


def test_missing_wayland_tool_raises_with_instructions(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(RuntimeError, match="wl-copy"):
        copy("hello")


def test_missing_x11_tools_raises_with_instructions(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(RuntimeError, match="xclip"):
        copy("hello")


def test_text_is_passed_as_stdin(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value="/usr/bin/wl-copy")
    mock_run = mocker.patch("subprocess.run")
    copy("my text")
    assert mock_run.call_args.kwargs["input"] == b"my text"
