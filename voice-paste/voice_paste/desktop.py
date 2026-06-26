"""Install/remove the voice-paste-tray .desktop entry (v0.6)."""
from __future__ import annotations

from pathlib import Path

DESKTOP_FILE = (
    Path.home() / ".local" / "share" / "applications" / "voice-paste-tray.desktop"
)
AUTOSTART_FILE = (
    Path.home() / ".config" / "autostart" / "voice-paste-tray.desktop"
)

_DESKTOP_TEMPLATE = """\
[Desktop Entry]
Name=Voice Paste
Comment=Voice-to-clipboard utility — speak, then paste
Exec={exe}
Icon=audio-input-microphone
Type=Application
Categories=Utility;Audio;
StartupNotify=false
"""

_AUTOSTART_TEMPLATE = """\
[Desktop Entry]
Name=Voice Paste Tray
Exec={exe}
Type=Application
X-GNOME-Autostart-enabled=true
"""


def install(exe_path: str, autostart: bool = False) -> None:
    """Write .desktop launcher and optionally an autostart entry."""
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(_DESKTOP_TEMPLATE.format(exe=exe_path))

    if autostart:
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(_AUTOSTART_TEMPLATE.format(exe=exe_path))


def uninstall() -> None:
    """Remove the .desktop launcher and autostart entry."""
    DESKTOP_FILE.unlink(missing_ok=True)
    AUTOSTART_FILE.unlink(missing_ok=True)
