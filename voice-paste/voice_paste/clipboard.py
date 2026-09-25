import os
import shutil
import subprocess
import time

from voice_paste import log as log_mod

logger = log_mod.get(__name__)

# A wl-copy call identical to the one below was timed five times in a row on the
# dev machine: 63.8–63.9 ms, every time.  So the 5 s timeout that was firing in
# the wild is not slowness — it is a hard stall, most likely a round-trip to a
# compositor that stopped answering.  A second attempt a moment later lands.
COPY_TIMEOUT = 5.0
COPY_ATTEMPTS = 3
RETRY_DELAY = 0.25


class ClipboardError(RuntimeError):
    """Every attempt to reach the clipboard failed.

    Subclasses RuntimeError so the existing `except Exception` handlers in the
    daemon and the CLI keep working unchanged.
    """


def copy(text: str, attempts: int = COPY_ATTEMPTS, timeout: float = COPY_TIMEOUT) -> None:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        tool, args = _wayland_tool()
    else:
        tool, args = _x11_tool()

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(
                [tool] + args, input=text.encode(), check=True, timeout=timeout
            )
            if attempt > 1:
                logger.info("clipboard write succeeded on attempt %d", attempt)
            return
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            # Both are transient: a timeout means the tool never got an answer,
            # and a non-zero exit means it gave up.  A missing tool never
            # reaches here — that is raised by the _tool() helpers, because no
            # amount of retrying installs a package.
            last_error = exc
            logger.warning(
                "clipboard write failed (attempt %d/%d): %s", attempt, attempts, exc
            )
            if attempt < attempts:
                time.sleep(RETRY_DELAY * attempt)

    logger.error("clipboard write failed after %d attempts", attempts)
    raise ClipboardError(
        "Could not write to the clipboard after {0} attempts: {1}".format(
            attempts, last_error
        )
    )


def _wayland_tool() -> tuple[str, list[str]]:
    tool = shutil.which("wl-copy")
    if not tool:
        raise RuntimeError(
            "wl-copy not found. Install with:\n  sudo apt install wl-clipboard"
        )
    return tool, []


def _x11_tool() -> tuple[str, list[str]]:
    for tool, args in [
        ("xclip", ["-selection", "clipboard"]),
        ("xsel", ["--clipboard", "--input"]),
    ]:
        found = shutil.which(tool)
        if found:
            return found, args
    raise RuntimeError(
        "No clipboard tool found. Install with:\n  sudo apt install xclip"
    )
