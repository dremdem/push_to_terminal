"""Translation core for the Sublime Text plugin — issue #23.

This module is deliberately free of ``import sublime``: everything here is plain
stdlib and can be exercised by pytest.  The Sublime-facing glue lives in
``lingua.py``, which imports this module and does nothing else of substance.

Two hard constraints shape the code:

* Sublime Text 4 has no pip, so there are **no third-party dependencies** — the
  package is installed by copying it into ``Packages/``.
* The plugin host runs Python **3.8**, so no ``X | Y`` annotations and no
  ``match``.  Tests run on 3.8 too (see ``.python-version``).

The backend is a local Ollama instance.  Ollama already runs as a service and
already keeps the model warm, so there is no daemon of our own to write —
see the issue for the benchmark that settled the model choice.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import socket
import sqlite3
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_TIMEOUT = 20.0
# Long enough to survive a coffee break: a cold load costs ~3 s, and open-webui
# on the same machine will happily evict the model if we let it go idle.
DEFAULT_KEEP_ALIVE = "30m"

# Bump whenever the prompt changes — it is part of the cache key, so old
# answers produced by an older prompt are never served again.
PROMPT_VERSION = 2

# Version 1 opened with «Ты переводчик … для программиста» and asked for a
# «краткий» translation.  Both were wrong outside documentation: on fiction the
# model rendered `to your northeast` as «от цели» and dropped `our` entirely
# (issue #25).  The base is now domain-neutral; anything domain-specific arrives
# through the caller's hint.
SYSTEM_PROMPT = (
    "Ты профессиональный переводчик с английского на русский. "
    "Переводи точно и естественно, сохраняя смысл, тон и регистр оригинала. "
    "Ничего не опускай: каждое местоимение (our, your, my) обязано остаться. "
    "Имена собственные и позывные оставляй латиницей. "
    "Названия инструментов, протоколов и API (Unix socket, daemon, hotkey, "
    "backend, push-to-talk) не переводи буквально — оставляй как есть. "
    "Выдай ТОЛЬКО перевод: без пояснений, без кавычек, без исходного текста."
)


def build_system_prompt(hint=None):
    # type: (str) -> str
    """Base prompt, optionally extended with what the caller knows about the text.

    A bare genre label ("военный радиообмен") only recovers the pronouns.  What
    actually repairs the jargon is spelling out the ambiguous words — telling the
    model that `a hit` is засечка сигнала and not попадание снаряда.  The hint is
    free text so it can carry either, or both.
    """
    hint = (hint or "").strip()
    if not hint:
        return SYSTEM_PROMPT
    return SYSTEM_PROMPT + " Об этом тексте известно: " + hint


# ── errors ────────────────────────────────────────────────────────────────────

class TranslateError(Exception):
    """Base class for every failure the popup has to render."""


class BackendOffline(TranslateError):
    """Ollama is not reachable at all."""


class BackendTimeout(TranslateError):
    """Ollama accepted the request but did not answer in time."""


class ModelMissing(TranslateError):
    """Ollama is up but does not have the configured model pulled."""


# ── text preparation ──────────────────────────────────────────────────────────

def normalize_selection(text):
    # type: (str) -> str
    """Flatten a selection into a single line.

    Text selected in an editor arrives wrapped and indented.  Feeding that to
    the model wastes tokens and, worse, makes two selections of the same
    sentence miss each other in the cache.
    """
    if not text:
        return ""
    return " ".join(text.split())


_SENTENCE_END = ".!?"


def sentence_around(text, pos):
    # type: (str, int) -> str
    """Return the sentence containing ``pos``.

    A single word is nearly untranslatable on its own — ``lead`` is either
    свинец or возглавить depending on what surrounds it — so the word under the
    cursor is always sent together with its sentence.
    """
    if not text:
        return ""
    pos = max(0, min(pos, len(text) - 1))

    start = 0
    for i in range(pos, 0, -1):
        if text[i - 1] in _SENTENCE_END:
            start = i
            break

    end = len(text)
    for i in range(pos, len(text)):
        if text[i] in _SENTENCE_END:
            end = i + 1
            break

    return text[start:end].strip() or text.strip()


def build_request(text, context=None, hint=None):
    # type: (str, str, str) -> dict
    """Build the ``system``/``prompt`` pair sent to the model."""
    if context:
        # Asking for "the fragment in the context of this sentence" makes the
        # model helpfully translate the whole sentence instead of the word
        # (lead + "Copper wire has a lead core." came back as «медный провод
        # имеет ядро из свинца»).  Naming the context and the word separately,
        # and forbidding the context outright, gets the single word every time.
        prompt = (
            'Контекст: "{context}"\n'
            'Слово: "{text}"\n'
            "Дай русский перевод ТОЛЬКО этого слова в этом значении. "
            "Максимум два слова в ответе. Не переводи контекст."
        ).format(text=text, context=context)
    else:
        prompt = text
    # The hint goes in the system prompt only: repeating it in the user prompt
    # invites the model to translate the hint along with the text.
    return {"system": build_system_prompt(hint), "prompt": prompt}


# ── cache ─────────────────────────────────────────────────────────────────────

def cache_key(text, model, context, hint=None):
    # type: (str, str, str, str) -> str
    parts = [str(PROMPT_VERSION), model, context or "", hint or "", text]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


class Cache:
    """A sqlite-backed translation cache.

    Hovering re-asks for the same word constantly, and the answer is
    deterministic (``temperature: 0``), so caching turns the second lookup into
    a free one.  A cache that cannot be opened degrades to a no-op rather than
    taking the popup down with it.
    """

    def __init__(self, path):
        # type: (object) -> None
        self._path = str(path)
        self._ok = True
        try:
            parent = os.path.dirname(self._path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with self._connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS translations ("
                    "  key TEXT PRIMARY KEY,"
                    "  value TEXT NOT NULL,"
                    "  created_at REAL DEFAULT (julianday('now'))"
                    ")"
                )
        except (OSError, sqlite3.Error):
            self._ok = False

    def _connect(self):
        return sqlite3.connect(self._path, timeout=5.0)

    def get(self, key):
        # type: (str) -> str
        if not self._ok:
            return None
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM translations WHERE key = ?", (key,)
                ).fetchone()
        except sqlite3.Error:
            return None
        return row[0] if row else None

    def set(self, key, value):
        # type: (str, str) -> None
        if not self._ok:
            return
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO translations (key, value) VALUES (?, ?)",
                    (key, value),
                )
        except sqlite3.Error:
            pass


# ── Ollama client ─────────────────────────────────────────────────────────────

def _urllib_transport(url, payload, timeout):
    # type: (str, bytes, float) -> bytes
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class OllamaClient:
    """Thin client for Ollama's ``/api/generate``.

    ``transport`` is injectable so the tests never touch the network.
    """

    def __init__(
        self,
        url=DEFAULT_URL,
        model=DEFAULT_MODEL,
        timeout=DEFAULT_TIMEOUT,
        keep_alive=DEFAULT_KEEP_ALIVE,
        transport=None,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._transport = transport or _urllib_transport

    def _post(self, body, timeout=None):
        # type: (dict, float) -> dict
        payload = json.dumps(body).encode("utf-8")
        endpoint = self.url + "/api/generate"
        try:
            raw = self._transport(endpoint, payload, timeout or self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise ModelMissing(
                    "Model {0} is not pulled. Run:  ollama pull {0}".format(self.model)
                )
            raise TranslateError("Ollama returned HTTP {0}".format(exc.code))
        except socket.timeout:
            raise BackendTimeout(
                "Ollama did not answer within {0:.0f}s. "
                "The model may be loading — try again.".format(timeout or self.timeout)
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise BackendTimeout("Ollama timed out while loading the model.")
            raise BackendOffline(
                "Ollama is not running at {0}. Start it with:  ollama serve".format(self.url)
            )
        except OSError:
            raise BackendOffline("Ollama is not reachable at {0}.".format(self.url))

        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise TranslateError("Ollama returned a malformed response.")

    def _body(self, system, prompt, num_predict):
        # type: (str, str, int) -> dict
        return {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            # Reasoning models (qwen3 and friends) otherwise spend seconds
            # thinking before emitting a one-line translation.
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0, "num_predict": num_predict},
        }

    def translate(self, text, context=None, hint=None):
        # type: (str, str, str) -> str
        request = build_request(text, context, hint)
        body = self._body(request["system"], request["prompt"], 512)
        return self._post(body).get("response", "").strip()

    def warm_up(self):
        # type: () -> None
        """Load the model into VRAM without generating anything.

        Called when the plugin starts so the first real lookup does not pay the
        ~3 s cold-load cost.  Best-effort: a missing backend is not an error
        worth interrupting the user's editing session for.
        """
        try:
            self._post(self._body(SYSTEM_PROMPT, "warm up", 0), timeout=self.timeout)
        except TranslateError:
            pass


# ── translator ────────────────────────────────────────────────────────────────

class Translator:
    """A cache in front of the client."""

    def __init__(self, client, cache):
        # type: (OllamaClient, Cache) -> None
        self._client = client
        self._cache = cache

    def translate(self, text, context=None, hint=None):
        # type: (str, str, str) -> str
        normalized = normalize_selection(text)
        if not normalized:
            return ""
        normalized_context = normalize_selection(context) if context else None
        normalized_hint = normalize_selection(hint) if hint else None

        key = cache_key(
            normalized, self._client.model, normalized_context, normalized_hint
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # A failure propagates without being cached: the next attempt should hit
        # the backend again rather than replay the error.
        result = self._client.translate(normalized, normalized_context, normalized_hint)
        self._cache.set(key, result)
        return result


# ── popup rendering (minihtml) ────────────────────────────────────────────────

_POPUP_CSS = """
    body { margin: 0; padding: 0.5rem 0.7rem; font-size: 1rem; }
    .translation { color: color(var(--foreground)); line-height: 1.4; }
    .source { color: color(var(--foreground) alpha(0.5)); font-size: 0.9rem;
              margin-top: 0.4rem; line-height: 1.3; }
    .error { color: color(var(--redish)); line-height: 1.4; }
"""


def render_popup(source, translation):
    # type: (str, str) -> str
    return (
        '<body id="lingua-popup"><style>{css}</style>'
        '<div class="translation">{translation}</div>'
        '<div class="source">{source}</div>'
        "</body>"
    ).format(
        css=_POPUP_CSS,
        translation=html.escape(translation),
        source=html.escape(source),
    )


def render_error(error):
    # type: (Exception) -> str
    return (
        '<body id="lingua-popup"><style>{css}</style>'
        '<div class="error">{message}</div>'
        "</body>"
    ).format(css=_POPUP_CSS, message=html.escape(str(error)))
