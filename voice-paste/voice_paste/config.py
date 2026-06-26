from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


class AudioConfig(BaseModel):
    device: str = "default"
    sample_rate: int = 16000


class TranscriptionConfig(BaseModel):
    backend: str = "whisperx"
    model: str = "base"
    device: str = "auto"        # "auto", "cuda", "cpu"
    compute_type: str = "auto"  # "auto", "float16", "int8"


class PostprocessConfig(BaseModel):
    terminal_single_line: bool = True


class Config(BaseModel):
    language: Literal["auto", "ru", "en"] = "auto"
    target: Literal["clipboard", "terminal", "active"] = "clipboard"
    duration: int = 15
    auto_paste: bool = False
    audio: AudioConfig = AudioConfig()
    transcription: TranscriptionConfig = TranscriptionConfig()
    postprocess: PostprocessConfig = PostprocessConfig()


def default_config_path() -> Path:
    return Path.home() / ".config" / "voice-paste" / "config.toml"


def load_config(path: Path | None = None) -> Config:
    if path is None:
        path = default_config_path()
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    general = data.get("general", {})
    audio = data.get("audio", {})
    transcription = data.get("transcription", {})
    postprocess = data.get("postprocess", {})
    return Config(
        **general,
        audio=AudioConfig(**audio),
        transcription=TranscriptionConfig(**transcription),
        postprocess=PostprocessConfig(**postprocess),
    )
