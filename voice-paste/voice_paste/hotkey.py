"""GNOME gsettings-based global hotkey registration for voice-paste.

Registers a custom keyboard shortcut under:
  org.gnome.settings-daemon.plugins.media-keys.custom-keybindings

Works on GNOME Wayland and X11 without extra permissions.
Requires gnome-settings-daemon to be running (standard Ubuntu desktop).
"""
from __future__ import annotations

import subprocess
from typing import Optional

_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
_LIST_KEY = "custom-keybindings"

GSETTINGS_PATH = (
    "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/voice-paste/"
)
_BINDING_SCHEMA = f"{_SCHEMA}.custom-keybinding:{GSETTINGS_PATH}"

_MODIFIER_MAP = {
    "ctrl": "<Ctrl>",
    "control": "<Ctrl>",
    "alt": "<Alt>",
    "shift": "<Shift>",
    "super": "<Super>",
    "meta": "<Super>",
    "win": "<Super>",
}


def binding_to_gnome(binding: str) -> str:
    """Convert 'ctrl+alt+space' → '<Ctrl><Alt>space'."""
    parts = binding.lower().split("+")
    result = ""
    for part in parts:
        mod = _MODIFIER_MAP.get(part)
        if mod:
            result += mod
        else:
            result += part
    return result


def _gsettings_get(schema: str, key: str) -> str:
    out = subprocess.run(
        ["gsettings", "get", schema, key],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip().strip("'\"")


def _gsettings_set(schema: str, key: str, value: str) -> None:
    subprocess.run(
        ["gsettings", "set", schema, key, value],
        check=True,
    )


def _get_keybinding_paths() -> list[str]:
    try:
        raw = _gsettings_get(_SCHEMA, _LIST_KEY)
        if raw in ("@as []", "[]", ""):
            return []
        return [p.strip().strip("'\"") for p in raw.strip("[]").split(",") if p.strip()]
    except subprocess.CalledProcessError:
        return []


def current_binding() -> Optional[str]:
    """Return the active GNOME binding string, or None if not registered."""
    if GSETTINGS_PATH not in _get_keybinding_paths():
        return None
    try:
        return _gsettings_get(_BINDING_SCHEMA, "binding")
    except subprocess.CalledProcessError:
        return None


def register(binding: str, command: str = "voice-paste start") -> None:
    """Register (or update) the voice-paste GNOME custom shortcut."""
    gnome_binding = binding_to_gnome(binding)

    paths = _get_keybinding_paths()
    if GSETTINGS_PATH not in paths:
        paths.append(GSETTINGS_PATH)
        paths_str = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        _gsettings_set(_SCHEMA, _LIST_KEY, paths_str)

    _gsettings_set(_BINDING_SCHEMA, "name", "voice-paste")
    _gsettings_set(_BINDING_SCHEMA, "command", command)
    _gsettings_set(_BINDING_SCHEMA, "binding", gnome_binding)


def unregister() -> None:
    """Remove the voice-paste GNOME custom shortcut."""
    paths = _get_keybinding_paths()
    if GSETTINGS_PATH not in paths:
        return
    paths.remove(GSETTINGS_PATH)
    paths_str = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
    _gsettings_set(_SCHEMA, _LIST_KEY, paths_str)
