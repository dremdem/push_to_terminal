"""File logging — issue #29.

The daemon is spawned with ``stderr=DEVNULL`` (see :mod:`voice_paste.daemon`),
so until now nothing it did left a trace.  When the clipboard write started
timing out intermittently there was no way to find out what the machine was
doing at that moment — the failure was unknowable after the fact.

The log lives in its own directory rather than in the state root, which holds
the socket, the PID file, and whatever else has accumulated there.
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOGGER_NAME = "voice_paste"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_configured_path: Path | None = None


def default_path() -> Path:
    return Path.home() / ".local" / "state" / "voice-paste" / "log" / "voice-paste.log"


def setup(path: Path | None = None, level: str = "INFO") -> Path:
    """Attach a rotating file handler to the package logger.

    Idempotent: calling it twice does not double every line.  A path that
    cannot be opened is not worth crashing a daemon over — logging is a
    diagnostic, not a feature — so failure here is swallowed and the rest of
    the run continues unlogged.
    """
    global _configured_path
    path = Path(path) if path is not None else default_path()
    logger = logging.getLogger(LOGGER_NAME)

    if _configured_path == path and logger.handlers:
        return path

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            str(path), maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        _configured_path = None
        logger.addHandler(logging.NullHandler())
        return path

    handler.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    # The daemon has nowhere to send records anyway, and the CLI prints its own
    # output through rich — a root handler would duplicate both.
    logger.propagate = False
    _configured_path = path
    return path


def get(name: str) -> logging.Logger:
    """Return a child of the package logger, so every module shares the file."""
    return logging.getLogger(LOGGER_NAME).getChild(name.rsplit(".", 1)[-1])
