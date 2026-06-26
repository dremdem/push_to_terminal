# voice-paste

Ubuntu voice-to-clipboard utility for GNOME/Wayland.

Press a hotkey → dictate → text lands in clipboard → paste manually with `Ctrl+V` or `Ctrl+Shift+V`.

**Never auto-executes commands.** Clipboard-only is the safe default.

## Quick start

### 1. System dependencies

```bash
sudo apt update
sudo apt install wl-clipboard libnotify-bin pipewire-bin
# X11 fallback (optional):
sudo apt install xclip xdotool
```

### 2. Python install

```bash
# Requires Python 3.10+. Uses uv (https://docs.astral.sh/uv/).
uv tool install git+https://github.com/dremdem/push_to_terminal#subdirectory=voice-paste
```

Or from a local clone:

```bash
cd voice-paste
uv sync
uv run voice-paste --help
```

### 3. Install whisperx (local transcription, GPU-accelerated)

```bash
# PyTorch with CUDA (for NVIDIA GPU — replace cu121 with your CUDA version):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# whisperx:
pip install whisperx
```

No API key required. The model is downloaded automatically on first use (~150 MB for `base`).

**Optional: OpenAI fallback** (cloud, requires key):
```bash
pip install openai
export OPENAI_API_KEY=sk-...
```

---

## Usage

### Fixed-duration recording (v0.1)

```bash
voice-paste record                          # 15s, auto-detect language
voice-paste record --duration 10            # 10s
voice-paste record --language ru            # Russian
voice-paste record --language en            # English
voice-paste record --target terminal        # single-line output for terminal paste
```

Then paste with `Ctrl+V` (browser/chat) or `Ctrl+Shift+V` (terminal).

### Push-to-talk (v0.2)

```bash
voice-paste start                           # begin recording
# … speak …
voice-paste stop                            # stop, transcribe, copy to clipboard
```

Bind these to two hotkeys in GNOME (see below).

### Utility commands

```bash
voice-paste devices        # list audio input devices
voice-paste test-mic       # record 3s and confirm audio is captured
voice-paste config-path    # print config file path
```

---

## Configuration

The config file lives at `~/.config/voice-paste/config.toml`.  
The app works without it (sensible defaults apply).

```toml
[general]
language = "auto"      # "auto", "ru", or "en"
target   = "clipboard" # "clipboard", "terminal", or "active"
duration = 15
auto_paste = false     # never auto-paste in v0.2 (see v0.3 roadmap)

[audio]
device      = "default"
sample_rate = 16000

[transcription]
backend      = "whisperx"  # "whisperx" (default) or "openai"
model        = "base"      # tiny / base / small / medium / large-v3
device       = "auto"      # auto / cuda / cpu
compute_type = "auto"      # auto → float16 on GPU, int8 on CPU

[postprocess]
terminal_single_line = true
```

---

## GNOME hotkey setup

### Push-to-talk (recommended)

Open **Settings → Keyboard → Keyboard Shortcuts → View and Customize Shortcuts → Custom Shortcuts** and add two shortcuts:

| Name | Command | Suggested key |
|------|---------|---------------|
| Voice Paste: Start | `voice-paste start --language auto` | `Ctrl+Alt+Space` |
| Voice Paste: Stop  | `voice-paste stop` | `Ctrl+Alt+Space` (or a second key) |

> **Tip:** If you bind both start and stop to the same key, the second press will reach the `stop` command because `start` checks whether the daemon is already running.

### Fixed-duration (simpler)

| Name | Command | Suggested key |
|------|---------|---------------|
| Voice Paste | `voice-paste record --duration 15 --target clipboard` | `Ctrl+Alt+Space` |
| Voice Paste (terminal) | `voice-paste record --duration 15 --target terminal` | `Ctrl+Alt+T` |

---

## Wayland limitations

GNOME/Wayland intentionally prevents apps from injecting keystrokes into other windows.  
`voice-paste` respects this: it **only** copies text to the clipboard. The user presses paste manually.

Auto-paste (`--auto-paste` via `ydotool`) is planned for v0.3 and requires extra system permissions.

---

## Safety

- Text is **never** sent to the shell or auto-executed.
- Enter/Return is **never** injected, even for terminal targets.
- The transcribed text goes to the clipboard. You paste it; you decide if you run it.

---

## Roadmap

| Version | Feature |
|---------|---------|
| v0.1 | Fixed-duration recording, OpenAI transcription, clipboard copy ([#1](https://github.com/dremdem/push_to_terminal/issues/1)) |
| **v0.2** | **Push-to-talk via Unix socket daemon (this release)** ([#2](https://github.com/dremdem/push_to_terminal/issues/2)) |
| v0.3 | Optional auto-paste with `ydotool` ([#3](https://github.com/dremdem/push_to_terminal/issues/3)) |
| v0.4 | System-tray GUI ([#4](https://github.com/dremdem/push_to_terminal/issues/4)) |

---

## Development

```bash
uv sync --group dev
uv run pytest -v
```

Tests are written first (TDD). All modules are independently testable with mocked subprocesses.
