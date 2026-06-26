import os
import pytest
from unittest.mock import patch, MagicMock
from voice_paste.paste import paste, _tool_for_session, PasteError


# ── _tool_for_session ─────────────────────────────────────────────────────────

def test_tool_for_session_wayland_returns_ydotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value="/usr/bin/ydotool")
    assert _tool_for_session() == "ydotool"


def test_tool_for_session_x11_returns_xdotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda t: "/usr/bin/xdotool" if t == "xdotool" else None)
    assert _tool_for_session() == "xdotool"


def test_tool_for_session_wayland_missing_raises(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(PasteError, match="ydotool"):
        _tool_for_session()


def test_tool_for_session_x11_missing_raises(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(PasteError, match="xdotool"):
        _tool_for_session()


# ── paste() ───────────────────────────────────────────────────────────────────

def test_paste_clipboard_target_is_noop(mocker):
    run = mocker.patch("subprocess.run")
    paste("clipboard")
    run.assert_not_called()


def test_paste_terminal_sends_ctrl_shift_v_xdotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda t: "/usr/bin/xdotool" if t == "xdotool" else None)
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    paste("terminal")
    cmd = run.call_args[0][0]
    assert "xdotool" in cmd[0]
    assert "ctrl+shift+v" in " ".join(cmd).lower()


def test_paste_active_sends_ctrl_v_xdotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda t: "/usr/bin/xdotool" if t == "xdotool" else None)
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    paste("active")
    cmd = run.call_args[0][0]
    assert "xdotool" in cmd[0]
    assert "ctrl+v" in " ".join(cmd).lower()


def test_paste_terminal_sends_ctrl_shift_v_ydotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value="/usr/bin/ydotool")
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    paste("terminal")
    cmd = run.call_args[0][0]
    assert "ydotool" in cmd[0]
    assert "ctrl+shift+v" in " ".join(cmd).lower()


def test_paste_active_sends_ctrl_v_ydotool(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value="/usr/bin/ydotool")
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    paste("active")
    cmd = run.call_args[0][0]
    assert "ydotool" in cmd[0]
    assert "ctrl+v" in " ".join(cmd).lower()


def test_paste_never_sends_enter(mocker):
    """No paste invocation should ever inject Enter/Return."""
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda t: "/usr/bin/xdotool" if t == "xdotool" else None)
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0))
    for target in ("terminal", "active"):
        paste(target)
    for call in run.call_args_list:
        cmd_str = " ".join(str(a) for a in call[0][0]).lower()
        assert "return" not in cmd_str
        assert "enter" not in cmd_str


def test_paste_missing_tool_raises_paste_error(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", return_value=None)
    with pytest.raises(PasteError):
        paste("active")


def test_paste_tool_nonzero_exit_raises_paste_error(mocker):
    mocker.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda t: "/usr/bin/xdotool" if t == "xdotool" else None)
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stderr=b"err"))
    with pytest.raises(PasteError):
        paste("active")
