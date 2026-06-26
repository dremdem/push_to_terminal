import os
import shutil
import subprocess


def copy(text: str) -> None:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland":
        _copy_wayland(text)
    else:
        _copy_x11(text)


def _copy_wayland(text: str) -> None:
    tool = shutil.which("wl-copy")
    if not tool:
        raise RuntimeError(
            "wl-copy not found. Install with:\n  sudo apt install wl-clipboard"
        )
    subprocess.run([tool], input=text.encode(), check=True, timeout=5)


def _copy_x11(text: str) -> None:
    for tool, args in [
        ("xclip", ["-selection", "clipboard"]),
        ("xsel", ["--clipboard", "--input"]),
    ]:
        found = shutil.which(tool)
        if found:
            subprocess.run([found] + args, input=text.encode(), check=True, timeout=5)
            return
    raise RuntimeError(
        "No clipboard tool found. Install with:\n  sudo apt install xclip"
    )
