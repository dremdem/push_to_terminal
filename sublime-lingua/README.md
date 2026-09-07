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
| From the menu | right-click → *Translate (EN → RU)* |
| From the palette | *Lingua: Translate selection (EN → RU)* |

With nothing selected, the word under the caret is sent **together with its
sentence**. That context is what decides between свинец and возглавить for
`lead`, or берег and банк for `bank` — the word alone cannot.

## Settings

`Preferences → Package Settings → Lingua`, or edit `Lingua.sublime-settings`:

| Setting | Default | Meaning |
|---|---|---|
| `url` | `http://localhost:11434` | Where Ollama listens |
| `model` | `gemma3:4b` | Any model Ollama has pulled |
| `timeout` | `20.0` | Seconds to wait for an answer |
| `keep_alive` | `"30m"` | How long Ollama holds the model in VRAM |
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

## Known gaps

- **Hover mode** is not implemented yet — it needs debouncing and cancellation
  so mouse movement does not flood the model.
- **Dictionary entries** (part of speech, other senses) are not offered. Both
  local models tested gloss an isolated word unreliably; the sentence-level
  translation is the trustworthy part.
- Russian → English is not wired up; the prompt is one-directional.
