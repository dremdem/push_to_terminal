"""Tests for the system tray module (v0.4)."""
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from voice_paste.tray import TrayApp, LANGUAGES, BACKENDS


# ── construction ──────────────────────────────────────────────────────────────

def test_tray_app_initialises_idle(tmp_path):
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    assert app.state == "idle"
    assert app.last_text == ""
    assert app.last_wav is None


# ── icon generation ───────────────────────────────────────────────────────────

def test_make_icon_returns_image_for_each_state():
    pytest.importorskip("PIL")
    from PIL import Image
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    for state in ("idle", "recording", "transcribing"):
        img = app._make_icon(state)
        assert isinstance(img, Image.Image)
        assert img.size == (64, 64)


def test_make_icon_different_colours_per_state():
    pytest.importorskip("PIL")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    idle = app._make_icon("idle")
    recording = app._make_icon("recording")
    transcribing = app._make_icon("transcribing")
    # Each state must produce a visually distinct icon
    assert idle.tobytes() != recording.tobytes()
    assert idle.tobytes() != transcribing.tobytes()
    assert recording.tobytes() != transcribing.tobytes()


# ── config persistence ────────────────────────────────────────────────────────

def test_save_cfg_writes_toml(tmp_path, mocker):
    cfg_path = tmp_path / "config.toml"
    mocker.patch("voice_paste.tray.default_config_path", return_value=cfg_path)
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app._cfg.language = "ru"
    app._cfg.transcription.backend = "docker"
    app._save_cfg()
    content = cfg_path.read_text()
    assert "language" in content
    assert "ru" in content
    assert "backend" in content
    assert "docker" in content


def test_save_cfg_does_not_include_enter_or_commands(tmp_path, mocker):
    cfg_path = tmp_path / "config.toml"
    mocker.patch("voice_paste.tray.default_config_path", return_value=cfg_path)
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app._save_cfg()
    content = cfg_path.read_text()
    assert "Enter" not in content
    assert "subprocess" not in content


# ── language / backend selection ─────────────────────────────────────────────

def test_set_language_updates_cfg(mocker, tmp_path):
    mocker.patch("voice_paste.tray.default_config_path", return_value=tmp_path / "c.toml")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.set_language("ru")
    assert app._cfg.language == "ru"


def test_set_backend_updates_cfg(mocker, tmp_path):
    mocker.patch("voice_paste.tray.default_config_path", return_value=tmp_path / "c.toml")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.set_backend("openai")
    assert app._cfg.transcription.backend == "openai"


def test_languages_and_backends_constants():
    assert "auto" in LANGUAGES
    assert "en" in LANGUAGES
    assert "ru" in LANGUAGES
    assert "whisperx" in BACKENDS
    assert "docker" in BACKENDS
    assert "openai" in BACKENDS


# ── copy again ────────────────────────────────────────────────────────────────

def test_copy_again_copies_last_text(mocker):
    mock_copy = mocker.patch("voice_paste.tray.clipboard.copy")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.last_text = "hello world"
    app.copy_again()
    mock_copy.assert_called_once_with("hello world")


def test_copy_again_noop_when_no_last_text(mocker):
    mock_copy = mocker.patch("voice_paste.tray.clipboard.copy")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.copy_again()
    mock_copy.assert_not_called()


# ── retry ─────────────────────────────────────────────────────────────────────

def test_retry_transcribes_last_wav(mocker, tmp_path):
    wav = tmp_path / "last.wav"
    wav.write_bytes(b"\x00" * 100)
    mock_t = mocker.MagicMock()
    mock_t.transcribe.return_value = "retry result"
    mocker.patch("voice_paste.tray.create_transcriber", return_value=mock_t)
    mocker.patch("voice_paste.tray.clipboard.copy")
    mocker.patch("voice_paste.tray.notify.notify")
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.last_wav = wav
    app.retry()
    mock_t.transcribe.assert_called_once()
    assert app.last_text == "retry result"


def test_retry_noop_when_no_last_wav(mocker):
    mock_t = mocker.MagicMock()
    mocker.patch("voice_paste.tray.create_transcriber", return_value=mock_t)
    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app.retry()
    mock_t.transcribe.assert_not_called()


# ── state transitions ─────────────────────────────────────────────────────────

def test_state_transitions_during_record(mocker, tmp_path):
    wav = tmp_path / "rec.wav"
    wav.write_bytes(b"\x00" * 100)

    states = []

    def capture_state(s):
        states.append(s)

    mocker.patch("voice_paste.tray.recorder.record_fixed")
    mock_t = mocker.MagicMock()
    mock_t.transcribe.return_value = "done"
    mocker.patch("voice_paste.tray.create_transcriber", return_value=mock_t)
    mocker.patch("voice_paste.tray.clipboard.copy")
    mocker.patch("voice_paste.tray.notify.notify")

    with patch("voice_paste.tray.load_config"):
        app = TrayApp()
    app._on_state_change = capture_state

    app._do_record(duration=3, language="en", wav_path=wav)

    assert "recording" in states
    assert "transcribing" in states
    assert app.state == "idle"
    assert app.last_text == "done"
