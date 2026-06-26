"""Tests for GNOME gsettings hotkey binding (v0.5)."""
from unittest.mock import call, patch

import pytest

from voice_paste.hotkey import (
    GSETTINGS_PATH,
    binding_to_gnome,
    current_binding,
    register,
    unregister,
)


# ── binding format conversion ─────────────────────────────────────────────────

def test_binding_to_gnome_single_key():
    assert binding_to_gnome("space") == "space"


def test_binding_to_gnome_ctrl_alt():
    assert binding_to_gnome("ctrl+alt+space") == "<Ctrl><Alt>space"


def test_binding_to_gnome_ctrl_shift():
    assert binding_to_gnome("ctrl+shift+v") == "<Ctrl><Shift>v"


def test_binding_to_gnome_super():
    assert binding_to_gnome("super+r") == "<Super>r"


def test_binding_to_gnome_case_insensitive():
    assert binding_to_gnome("CTRL+ALT+SPACE") == "<Ctrl><Alt>space"


# ── register ─────────────────────────────────────────────────────────────────

def test_register_calls_gsettings(mocker):
    mock_run = mocker.patch("voice_paste.hotkey.subprocess.run")
    register("ctrl+alt+space", "voice-paste start")
    assert mock_run.called


def test_register_sets_name_binding_command(mocker):
    mock_run = mocker.patch("voice_paste.hotkey.subprocess.run")
    register("ctrl+alt+space", "voice-paste start")
    calls_str = " ".join(str(c) for c in mock_run.call_args_list)
    assert "voice-paste" in calls_str
    assert "<Ctrl><Alt>space" in calls_str


def test_register_adds_path_to_custom_keybindings_list(mocker):
    mock_run = mocker.patch("voice_paste.hotkey.subprocess.run")
    mocker.patch("voice_paste.hotkey.current_binding", return_value=None)
    register("ctrl+alt+space", "voice-paste start")
    # One of the gsettings calls must update the top-level list
    calls_str = " ".join(str(c) for c in mock_run.call_args_list)
    assert "custom-keybindings" in calls_str


# ── unregister ────────────────────────────────────────────────────────────────

def test_unregister_calls_gsettings(mocker):
    mock_run = mocker.patch("voice_paste.hotkey.subprocess.run")
    mocker.patch("voice_paste.hotkey._get_keybinding_paths", return_value=[GSETTINGS_PATH])
    unregister()
    assert mock_run.called


def test_unregister_noop_when_not_registered(mocker):
    mock_run = mocker.patch("voice_paste.hotkey.subprocess.run")
    mocker.patch("voice_paste.hotkey._get_keybinding_paths", return_value=[])
    unregister()
    mock_run.assert_not_called()


# ── current_binding ───────────────────────────────────────────────────────────

def test_current_binding_returns_none_when_not_registered(mocker):
    mocker.patch("voice_paste.hotkey._get_keybinding_paths", return_value=[])
    assert current_binding() is None


def test_current_binding_returns_gnome_string(mocker):
    mocker.patch(
        "voice_paste.hotkey._get_keybinding_paths", return_value=[GSETTINGS_PATH]
    )
    mocker.patch(
        "voice_paste.hotkey._gsettings_get",
        return_value="<Ctrl><Alt>space",
    )
    assert current_binding() == "<Ctrl><Alt>space"


# ── gsettings_path constant ───────────────────────────────────────────────────

def test_gsettings_path_contains_voice_paste():
    assert "voice-paste" in GSETTINGS_PATH
