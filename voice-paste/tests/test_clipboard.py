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


# ── retry (issue #29) ─────────────────────────────────────────────────────────
# A wl-copy call measured on the dev machine takes ~64 ms, five times out of
# five.  The 5 s timeout that was firing in the wild is a hard stall, not
# slowness, so a second attempt a quarter-second later is worth making.

import subprocess

import voice_paste.clipboard as clip


@pytest.fixture
def wayland(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value="/usr/bin/wl-copy")
    mocker.patch("time.sleep")  # keep the retry backoff out of the test runtime


def test_copy_retries_after_a_timeout_and_succeeds(wayland, mocker):
    run = mocker.patch(
        "subprocess.run",
        side_effect=[subprocess.TimeoutExpired(cmd="wl-copy", timeout=5), None],
    )
    copy("hello")
    assert run.call_count == 2


def test_copy_retries_after_a_nonzero_exit(wayland, mocker):
    run = mocker.patch(
        "subprocess.run",
        side_effect=[subprocess.CalledProcessError(1, "wl-copy"), None],
    )
    copy("hello")
    assert run.call_count == 2


def test_copy_gives_up_after_the_configured_attempts(wayland, mocker):
    run = mocker.patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="wl-copy", timeout=5)
    )
    with pytest.raises(clip.ClipboardError):
        copy("hello", attempts=3)
    assert run.call_count == 3


def test_the_failure_says_how_many_attempts_were_made(wayland, mocker):
    mocker.patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="wl-copy", timeout=5)
    )
    with pytest.raises(clip.ClipboardError, match="3"):
        copy("hello", attempts=3)


def test_clipboard_error_is_a_runtime_error():
    # daemon.run() catches Exception and the CLI catches Exception; existing
    # callers and tests must keep working unchanged.
    assert issubclass(clip.ClipboardError, RuntimeError)


def test_copy_waits_between_attempts(wayland, mocker):
    sleep = mocker.patch("time.sleep")
    mocker.patch(
        "subprocess.run",
        side_effect=[subprocess.TimeoutExpired(cmd="wl-copy", timeout=5), None],
    )
    copy("hello")
    assert sleep.call_count == 1
    assert sleep.call_args[0][0] > 0


def test_a_missing_tool_is_not_retried(mocker):
    # No amount of retrying installs wl-clipboard.
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
    mocker.patch("shutil.which", return_value=None)
    run = mocker.patch("subprocess.run")
    with pytest.raises(RuntimeError, match="wl-copy"):
        copy("hello")
    assert run.call_count == 0


def test_x11_retries_too(mocker):
    mocker.patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
    mocker.patch("shutil.which", side_effect=lambda cmd: "/usr/bin/xclip" if cmd == "xclip" else None)
    mocker.patch("time.sleep")
    run = mocker.patch(
        "subprocess.run",
        side_effect=[subprocess.TimeoutExpired(cmd="xclip", timeout=5), None],
    )
    copy("hello")
    assert run.call_count == 2


def test_first_attempt_success_does_not_sleep(wayland, mocker):
    sleep = mocker.patch("time.sleep")
    mocker.patch("subprocess.run")
    copy("hello")
    assert sleep.call_count == 0
