"""Tests for the rescue file — where a transcription goes when the clipboard refuses it (issue #29)."""
from datetime import datetime

import pytest

from voice_paste import rescue


def test_save_writes_the_text(tmp_path):
    path = rescue.save("привет мир", path=tmp_path / "rescued.txt")
    assert "привет мир" in path.read_text(encoding="utf-8")


def test_save_returns_the_path_it_used(tmp_path):
    target = tmp_path / "rescued.txt"
    assert rescue.save("x", path=target) == target


def test_save_stamps_the_entry_with_date_and_time(tmp_path):
    path = rescue.save("x", path=tmp_path / "r.txt", now=datetime(2026, 9, 24, 23, 27, 31))
    assert "2026-09-24 23:27:31" in path.read_text(encoding="utf-8")


def test_save_appends_rather_than_replacing(tmp_path):
    target = tmp_path / "r.txt"
    rescue.save("первая", path=target)
    rescue.save("вторая", path=target)
    body = target.read_text(encoding="utf-8")
    assert "первая" in body and "вторая" in body


def test_entries_are_separated(tmp_path):
    target = tmp_path / "r.txt"
    rescue.save("первая", path=target)
    rescue.save("вторая", path=target)
    # Two header lines means two findable entries rather than one run-on blob.
    # (The separator itself appears twice per header — either side of the stamp.)
    headers = [
        line for line in target.read_text(encoding="utf-8").splitlines()
        if line.startswith(rescue.SEPARATOR)
    ]
    assert len(headers) == 2


def test_save_creates_missing_directories(tmp_path):
    path = rescue.save("x", path=tmp_path / "deep" / "deeper" / "r.txt")
    assert path.exists()


def test_save_preserves_multiline_text(tmp_path):
    path = rescue.save("одна\nдве", path=tmp_path / "r.txt")
    assert "одна\nдве" in path.read_text(encoding="utf-8")


def test_default_path_is_outside_the_cluttered_state_root(tmp_path):
    # ~/.local/state/voice-paste/ holds the socket, the PID file and ~150 stray
    # wavs the user put there.  The rescue file lives in its own subdirectory.
    assert rescue.default_path().parent.name == "log"
    assert rescue.default_path().name == "rescued.txt"


def test_save_refuses_empty_text(tmp_path):
    with pytest.raises(ValueError):
        rescue.save("   ", path=tmp_path / "r.txt")
