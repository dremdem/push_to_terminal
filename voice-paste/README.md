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

### 2. Install with uv (handles everything including CUDA torch)

```bash
# Install uv if not already present:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install:
git clone https://github.com/dremdem/push_to_terminal
cd push_to_terminal/voice-paste
uv sync          # creates .venv, installs whisperx + torch (CUDA) automatically
```

That's it. No `pip install`, no separate torch download step.
`uv sync` reads `pyproject.toml` and pulls `torch+cu124` from the
PyTorch CUDA index automatically.

No API key required. The whisperx model is downloaded on first use (~150 MB for `base`).

### 3. Fix ctranslate2 CUDA library issues (Linux kernel 6.6+ / CUDA 12)

ctranslate2 4.x has two issues on modern Ubuntu / CUDA 12 setups.
Run this **once after every `uv sync`**:

```bash
uv run python scripts/fix_cuda_libs.py
```

Expected output:
```
ctranslate2.libs: .venv/lib/python3.12/site-packages/ctranslate2.libs
  execstack patched: libctranslate2-d3638643.so.4.4.0
  1 file(s) had execstack cleared.
  6 symlink(s) created.

Done. ctranslate2 should now load correctly on CUDA 12 / kernel 6.6+.
```

What it fixes (no system tools required, Python-only):
- **execstack** — ctranslate2 ships with GNU_STACK marked RWE; kernel 6.6+ refuses it.
  Fixed by clearing the execute bit in the ELF header in-place.
- **cuDNN 8 sub-libraries** — ctranslate2 bundles a consolidated cuDNN 8.9.7 (all ops
  in one `.so`) but cuDNN 8's runtime loader still tries to `dlopen` the historical
  split names (`libcudnn_ops_infer.so.8`, etc.).  Simple symlinks deadlock (the library
  re-enters its own glibc init mutex); the fix compiles minimal stub `.so` files via
  `gcc` that list the consolidated lib as a `NEEDED` dep, so `dlsym` resolves all
  cuDNN symbols through the dep chain without re-running any initialization.
  Requires `gcc` (`sudo apt install build-essential`).

**Optional: OpenAI cloud fallback** (needs key):
```bash
uv sync --extra openai
export OPENAI_API_KEY=sk-...
```

### GPU inference via Docker (recommended for NVIDIA GPUs)

The host-installed `ctranslate2 4.4.0` (pinned by `whisperx 3.4.5`) is broken on CUDA 12.4.
The Docker container uses `nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04` + `whisperx 3.8.5`
which has proper cuDNN 8 split libraries — GPU inference works correctly there.

**Prerequisites:** Docker + the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

```bash
# Build and start the container (runs in background, model stays loaded):
cd voice-paste
docker compose up -d

# Switch voice-paste to use the Docker backend:
mkdir -p ~/.config/voice-paste
cat >> ~/.config/voice-paste/config.toml <<'EOF'
[transcription]
backend = "docker"
EOF
```

The container mounts `~/.cache/huggingface` and `~/.cache/torch` so models are shared with the
host and not re-downloaded. The Unix socket is at `~/.local/state/voice-paste/docker-transcribe.sock`.

```bash
# Stop the container:
docker compose down

# View logs:
docker compose logs -f
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
voice-paste record --auto-paste             # copy + auto-inject Ctrl+V (opt-in)
```

Then paste with `Ctrl+V` (browser/chat) or `Ctrl+Shift+V` (terminal).

### System tray (v0.4)

```bash
# System build deps (one-time):
sudo apt install libgirepository-2.0-dev libcairo2-dev gir1.2-appindicator3-0.1

# Install tray extra:
uv sync --extra tray

# Launch:
voice-paste-tray
```

**Icon colours:**

| Colour | State |
|--------|-------|
| Green | Idle — click icon or menu → Record to start |
| Red | Recording |
| Amber | Transcribing |

**Menu items:**

- **Record** — start a fixed-duration recording (uses `duration` from config)
- **Language** — submenu: auto / en / ru (saved to config on change)
- **Backend** — submenu: whisperx / docker / openai (saved to config on change)
- **Last:** … — preview of the most recently transcribed text (read-only)
- **Copy Again** — re-copy the last transcription to clipboard
- **Retry** — re-transcribe the last recorded audio file
- **Quit** — exit the tray app

Config changes made via the menu are written immediately to `~/.config/voice-paste/config.toml`.

---

### Auto-paste (v0.3, opt-in)

By default voice-paste only copies to clipboard — you paste manually.  
Enable auto-paste to have the keystroke injected automatically:

```bash
# One-off:
voice-paste record --auto-paste --target active    # Ctrl+V into focused window
voice-paste record --auto-paste --target terminal  # Ctrl+Shift+V into terminal

# Always-on (config):
# ~/.config/voice-paste/config.toml
auto_paste = true
```

**Requirements:**
- Wayland: install `ydotool` and add yourself to the `ydotool` group:
  ```bash
  sudo apt install ydotool
  sudo usermod -aG ydotool $USER   # re-login required
  sudo systemctl enable --now ydotool
  ```
- X11: install `xdotool` (`sudo apt install xdotool`)

If the tool is missing, voice-paste falls back to clipboard-only and shows a notification. **Enter is never injected.**

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
auto_paste = false     # true → inject Ctrl+V / Ctrl+Shift+V after copy (opt-in)

[audio]
device      = "default"
sample_rate = 16000

[transcription]
backend      = "whisperx"  # "whisperx" (local CPU), "docker" (GPU container), "openai"
model        = "base"      # tiny / base / small / medium / large-v3
device       = "auto"      # auto / cuda / cpu
compute_type = "auto"      # auto → float16 on GPU, int8 on CPU
vad_method   = "silero"    # "silero" (default) or "pyannote"
# pyannote VAD requires cuDNN 8 and is incompatible with modern CUDA 12 / cuDNN 9 setups.

[postprocess]
terminal_single_line = true
```

---

## GNOME hotkey setup

### Automatic (v0.5, recommended)

Register the shortcut in one command — no GUI needed:

```bash
# Push-to-talk on Ctrl+Alt+Space (press to start, press again to stop):
voice-paste hotkey set ctrl+alt+space

# Fixed-duration recording instead:
voice-paste hotkey set ctrl+alt+space --command record

# Check what's registered:
voice-paste hotkey show

# Remove:
voice-paste hotkey unset
```

The shortcut appears immediately in **GNOME Settings → Keyboard → Custom Shortcuts** and the tray menu shows the active binding.

### Manual (alternative)

Open **Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts** and add:

| Name | Command | Suggested key |
|------|---------|---------------|
| Voice Paste: Start | `voice-paste start` | `Ctrl+Alt+Space` |
| Voice Paste: Stop  | `voice-paste stop`  | `Ctrl+Alt+Space` |

> **Tip:** Binding start and stop to the same key works — `start` detects if the daemon is already running and acts as a no-op.

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
| **v0.3** | **Optional auto-paste with `ydotool`/`xdotool` (this release)** ([#3](https://github.com/dremdem/push_to_terminal/issues/3)) |
| v0.4 | System-tray GUI with language/backend selectors ([#4](https://github.com/dremdem/push_to_terminal/issues/4)) |
| **v0.5** | **Hotkey binding via GNOME gsettings (this release)** ([#9](https://github.com/dremdem/push_to_terminal/issues/9)) |

---

## Development

```bash
uv sync --group dev
uv run pytest -v
```

Tests are written first (TDD). All modules are independently testable with mocked subprocesses.
