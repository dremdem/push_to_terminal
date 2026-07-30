# push_to_terminal

**Talk to your terminal.** A push-to-talk dictation tool for Ubuntu/GNOME — press a hotkey, speak, and your words land where your cursor is.

```
🎤  Ctrl+Alt+Shift+P  →  "run the test suite and show me what fails"  →  📋  → terminal
```

---

## Why

Working with AI agents in a terminal turns a conversation into a typing contest. The model answers in seconds; replying takes far longer than thinking of the reply. Across several parallel sessions, the bottleneck stops being the model and starts being the keyboard.

`push_to_terminal` removes that. Speak instead of typing, keep your hands free for the parts that actually need precision, and stay in flow across as many terminal sessions as you like.

It is deliberately **not** a voice assistant. It does not interpret, execute, or act. It transcribes and hands you the text.

## Safety first

Speech recognition misfires. A misheard `rm -rf` should never become a running command, so the design rules out that failure mode entirely:

- **Enter is never injected** — not even in terminal mode.
- **Nothing is ever auto-executed.** Text goes to the clipboard; you decide what runs.
- Clipboard-only is the safe default, and auto-paste degrades back to it when unavailable.

## How it works

```
hotkey → pw-record → whisperx → post-process → clipboard → (optional) paste keystroke
```

Recording runs as a detached daemon coordinated over a Unix socket, so push-to-talk can start and stop from independent hotkey presses. Transcription is pluggable:

| Backend | Runs on | Notes |
|---|---|---|
| `docker` | Your GPU, in a container | Fastest. Model stays warm between calls. |
| `whisperx` | Your CPU, locally | No container needed. ~100× real-time for `base`. |
| `openai` | Cloud | Optional fallback; needs an API key. |

The two local backends keep your audio on your own machine.

## Quick start

```bash
git clone https://github.com/dremdem/push_to_terminal
cd push_to_terminal/voice-paste
./install.sh

# Bind a hotkey:
uv run voice-paste hotkey set ctrl+alt+shift+p
```

Then press the hotkey, speak, press it again. There is also a system-tray icon (green = idle, red = recording, amber = transcribing) with language and backend switchers.

```bash
voice-paste record --duration 10     # fixed-length recording
voice-paste toggle                   # push-to-talk start/stop
voice-paste test-mic                 # confirm audio is being captured
```

**📖 Full documentation — install, configuration, hotkeys, GPU setup, troubleshooting — lives in [`voice-paste/README.md`](voice-paste/README.md).**

## Repo layout

| Path | What's in it |
|---|---|
| [`voice-paste/`](voice-paste/) | The application, its tests, and the complete docs |
| [`voice-paste/voice_paste/`](voice-paste/voice_paste/) | Source: daemon, recorder, transcriber, clipboard, tray, hotkey |
| [`voice-paste/docker/`](voice-paste/docker/) | GPU transcription container |
| [`ubuntu_voice_paste_agent_task.md`](ubuntu_voice_paste_agent_task.md) | Original product spec |
| [`CLAUDE.md`](CLAUDE.md) | Contributor guidelines (TDD, `uv`, branch-per-issue) |

## Requirements

Ubuntu Desktop on GNOME (Wayland or X11), PipeWire, Python 3.10+, and [`uv`](https://docs.astral.sh/uv/). An NVIDIA GPU is optional and only speeds transcription up. English and Russian are supported, with auto-detection.

## Status

Shipped through **v0.8**: fixed-duration and push-to-talk recording, local and GPU transcription, clipboard and auto-paste, system tray, GNOME hotkey binding, reproducible install, and error notifications. 126 tests passing.

```bash
cd voice-paste && uv run pytest -v
```

Development follows TDD — tests are written before the implementation, and every change goes through its own issue, branch, and PR.

## License

[MIT](LICENSE) — use it, fork it, build on it.

---

<sub>A personal project, built on Ubuntu with [Claude Code](https://claude.com/claude-code) — and dictated, increasingly, with itself.</sub>
