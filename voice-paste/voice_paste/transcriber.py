import os
from abc import ABC, abstractmethod
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]


class BaseTranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None) -> str: ...


class WhisperXTranscriber(BaseTranscriber):
    """Local transcription via whisperx (faster-whisper backend, CUDA-accelerated)."""

    def __init__(
        self,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self._model_name = model
        self._device = self._resolve_device(device)
        self._compute_type = self._resolve_compute_type(compute_type)
        self._model = None  # lazy-loaded on first transcription

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _resolve_compute_type(self, compute_type: str) -> str:
        if compute_type != "auto":
            return compute_type
        return "float16" if self._device == "cuda" else "int8"

    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        try:
            import whisperx
        except ImportError:
            raise RuntimeError(
                "whisperx is not installed.\n"
                "Install (GPU):  pip install torch torchvision torchaudio "
                "--index-url https://download.pytorch.org/whl/cu121 && pip install whisperx\n"
                "Install (CPU):  pip install whisperx"
            )
        if self._model is None:
            self._model = whisperx.load_model(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            )
        audio = whisperx.load_audio(str(audio_path))
        lang = language if language and language != "auto" else None
        result = self._model.transcribe(audio, language=lang)
        return " ".join(seg["text"].strip() for seg in result["segments"]).strip()


class OpenAITranscriber(BaseTranscriber):
    """Cloud transcription via OpenAI Whisper API (requires OPENAI_API_KEY)."""

    def __init__(self, model: str = "whisper-1") -> None:
        self._model = model

    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        if OpenAI is None:
            raise RuntimeError(
                "openai package not installed.\n"
                "Install with:  pip install openai"
            )
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


def create_transcriber(
    backend: str = "whisperx",
    model: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
) -> BaseTranscriber:
    if backend == "whisperx":
        return WhisperXTranscriber(model=model, device=device, compute_type=compute_type)
    if backend == "openai":
        return OpenAITranscriber(model=model)
    raise ValueError(f"Unknown transcription backend: {backend!r}")
