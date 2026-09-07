"""Sublime Text glue for the translation popup — issue #23.

Everything that can be tested without Sublime lives in ``lingua_core``; this
file is only the parts that need the editor: reading the selection, running the
request off the UI thread, and drawing the popup.
"""
import os
import threading

import sublime
import sublime_plugin

# Import the MODULE, never its names.  Sublime hot-reloads a changed file with
# importlib.reload, which mutates the existing module object in place: attribute
# lookups pick up the new code, while names bound by `from … import …` stay
# pinned to whatever was captured at first import.  Mixing the two is what made
# a reloaded lingua.py call into a stale lingua_core and fail with
# "translate() takes from 2 to 3 positional arguments but 4 were given" (#27).
try:
    from . import lingua_core as core
except (ImportError, ValueError):  # pragma: no cover - depends on how ST loads us
    import lingua_core as core

SETTINGS_FILE = "Lingua.sublime-settings"
POPUP_MAX_WIDTH = 700
POPUP_MAX_HEIGHT = 500

# Monotonic id of the newest request.  A slow answer whose id is stale belongs
# to a selection the user has already moved away from, and is dropped.
_request_seq = 0
_seq_lock = threading.Lock()

# Last hint picked from the quick panel, offered again next time.
_last_hint = ""

NO_HINT = ""  # an explicit "translate it plain", distinct from "use the setting"


def _settings():
    return sublime.load_settings(SETTINGS_FILE)


def _make_translator():
    """Build a translator from the current settings.

    Deliberately not memoised: a cached instance would outlive a reload of
    ``lingua_core`` and keep running the old code, and the saving is ~0.2 ms
    against a ~400 ms model call — ``Cache`` opens a connection per query
    anyway.
    """
    settings = _settings()
    client = core.OllamaClient(
        url=settings.get("url", "http://localhost:11434"),
        model=settings.get("model", "gemma3:4b"),
        timeout=float(settings.get("timeout", 20.0)),
        keep_alive=settings.get("keep_alive", "30m"),
    )
    cache_path = os.path.expanduser(
        settings.get("cache_path", "~/.cache/sublime-lingua/cache.sqlite3")
    )
    return core.Translator(client=client, cache=core.Cache(cache_path)), client


def _next_seq():
    global _request_seq
    with _seq_lock:
        _request_seq += 1
        return _request_seq


def _is_current(seq):
    with _seq_lock:
        return seq == _request_seq


def _selection_and_context(view):
    """Return ``(text, context, anchor_point)`` for what should be translated.

    With a selection, that selection is translated on its own.  With just a
    caret, the word under it is translated together with its sentence — a bare
    word is ambiguous in a way the surrounding sentence resolves.
    """
    for region in view.sel():
        if not region.empty():
            return view.substr(region), None, region.begin()

    if not len(view.sel()):
        return "", None, 0

    point = view.sel()[0].begin()
    word_region = view.word(point)
    word = view.substr(word_region).strip()
    if not word:
        return "", None, point

    line_region = view.line(point)
    line = view.substr(line_region)
    context = core.sentence_around(line, point - line_region.begin())
    if context == word:
        context = None
    return word, context, word_region.begin()


class LinguaTranslateCommand(sublime_plugin.TextCommand):
    """Translate the selection (or the word under the caret) into a popup."""

    def run(self, edit, hint=None):
        text, context, point = _selection_and_context(self.view)
        if not text.strip():
            sublime.status_message("Lingua: nothing selected")
            return

        if hint is None:
            hint = _settings().get("hint", "")

        seq = _next_seq()
        sublime.status_message("Lingua: translating…")
        threading.Thread(
            target=self._work, args=(text, context, point, seq, hint), daemon=True
        ).start()

    def _work(self, text, context, point, seq, hint):
        translator, _ = _make_translator()
        try:
            translation = translator.translate(text, context, hint)
            html = core.render_popup(text, translation) if translation else None
        except core.TranslateError as exc:
            html = core.render_error(exc)
        except Exception as exc:  # never let a worker thread die silently
            html = core.render_error(core.TranslateError(str(exc)))

        if html is None:
            sublime.set_timeout(lambda: sublime.status_message("Lingua: empty answer"), 0)
            return
        sublime.set_timeout(lambda: self._show(html, point, seq), 0)

    def _show(self, html, point, seq):
        if not _is_current(seq):
            return  # the user has moved on; this answer is stale
        sublime.status_message("")
        self.view.show_popup(
            html,
            flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
            location=point,
            max_width=POPUP_MAX_WIDTH,
            max_height=POPUP_MAX_HEIGHT,
        )


class LinguaTranslateWithHintCommand(sublime_plugin.TextCommand):
    """Pick what the text is about, then translate.

    A hint is what rescues jargon: naming the genre alone only recovers the
    pronouns, while spelling out the ambiguous words ("'a hit' — засечка
    сигнала, не попадание снаряда") fixes the terms too.  See issue #25.
    """

    def run(self, edit):
        window = self.view.window()
        if window is None:
            return

        presets = [str(h) for h in _settings().get("hints", []) if str(h).strip()]
        configured = str(_settings().get("hint", "")).strip()

        options = []          # (label, subtitle, hint)
        options.append(("Без подсказки", "перевести как есть", NO_HINT))
        if configured:
            options.append(("Из настроек", configured, configured))
        if _last_hint and _last_hint != configured:
            options.append(("Прошлая подсказка", _last_hint, _last_hint))
        for preset in presets:
            options.append((preset[:60], "пресет", preset))
        options.append(("Своя подсказка…", "ввести текст", None))

        def on_done(index):
            if index < 0:
                return
            _, _, hint = options[index]
            if hint is None:
                window.show_input_panel(
                    "О чём текст (и как переводить спорные слова):",
                    _last_hint,
                    self._apply,
                    None,
                    None,
                )
                return
            self._apply(hint)

        window.show_quick_panel([[a, b] for a, b, _ in options], on_done)

    def _apply(self, hint):
        global _last_hint
        _last_hint = hint.strip()
        self.view.run_command("lingua_translate", {"hint": _last_hint})


def plugin_loaded():
    """Warm the model so the first lookup does not pay the cold-load cost."""
    def warm():
        if not _settings().get("warm_up_on_start", True):
            return
        _, client = _make_translator()
        client.warm_up()

    # Settings are not available the instant the plugin loads.
    sublime.set_timeout(lambda: threading.Thread(target=warm, daemon=True).start(), 500)

