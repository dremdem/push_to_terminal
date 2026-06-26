"""Auto-paste support for v0.3.

Wayland: uses ydotool (requires udev rule or ydotool group — see README).
X11:     uses xdotool.

Auto-paste is opt-in (auto_paste = false by default).
Enter/Return is NEVER injected under any circumstances.
"""
from __future__ import annotations

import os
import shutil
import subprocess


class PasteError(RuntimeError):
    """Raised when auto-paste fails (missing tool, non-zero exit, etc.)."""


def _tool_for_session() -> str:
    """Return the available paste tool name for the current session type.

    Raises PasteError if the required tool is not installed.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        if shutil.which("ydotool"):
            return "ydotool"
        raise PasteError(
            "ydotool not found — required for auto-paste on Wayland.\n"
            "Install: sudo apt install ydotool\n"
            "Then add yourself to the ydotool group:\n"
            "  sudo usermod -aG ydotool $USER  (re-login required)\n"
            "Or run as root once to create the udev rule:\n"
            "  sudo ydotoold &"
        )
    # X11 or unknown session
    if shutil.which("xdotool"):
        return "xdotool"
    raise PasteError(
        "xdotool not found — required for auto-paste on X11.\n"
        "Install: sudo apt install xdotool"
    )


def _keystroke(tool: str, keys: str) -> None:
    """Send a keystroke combination via ydotool or xdotool."""
    if tool == "ydotool":
        cmd = ["ydotool", "key", keys]
    else:
        cmd = ["xdotool", "key", "--clearmodifiers", keys]
    result = subprocess.run(cmd, capture_output=True, timeout=5)
    if result.returncode != 0:
        raise PasteError(
            f"{tool} exited {result.returncode}: {result.stderr.decode().strip()}"
        )


def paste(target: str) -> None:
    """Inject a paste keystroke into the active window.

    target="clipboard" → no-op (text already in clipboard, user pastes manually)
    target="terminal"  → Ctrl+Shift+V  (terminal paste shortcut)
    target="active"    → Ctrl+V        (standard paste shortcut)

    Enter is NEVER sent.  Raises PasteError if the tool is missing or fails.
    """
    if target == "clipboard":
        return

    tool = _tool_for_session()

    if target == "terminal":
        _keystroke(tool, "ctrl+shift+v")
    else:
        _keystroke(tool, "ctrl+v")
