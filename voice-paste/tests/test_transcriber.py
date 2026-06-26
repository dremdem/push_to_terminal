import pytest
from voice_paste.transcriber import WhisperXTranscriber, OpenAITranscriber, create_transcriber


# ── WhisperXTranscriber ───────────────────────────────────────────────────────

def test_whisperx_transcribe_patches_torch_load(mocker, tmp_path):
    """transcribe() must call _patch_torch_load() before loading the model."""
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {"segments": [{"text": "x"}]}
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    spy = mocker.patch.object(WhisperXTranscriber, "_patch_torch_load")

    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "en")

    spy.assert_called_once()


def test_whisperx_transcribe_patches_torch_hub(mocker, tmp_path):
    """transcribe() must call _patch_torch_hub() before loading the model."""
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {"segments": [{"text": "x"}]}
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    spy = mocker.patch.object(WhisperXTranscriber, "_patch_torch_hub")

    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "en")

    spy.assert_called_once()


def test_patch_torch_hub_injects_cached_branch(mocker, tmp_path):
    """_patch_torch_hub wraps hub.load to inject the cached branch ref.

    torch.hub._parse_repo_info makes a GitHub network request to detect the
    default branch when no ':ref' appears in the repo string.  The wrapper
    should inject ':master' (or ':main') from the local cache, preventing
    the network call.
    """
    import torch.hub as hub

    original_load = hub.load
    captured: list = []

    def _fake_load(repo_or_dir, model, *args, source="github", **kwargs):
        captured.append((repo_or_dir, source))

    try:
        hub.load = _fake_load  # type: ignore[assignment]
        (tmp_path / "snakers4_silero-vad_master").mkdir()
        mocker.patch.object(hub, "get_dir", return_value=str(tmp_path))

        WhisperXTranscriber._patch_torch_hub()
        assert getattr(hub.load, "_whisperx_patched", False)

        # No ref → injects ':master' from cache
        hub.load("snakers4/silero-vad", "silero_vad")
        assert captured[-1][0] == "snakers4/silero-vad:master"

        # Explicit ref → unchanged
        hub.load("snakers4/silero-vad:main", "silero_vad")
        assert captured[-1][0] == "snakers4/silero-vad:main"

        # source=local → unchanged (already local, no network risk)
        hub.load("snakers4/silero-vad", "silero_vad", source="local")
        assert captured[-1][1] == "local"
        assert ":" not in captured[-1][0]
    finally:
        hub.load = original_load


def test_patch_torch_load_defaults_weights_only_to_false():
    """_patch_torch_load wraps torch.load so weights_only defaults to False.

    PyTorch 2.6 changed the default to True; pyannote checkpoints contain
    arbitrary globals that can't be enumerated in advance, so we revert the
    default for callers that don't explicitly set weights_only.
    """
    import torch

    original_load = torch.load
    captured_kwargs: list = []

    def _fake_load(*args, **kwargs):
        captured_kwargs.append(dict(kwargs))

    try:
        torch.load = _fake_load  # type: ignore[assignment]
        WhisperXTranscriber._patch_torch_load()
        assert getattr(torch.load, "_whisperx_patched", False)

        # No weights_only kwarg → must inject False.
        torch.load("some_path")
        assert captured_kwargs[-1].get("weights_only") is False

        # weights_only=None (lightning_fabric passes this) → must become False.
        torch.load("some_path", weights_only=None)
        assert captured_kwargs[-1].get("weights_only") is False

        # Explicit True → must be preserved.
        torch.load("some_path", weights_only=True)
        assert captured_kwargs[-1].get("weights_only") is True
    finally:
        torch.load = original_load


def test_whisperx_raises_if_not_installed(mocker, tmp_path):
    mocker.patch.dict("sys.modules", {"whisperx": None})
    t = WhisperXTranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="whisperx"):
        t.transcribe(wav, "auto")


def test_whisperx_resolves_cuda_when_torch_available(mocker):
    mock_torch = mocker.MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mocker.patch.dict("sys.modules", {"torch": mock_torch})
    t = WhisperXTranscriber(device="auto")
    assert t._device == "cuda"


def test_whisperx_resolves_cpu_when_cuda_unavailable(mocker):
    mock_torch = mocker.MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mocker.patch.dict("sys.modules", {"torch": mock_torch})
    t = WhisperXTranscriber(device="auto")
    assert t._device == "cpu"


def test_whisperx_float16_on_cuda(mocker):
    mock_torch = mocker.MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mocker.patch.dict("sys.modules", {"torch": mock_torch})
    t = WhisperXTranscriber(device="auto", compute_type="auto")
    assert t._compute_type == "float16"


def test_whisperx_int8_on_cpu(mocker):
    mocker.patch.dict("sys.modules", {"torch": None})
    t = WhisperXTranscriber(device="auto", compute_type="auto")
    assert t._device == "cpu"
    assert t._compute_type == "int8"


def test_whisperx_transcribe_calls_load_model_and_returns_text(mocker, tmp_path):
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {
        "segments": [{"text": " hello "}, {"text": " world"}]
    }
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    result = t.transcribe(wav, "en")
    assert result == "hello world"
    mock_wx.load_model.assert_called_once_with("base", device="cpu", compute_type="int8", vad_method="silero")


def test_whisperx_passes_language_when_not_auto(mocker, tmp_path):
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {"segments": [{"text": "привет"}]}
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "ru")
    call_kwargs = mock_wx.load_model.return_value.transcribe.call_args.kwargs
    assert call_kwargs.get("language") == "ru"


def test_whisperx_omits_language_for_auto(mocker, tmp_path):
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {"segments": [{"text": "hello"}]}
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "auto")
    call_kwargs = mock_wx.load_model.return_value.transcribe.call_args.kwargs
    assert call_kwargs.get("language") is None


def test_whisperx_model_is_lazy_loaded_once(mocker, tmp_path):
    mock_wx = mocker.MagicMock()
    mock_wx.load_audio.return_value = b"audio"
    mock_wx.load_model.return_value.transcribe.return_value = {"segments": [{"text": "x"}]}
    mocker.patch.dict("sys.modules", {"whisperx": mock_wx})
    t = WhisperXTranscriber(device="cpu", compute_type="int8")
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "en")
    t.transcribe(wav, "en")
    assert mock_wx.load_model.call_count == 1  # loaded once, reused


# ── OpenAITranscriber (kept as optional fallback) ─────────────────────────────

def test_openai_missing_api_key_raises(mocker, tmp_path):
    mocker.patch.dict("os.environ", {}, clear=True)
    mocker.patch("voice_paste.transcriber.OpenAI", mocker.MagicMock())  # simulate package installed
    t = OpenAITranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        t.transcribe(wav, "auto")


def test_openai_transcribe_calls_api(mocker, tmp_path):
    mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    mock_resp = mocker.MagicMock()
    mock_resp.text = "hello world"
    mock_client = mocker.MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_resp
    mocker.patch("voice_paste.transcriber.OpenAI", return_value=mock_client)
    t = OpenAITranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"fake wav data")
    result = t.transcribe(wav, "ru")
    assert result == "hello world"


# ── create_transcriber factory ────────────────────────────────────────────────

def test_create_transcriber_defaults_to_whisperx():
    t = create_transcriber()
    assert isinstance(t, WhisperXTranscriber)


def test_create_transcriber_openai():
    t = create_transcriber("openai")
    assert isinstance(t, OpenAITranscriber)


def test_create_transcriber_raises_for_unknown_backend():
    with pytest.raises(ValueError, match="Unknown"):
        create_transcriber("unknown-backend")
