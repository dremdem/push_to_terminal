"""Tests for lingua_core — the Sublime-free half of the plugin (issue #23)."""
import json
import socket
import urllib.error

import pytest

import lingua_core as lc


# ── text preparation ──────────────────────────────────────────────────────────

def test_normalize_selection_collapses_code_indentation():
    raw = "    Recording runs as a detached daemon\n    coordinated over a Unix socket.\n"
    assert lc.normalize_selection(raw) == (
        "Recording runs as a detached daemon coordinated over a Unix socket."
    )


def test_normalize_selection_of_blank_text_is_empty():
    assert lc.normalize_selection("   \n\t \n") == ""


def test_normalize_selection_keeps_paragraph_as_one_line():
    assert "\n" not in lc.normalize_selection("one\ntwo\n\n\nthree")


def test_sentence_around_returns_the_containing_sentence():
    text = "First one. Copper wire has a lead core. Third one."
    pos = text.index("lead")
    assert lc.sentence_around(text, pos) == "Copper wire has a lead core."


def test_sentence_around_handles_first_and_last_sentence():
    text = "Alpha beta. Gamma delta."
    assert lc.sentence_around(text, 0) == "Alpha beta."
    assert lc.sentence_around(text, len(text) - 2) == "Gamma delta."


def test_sentence_around_without_punctuation_returns_whole_text():
    text = "just a fragment of prose"
    assert lc.sentence_around(text, 5) == text


def test_sentence_around_out_of_range_does_not_raise():
    assert lc.sentence_around("Alpha beta.", 999) == "Alpha beta."


# ── prompt ────────────────────────────────────────────────────────────────────

def test_build_request_carries_the_text():
    body = lc.build_request("The bank refused the loan.")
    assert "The bank refused the loan." in body["prompt"]


def test_system_prompt_tells_the_model_to_keep_technical_terms():
    body = lc.build_request("anything")
    system = body["system"].lower()
    assert "unix socket" in system  # the terms that opus-mt mangled, given as examples
    assert "push-to-talk" in system


def test_build_request_includes_context_when_given():
    body = lc.build_request("lead", context="Copper wire has a lead core.")
    assert "Copper wire has a lead core." in body["prompt"]
    assert "lead" in body["prompt"]


def test_build_request_forbids_translating_the_context():
    # Without this, gemma3:4b translates the whole sentence rather than the word.
    prompt = lc.build_request("lead", context="Copper wire has a lead core.")["prompt"].lower()
    assert "не переводи контекст" in prompt


def test_build_request_asks_for_a_short_answer_for_a_word():
    assert "максимум два слова" in lc.build_request("lead", context="A lead core.")["prompt"].lower()


def test_build_request_omits_context_section_when_absent():
    assert "Copper" not in lc.build_request("lead")["prompt"]


# ── cache key ─────────────────────────────────────────────────────────────────

def test_cache_key_is_stable():
    assert lc.cache_key("hello", "gemma3:4b", None) == lc.cache_key("hello", "gemma3:4b", None)


def test_cache_key_varies_by_text_model_and_context():
    base = lc.cache_key("hello", "gemma3:4b", None)
    assert base != lc.cache_key("hallo", "gemma3:4b", None)
    assert base != lc.cache_key("hello", "qwen3:8b", None)
    assert base != lc.cache_key("hello", "gemma3:4b", "some sentence")


def test_cache_key_changes_when_the_prompt_changes(monkeypatch):
    before = lc.cache_key("hello", "gemma3:4b", None)
    monkeypatch.setattr(lc, "PROMPT_VERSION", lc.PROMPT_VERSION + 1)
    assert lc.cache_key("hello", "gemma3:4b", None) != before


# ── cache ─────────────────────────────────────────────────────────────────────

def test_cache_roundtrip(tmp_path):
    cache = lc.Cache(tmp_path / "c.sqlite3")
    cache.set("k", "Банк отклонил заявку.")
    assert cache.get("k") == "Банк отклонил заявку."


def test_cache_miss_returns_none(tmp_path):
    assert lc.Cache(tmp_path / "c.sqlite3").get("nope") is None


def test_cache_persists_across_instances(tmp_path):
    path = tmp_path / "c.sqlite3"
    lc.Cache(path).set("k", "v")
    assert lc.Cache(path).get("k") == "v"


def test_cache_creates_missing_parent_directories(tmp_path):
    cache = lc.Cache(tmp_path / "deep" / "deeper" / "c.sqlite3")
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_unusable_cache_path_degrades_to_no_cache(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    cache = lc.Cache(blocker / "c.sqlite3")  # must not raise
    cache.set("k", "v")
    assert cache.get("k") is None


# ── Ollama client ─────────────────────────────────────────────────────────────

class FakeTransport:
    """Stands in for urllib: records requests, replays canned responses."""

    def __init__(self, response="Банк отклонил заявку.", raises=None):
        self.calls = []
        self._response = response
        self._raises = raises

    def __call__(self, url, payload, timeout):
        self.calls.append({"url": url, "body": json.loads(payload), "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return json.dumps({"response": self._response}).encode()


def test_translate_returns_the_models_answer():
    client = lc.OllamaClient(transport=FakeTransport())
    assert client.translate("The bank refused the loan.") == "Банк отклонил заявку."


def test_translate_strips_surrounding_whitespace():
    client = lc.OllamaClient(transport=FakeTransport(response="  Банк.\n\n"))
    assert client.translate("x") == "Банк."


def test_translate_posts_to_the_generate_endpoint():
    t = FakeTransport()
    lc.OllamaClient(url="http://localhost:11434", transport=t).translate("x")
    assert t.calls[0]["url"] == "http://localhost:11434/api/generate"


def test_translate_sends_the_configured_model_and_keep_alive():
    t = FakeTransport()
    lc.OllamaClient(model="gemma3:4b", keep_alive="30m", transport=t).translate("x")
    body = t.calls[0]["body"]
    assert body["model"] == "gemma3:4b"
    assert body["keep_alive"] == "30m"


def test_translate_requests_a_deterministic_non_streaming_answer():
    t = FakeTransport()
    lc.OllamaClient(transport=t).translate("x")
    body = t.calls[0]["body"]
    assert body["stream"] is False
    assert body["think"] is False          # qwen3 & co. must not burn time thinking
    assert body["options"]["temperature"] == 0


def test_connection_refused_is_reported_as_backend_offline():
    t = FakeTransport(raises=urllib.error.URLError(ConnectionRefusedError()))
    with pytest.raises(lc.BackendOffline) as exc:
        lc.OllamaClient(transport=t).translate("x")
    assert "ollama" in str(exc.value).lower()  # the message must say what to start


def test_timeout_is_reported_as_backend_timeout():
    t = FakeTransport(raises=socket.timeout("timed out"))
    with pytest.raises(lc.BackendTimeout):
        lc.OllamaClient(transport=t).translate("x")


def test_missing_model_is_reported_with_the_pull_command():
    t = FakeTransport(raises=urllib.error.HTTPError(
        "u", 404, 'model "gemma3:4b" not found', {}, None))
    with pytest.raises(lc.ModelMissing) as exc:
        lc.OllamaClient(model="gemma3:4b", transport=t).translate("x")
    assert "ollama pull gemma3:4b" in str(exc.value)


def test_backend_errors_all_share_one_base_class():
    for err in (lc.BackendOffline, lc.BackendTimeout, lc.ModelMissing):
        assert issubclass(err, lc.TranslateError)


def test_warm_up_loads_the_model_without_translating():
    t = FakeTransport()
    lc.OllamaClient(transport=t).warm_up()
    assert len(t.calls) == 1
    assert t.calls[0]["body"]["options"]["num_predict"] == 0


def test_warm_up_never_raises_when_the_backend_is_down():
    t = FakeTransport(raises=urllib.error.URLError(ConnectionRefusedError()))
    lc.OllamaClient(transport=t).warm_up()  # best-effort: must stay silent


# ── Translator (client + cache) ───────────────────────────────────────────────

def test_translator_caches_repeated_requests(tmp_path):
    t = FakeTransport()
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    assert tr.translate("The bank refused the loan.") == "Банк отклонил заявку."
    assert tr.translate("The bank refused the loan.") == "Банк отклонил заявку."
    assert len(t.calls) == 1


def test_translator_treats_different_context_as_a_different_request(tmp_path):
    t = FakeTransport()
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    tr.translate("lead", context="Copper wire has a lead core.")
    tr.translate("lead", context="She will lead the team.")
    assert len(t.calls) == 2


def test_translator_normalizes_before_sending(tmp_path):
    t = FakeTransport()
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    tr.translate("  The bank\n    refused the loan.  ")
    assert "The bank refused the loan." in t.calls[0]["body"]["prompt"]


def test_translator_hits_the_cache_regardless_of_formatting(tmp_path):
    t = FakeTransport()
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    tr.translate("The bank refused the loan.")
    tr.translate("The bank\n  refused the loan.")
    assert len(t.calls) == 1


def test_translator_returns_empty_for_blank_selection_without_calling_backend(tmp_path):
    t = FakeTransport()
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    assert tr.translate("   \n  ") == ""
    assert t.calls == []


def test_translator_does_not_cache_failures(tmp_path):
    t = FakeTransport(raises=socket.timeout("timed out"))
    tr = lc.Translator(client=lc.OllamaClient(transport=t), cache=lc.Cache(tmp_path / "c.db"))
    with pytest.raises(lc.BackendTimeout):
        tr.translate("x")
    t._raises = None
    assert tr.translate("x") == "Банк отклонил заявку."


# ── popup rendering ───────────────────────────────────────────────────────────

def test_render_popup_shows_translation_and_source():
    html = lc.render_popup("The bank refused the loan.", "Банк отклонил заявку.")
    assert "Банк отклонил заявку." in html
    assert "The bank refused the loan." in html


def test_render_popup_escapes_html_in_the_source_text():
    html = lc.render_popup("<script>alert(1)</script> & co", "перевод")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_render_error_names_the_problem():
    html = lc.render_error(lc.BackendOffline("Ollama is not running"))
    assert "Ollama is not running" in html


def test_render_error_escapes_the_message():
    assert "<b>" not in lc.render_error(lc.TranslateError("<b>boom</b>"))
