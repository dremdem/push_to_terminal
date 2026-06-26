import os
from abc import ABC, abstractmethod
from pathlib import Path

from openai import OpenAI


class BaseTranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None) -> str: ...


class OpenAITranscriber(BaseTranscriber):
    def __init__(self, model: str = "whisper-1") -> None:
        self._model = model

    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable not set.\n"
                "Set it with:  export OPENAI_API_KEY=sk-..."
            )
        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as f:
            kwargs: dict = {"model": self._model, "file": f}
            if language and language != "auto":
                kwargs["language"] = language
            result = client.audio.transcriptions.create(**kwargs)
        return result.text


def create_transcriber(backend: str = "openai", model: str = "whisper-1") -> BaseTranscriber:
    if backend == "openai":
        return OpenAITranscriber(model=model)
    raise ValueError(f"Unknown transcription backend: {backend!r}")
