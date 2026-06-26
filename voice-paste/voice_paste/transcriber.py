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

    @staticmethod
    def _allow_omegaconf_globals() -> None:
        # PyTorch 2.6 changed weights_only default to True in torch.load.
        # pyannote VAD checkpoints pickle many omegaconf types (ListConfig,
        # DictConfig, ContainerMetadata, value nodes, …).  Register the whole
        # omegaconf package so we never hit this one-at-a-time.
        # NOTE: whisperx lazy-loads torch, so it is NOT in sys.modules after
        # `import whisperx`.  We must `import torch` here to guarantee it is
        # loaded before add_safe_globals is called.  Test isolation is handled
        # by tests/conftest.py which pre-loads torch at session start, ensuring
        # mock.patch.dict teardown restores rather than deletes it.
        try:
            import importlib
            import inspect
            import pkgutil
            import torch
            import omegaconf

            classes: set = set()
            for _, modname, _ in pkgutil.walk_packages(
                path=omegaconf.__path__,
                prefix=omegaconf.__name__ + ".",
                onerror=lambda _: None,
            ):
                try:
                    mod = importlib.import_module(modname)
                except Exception:
                    continue
                for _, obj in inspect.getmembers(mod, inspect.isclass):
                    if getattr(obj, "__module__", "").startswith("omegaconf"):
                        classes.add(obj)
            torch.serialization.add_safe_globals(list(classes))
        except (ImportError, AttributeError):
            pass  # omegaconf missing or PyTorch < 2.6 — nothing to do

    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        try:
            import whisperx
        except ImportError:
            raise RuntimeError(
                "whisperx is not installed.\n"
                "Run:  uv sync  (torch + whisperx are declared in pyproject.toml)"
            )
        self._allow_omegaconf_globals()
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
