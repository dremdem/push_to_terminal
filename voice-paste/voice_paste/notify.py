import shutil
import subprocess


def notify(message: str, title: str = "voice-paste") -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], timeout=5)
    else:
        print(f"[{title}] {message}")
