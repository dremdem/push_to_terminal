from pathlib import Path
from voice_paste.config import Config, load_config, default_config_path


def test_defaults():
    c = Config()
    assert c.language == "auto"
    assert c.target == "clipboard"
    assert c.duration == 15
    assert c.auto_paste is False
    assert c.transcription.backend == "whisperx"
    assert c.transcription.model == "base"
    assert c.transcription.device == "auto"
    assert c.transcription.compute_type == "auto"
    assert c.audio.sample_rate == 16000


def test_config_path_contains_voice_paste():
    p = default_config_path()
    assert "voice-paste" in str(p)
    assert p.name == "config.toml"


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    c = load_config(tmp_path / "nonexistent.toml")
    assert c.language == "auto"


def test_load_config_reads_toml(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[general]\nlanguage = "ru"\ntarget = "clipboard"\nduration = 10\nauto_paste = false\n'
    )
    c = load_config(cfg)
    assert c.language == "ru"
    assert c.duration == 10


def test_load_config_reads_transcription_section(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('[transcription]\nbackend = "openai"\nmodel = "whisper-1"\n')
    c = load_config(cfg)
    assert c.transcription.backend == "openai"
    assert c.transcription.model == "whisper-1"
