import pytest
from voice_paste.transcriber import OpenAITranscriber, create_transcriber


def test_missing_api_key_raises_clear_error(mocker, tmp_path):
    mocker.patch.dict("os.environ", {}, clear=True)
    t = OpenAITranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        t.transcribe(wav, "auto")


def test_transcribe_calls_openai_api(mocker, tmp_path):
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
    mock_client.audio.transcriptions.create.assert_called_once()


def test_transcribe_passes_language_to_api(mocker, tmp_path):
    mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    mock_resp = mocker.MagicMock()
    mock_resp.text = "привет"
    mock_client = mocker.MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_resp
    mocker.patch("voice_paste.transcriber.OpenAI", return_value=mock_client)
    t = OpenAITranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "ru")
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs.get("language") == "ru"


def test_auto_language_omits_language_param(mocker, tmp_path):
    mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    mock_resp = mocker.MagicMock()
    mock_resp.text = "hello"
    mock_client = mocker.MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_resp
    mocker.patch("voice_paste.transcriber.OpenAI", return_value=mock_client)
    t = OpenAITranscriber()
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"data")
    t.transcribe(wav, "auto")
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert "language" not in call_kwargs


def test_create_transcriber_returns_openai_by_default():
    t = create_transcriber("openai")
    assert isinstance(t, OpenAITranscriber)


def test_create_transcriber_raises_for_unknown_backend():
    with pytest.raises(ValueError, match="Unknown"):
        create_transcriber("unknown-backend")
