"""Tests for desktop entry installation (v0.6)."""
from pathlib import Path
from unittest.mock import patch

import pytest

from voice_paste.desktop import install, uninstall, DESKTOP_FILE, AUTOSTART_FILE


# ── install ───────────────────────────────────────────────────────────────────

def test_install_creates_desktop_file(tmp_path, mocker):
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", tmp_path / "voice-paste-tray.desktop")
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", tmp_path / "autostart.desktop")
    install("/usr/bin/voice-paste-tray", autostart=False)
    assert (tmp_path / "voice-paste-tray.desktop").exists()


def test_install_desktop_contains_exec_path(tmp_path, mocker):
    dest = tmp_path / "voice-paste-tray.desktop"
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", dest)
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", tmp_path / "autostart.desktop")
    install("/home/user/.venv/bin/voice-paste-tray", autostart=False)
    content = dest.read_text()
    assert "Exec=/home/user/.venv/bin/voice-paste-tray" in content


def test_install_desktop_has_required_fields(tmp_path, mocker):
    dest = tmp_path / "voice-paste-tray.desktop"
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", dest)
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", tmp_path / "autostart.desktop")
    install("/usr/bin/voice-paste-tray", autostart=False)
    content = dest.read_text()
    assert "[Desktop Entry]" in content
    assert "Name=" in content
    assert "Type=Application" in content
    assert "Categories=" in content


def test_install_creates_autostart_when_requested(tmp_path, mocker):
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", tmp_path / "app.desktop")
    autostart = tmp_path / "autostart.desktop"
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", autostart)
    install("/usr/bin/voice-paste-tray", autostart=True)
    assert autostart.exists()


def test_install_no_autostart_by_default(tmp_path, mocker):
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", tmp_path / "app.desktop")
    autostart = tmp_path / "autostart.desktop"
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", autostart)
    install("/usr/bin/voice-paste-tray", autostart=False)
    assert not autostart.exists()


def test_install_autostart_contains_exec_path(tmp_path, mocker):
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", tmp_path / "app.desktop")
    autostart = tmp_path / "autostart.desktop"
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", autostart)
    install("/home/user/.venv/bin/voice-paste-tray", autostart=True)
    content = autostart.read_text()
    assert "Exec=/home/user/.venv/bin/voice-paste-tray" in content


def test_install_creates_parent_dirs(tmp_path, mocker):
    dest = tmp_path / "applications" / "voice-paste-tray.desktop"
    autostart = tmp_path / "autostart" / "voice-paste-tray.desktop"
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", dest)
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", autostart)
    install("/usr/bin/voice-paste-tray", autostart=True)
    assert dest.exists()
    assert autostart.exists()


# ── uninstall ─────────────────────────────────────────────────────────────────

def test_uninstall_removes_desktop_file(tmp_path, mocker):
    dest = tmp_path / "voice-paste-tray.desktop"
    dest.write_text("[Desktop Entry]\n")
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", dest)
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", tmp_path / "autostart.desktop")
    uninstall()
    assert not dest.exists()


def test_uninstall_removes_autostart_file(tmp_path, mocker):
    desktop = tmp_path / "app.desktop"
    desktop.write_text("[Desktop Entry]\n")
    autostart = tmp_path / "autostart.desktop"
    autostart.write_text("[Desktop Entry]\n")
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", desktop)
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", autostart)
    uninstall()
    assert not autostart.exists()


def test_uninstall_noop_when_files_missing(tmp_path, mocker):
    mocker.patch("voice_paste.desktop.DESKTOP_FILE", tmp_path / "missing.desktop")
    mocker.patch("voice_paste.desktop.AUTOSTART_FILE", tmp_path / "missing2.desktop")
    uninstall()  # must not raise


# ── constants ─────────────────────────────────────────────────────────────────

def test_desktop_file_path_is_in_home():
    assert str(Path.home()) in str(DESKTOP_FILE)


def test_autostart_file_path_is_in_home():
    assert str(Path.home()) in str(AUTOSTART_FILE)
