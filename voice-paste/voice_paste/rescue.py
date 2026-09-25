"""Somewhere for a transcription to land when the clipboard refuses it — issue #29.

Before this, a clipboard failure threw the text away: ``daemon.run()`` reported
the error and its ``finally`` deleted the recording, so the one expensive part
of the job — the audio and the transcription — was gone with nothing to retry
from.  Now the text is appended here first, and the notification says where.

One file, appended to, each entry stamped — so it stays greppable instead of
turning into a directory of numbered fragments.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

SEPARATOR = "─" * 12
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def default_path() -> Path:
    return Path.home() / ".local" / "state" / "voice-paste" / "log" / "rescued.txt"


def save(text: str, path: Path | None = None, now: datetime | None = None) -> Path:
    """Append ``text`` under a timestamped header. Returns the file written to."""
    if not text or not text.strip():
        raise ValueError("refusing to rescue empty text")

    path = Path(path) if path is not None else default_path()
    now = now or datetime.now()

    path.parent.mkdir(parents=True, exist_ok=True)
    entry = "{sep} {stamp} {sep}\n{text}\n\n".format(
        sep=SEPARATOR, stamp=now.strftime(TIME_FORMAT), text=text.strip()
    )
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(entry)
    return path
