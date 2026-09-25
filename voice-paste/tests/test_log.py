"""Tests for file logging (issue #29) — the daemon runs with stderr=DEVNULL,
so without this there is no record of anything that happens inside it."""
import logging

from voice_paste import log as log_mod


def test_setup_creates_the_log_file(tmp_path):
    path = log_mod.setup(path=tmp_path / "log" / "voice-paste.log")
    logging.getLogger("voice_paste").info("hello")
    assert path.exists()


def test_messages_reach_the_file(tmp_path):
    path = log_mod.setup(path=tmp_path / "v.log")
    log_mod.get(__name__).info("транскрипция готова")
    assert "транскрипция готова" in path.read_text(encoding="utf-8")


def test_lines_carry_a_timestamp_and_level(tmp_path):
    path = log_mod.setup(path=tmp_path / "v.log")
    log_mod.get(__name__).warning("careful")
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "WARNING" in line
    assert line[:4].isdigit()  # starts with a year


def test_setup_is_idempotent(tmp_path):
    path = tmp_path / "v.log"
    log_mod.setup(path=path)
    log_mod.setup(path=path)
    log_mod.get(__name__).info("once")
    assert path.read_text(encoding="utf-8").count("once") == 1


def test_setup_does_not_raise_when_the_path_is_unusable(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    log_mod.setup(path=blocker / "v.log")  # must degrade, not crash the daemon
    log_mod.get(__name__).info("still alive")


def test_default_path_is_in_its_own_directory():
    assert log_mod.default_path().parent.name == "log"
    assert log_mod.default_path().name == "voice-paste.log"


def test_exceptions_are_logged_with_a_traceback(tmp_path):
    path = log_mod.setup(path=tmp_path / "v.log")
    try:
        raise ValueError("boom")
    except ValueError:
        log_mod.get(__name__).exception("failed")
    body = path.read_text(encoding="utf-8")
    assert "Traceback" in body and "boom" in body
