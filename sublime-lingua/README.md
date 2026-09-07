# sublime-lingua

**Select English, get Russian.** A Sublime Text 4 plugin that translates the
selection — or the word under the caret — into a popup, using a model that runs
on your own machine.

```
    Recording runs as a detached daemon coordinated over a Unix socket.
            ┌──────────────────────────────────────────────────────┐
  Ctrl+Alt+ │ Запись выполняется как отсоединённый демон,           │
  Shift+T → │ координируемый через Unix socket.                     │
            └──────────────────────────────────────────────────────┘
```

No API key, no account, no network traffic leaving the machine — the same rule
the rest of this repo follows.

## Why a local LLM and not a translation model

The obvious choice is a dedicated MT model. It was measured and rejected.
`Helsinki-NLP/opus-mt-en-ru` is four times faster, but it destroys exactly the
text you want to read in an editor:

| Input | `opus-mt-en-ru` | `gemma3:4b` |
|---|---|---|
| `Unix socket` | розетка Unix | Unix socket |
| `push-to-talk` | толкнуть к разговору | push-to-talk |
| `local backends` | местных прикрытий | локальные бэкенды |
| `Copper wire has a lead core.` | Медная проволока имеет ядро **(свинец потерян)** | Медная проволока имеет сердечник из свинца |

`gemma3:4b` costs ~400 ms per sentence, fits in 8 GB of VRAM alongside
`voice-paste`'s whisper container, and keeps terminology intact.

Full benchmark: [issue #23](https://github.com/dremdem/push_to_terminal/issues/23).

## Requirements

- Sublime Text 4 (build 4200 or newer)
- [Ollama](https://ollama.com) running locally, with the model pulled:

  ```bash
  ollama pull gemma3:4b
  ```

That is the entire dependency list. The plugin itself imports nothing but the
standard library — Sublime has no pip, so it cannot be otherwise.

## Install

Symlink the package into Sublime's `Packages` directory:

```bash
ln -s "$PWD" ~/.config/sublime-text/Packages/Lingua
```

Sublime picks it up immediately. The `.python-version` file opts the package
into Sublime's Python 3.8 plugin host.

## Use

| Action | How |
|---|---|
| Translate the selection | `Ctrl+Alt+Shift+T` |
| Translate the word under the caret | same key, with nothing selected |
| Translate, saying what the text is about | `Ctrl+Alt+Shift+H` |
| From the menu | right-click → *Translate (EN → RU)* |
| From the palette | *Lingua: Translate selection (EN → RU)* |

With nothing selected, the word under the caret is sent **together with its
sentence**. That context is what decides between свинец and возглавить for
`lead`, or берег and банк for `bank` — the word alone cannot.

## Telling it what the text is about

The model has no idea what it is reading. Out of the box it renders this radio
exchange wrong in four places:

```
we got a hit … to your northeast … a more accurate read … our target?
→ у нас ПОПАДАНИЕ … к северо-востоку ОТ ЦЕЛИ … более точную ОЦЕНКУ … Друзья цели?
```

`Ctrl+Alt+Shift+H` lets you say what it is looking at first. What you write
matters more than you would expect:

| Hint | `hit` | `your` | `our` | `read` |
|---|---|---|---|---|
| *(none)* | ✗ | ✗ | ✓ | ✗ |
| `военный радиообмен` — genre only | ✗ | ✓ | ✓ | ✗ |
| **glossing the actual words** | **✓** | **✓** | **✓** | **✓** |

Naming the genre only recovers the dropped pronoun. What repairs the jargon is
spelling out the ambiguous words:

```
военный радиообмен; 'a hit' — засечка сигнала, не попадание снаряда;
'read' — показание/засечка; 'popped' — телефон засветился в сети
```

Set `hint` to apply one to every translation, or keep a few in `hints` to pick
from the quick panel. The hint is part of the cache key, so the same sentence
under two different hints is two different answers.

## Settings

`Preferences → Package Settings → Lingua`, or edit `Lingua.sublime-settings`:

| Setting | Default | Meaning |
|---|---|---|
| `url` | `http://localhost:11434` | Where Ollama listens |
| `model` | `gemma3:4b` | Any model Ollama has pulled |
| `timeout` | `20.0` | Seconds to wait for an answer |
| `keep_alive` | `"30m"` | How long Ollama holds the model in VRAM |
| `hint` | `""` | What the text is about, applied to every translation |
| `hints` | *five presets* | Offered by *Translate with a hint…* |
| `warm_up_on_start` | `true` | Load the model when Sublime starts |
| `cache_path` | `~/.cache/sublime-lingua/cache.sqlite3` | Translation cache |

Translations run at `temperature: 0`, so they are deterministic and cached
forever — a repeated lookup returns in ~0.1 ms instead of ~400 ms. Delete the
cache file to clear it.

## How it is put together

```
lingua.py       Sublime glue: selection, worker thread, popup.  Not unit-tested.
lingua_core.py  Everything else. No `import sublime`, so pytest can reach it.
tests/          42 tests, run on Python 3.8 — the same version as the ST host.
```

The split exists because Sublime's `sublime` module only exists inside Sublime.
Keeping the HTTP client, the prompt, the cache and the HTML rendering on the
other side of that line makes all of it testable.

There is no daemon of our own: Ollama already runs as a service and already
keeps the model warm.

## Development

```bash
cd sublime-lingua
uv sync --group dev
uv run pytest -v
```

`uv` downloads CPython 3.8 for this package (pinned by `.python-version`), so
anything that would fail inside Sublime's plugin host fails in the tests first.

**One rule when editing `lingua.py`: import the module, never its names.**

```python
from . import lingua_core as core     # yes — core.Translator resolves at call time
from .lingua_core import Translator   # no  — pinned to the class captured at import
```

Sublime hot-reloads changed files with `importlib.reload`, which mutates the
existing module object in place. Names bound by `from … import …` keep pointing
at the pre-reload objects, so a reloaded `lingua.py` calling into a stale
`lingua_core` fails with an arity error that disappears on restart and is
invisible to the tests. A test asserts the import style to keep it from coming
back.

## How good is it, really

For technical prose — the corpus it was tuned on — it is dependable.

For fiction it conveys the sense but is not a faithful translation, and no
prompt fixes that: `gemma3:4b` still writes «нашего цели» with the wrong gender,
cyrillicises `Bravo` → «Браво», and occasionally drops a noun. `qwen3:8b` was
measured on the same passage and is no better while being five times slower —
and it does not fit in 8 GB. Read prose translations as a gist, not as text you
would quote.

## Known gaps

- **Hover mode** is not implemented yet — it needs debouncing and cancellation
  so mouse movement does not flood the model.
- **Dictionary entries** (part of speech, other senses) are not offered. Both
  local models tested gloss an isolated word unreliably; the sentence-level
  translation is the trustworthy part.
- **The hint is manual.** Nothing detects the genre of the buffer for you.
- Russian → English is not wired up; the prompt is one-directional.
