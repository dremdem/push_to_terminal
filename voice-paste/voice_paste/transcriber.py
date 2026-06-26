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
        vad_method: str = "silero",
    ) -> None:
        self._model_name = model
        self._device = self._resolve_device(device)
        self._compute_type = self._resolve_compute_type(compute_type)
        self._vad_method = vad_method
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
    def _patch_torch_hub() -> None:
        # torch.hub._parse_repo_info fetches github.com to detect the default
        # branch (main vs master) when no ':ref' is given in the repo string.
        # This network call blocks even when the repo is already cached locally,
        # hanging indefinitely on slow or unavailable connections.
        # Fix: wrap hub.load to inject the cached branch ref, skipping GitHub.
        try:
            import os
            import torch.hub as _hub
            if getattr(_hub.load, "_whisperx_patched", False):
                return
            _orig_hub_load = _hub.load

            def _hub_load(repo_or_dir, model, *args, source="github", **kwargs):
                if (
                    source == "github"
                    and isinstance(repo_or_dir, str)
                    and "/" in repo_or_dir
                    and ":" not in repo_or_dir
                ):
                    hub_dir = _hub.get_dir()
                    owner, repo = repo_or_dir.split("/", 1)
                    for ref in ("master", "main"):
                        if os.path.exists(os.path.join(hub_dir, f"{owner}_{repo}_{ref}")):
                            repo_or_dir = f"{repo_or_dir}:{ref}"
                            break
                return _orig_hub_load(repo_or_dir, model, *args, source=source, **kwargs)

            _hub_load._whisperx_patched = True  # type: ignore[attr-defined]
            _hub.load = _hub_load
        except (ImportError, AttributeError):
            pass

    @staticmethod
    def _patch_torch_load() -> None:
        # PyTorch 2.6 changed the weights_only default from False → True.
        # The pyannote VAD checkpoint (used by whisperx) was pickled before
        # this change and contains arbitrary globals (omegaconf types, typing
        # specials, …).  Enumerating every type is a losing battle — the list
        # changes across pyannote versions.
        # Solution: restore the pre-2.6 behaviour for calls that don't
        # explicitly set weights_only.  The checkpoint is from HuggingFace
        # (trusted source), so weights_only=False is safe here.
        # This is exactly what PyTorch recommends as Option 1 in the error.
        try:
            import torch
            if getattr(torch.load, "_whisperx_patched", False):
                return  # already applied; don't double-wrap
            _orig = torch.load

            def _load(*args, **kwargs):
                # lightning_fabric passes weights_only=None (not absent),
                # so setdefault would not fire.  We want False for None/absent;
                # only an explicit True should be preserved.
                if kwargs.get("weights_only") is not True:
                    kwargs["weights_only"] = False
                return _orig(*args, **kwargs)

            _load._whisperx_patched = True  # type: ignore[attr-defined]
            torch.load = _load
        except (ImportError, AttributeError):
            pass  # PyTorch not installed or too old to matter

    def transcribe(self, audio_path: Path, language: str | None = None) -> str:
        try:
            import whisperx
        except ImportError:
            raise RuntimeError(
                "whisperx is not installed.\n"
                "Run:  uv sync  (torch + whisperx are declared in pyproject.toml)"
            )
        self._patch_torch_load()
        self._patch_torch_hub()
        if self._model is None:
            self._model = whisperx.load_model(
                self._model_name,
                device=self._device,
                compute_type=self._compute_type,
                vad_method=self._vad_method,
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
    vad_method: str = "silero",
) -> BaseTranscriber:
    if backend == "whisperx":
        return WhisperXTranscriber(
            model=model, device=device, compute_type=compute_type, vad_method=vad_method
        )
    if backend == "openai":
        return OpenAITranscriber(model=model)
    raise ValueError(f"Unknown transcription backend: {backend!r}")
