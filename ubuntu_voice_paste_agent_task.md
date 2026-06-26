# Ubuntu Voice Paste Agent Task

## Goal

Build a small Ubuntu utility called `voice-paste` that records speech from the microphone when triggered, transcribes it, copies the recognized text to the clipboard, and optionally pastes it into the active application or terminal.

The primary target environment is Ubuntu Desktop on GNOME/Wayland. The first version must be reliable and safe, even if that means clipboard-only behavior by default.

## User story

As a user on Ubuntu, I want to press a hotkey, dictate a short phrase or command, have it transcribed, and then paste it into a terminal, ChatGPT, messenger, browser, or editor without manually typing.

Typical use cases:

- Dictate text into ChatGPT in a browser.
- Dictate short messages into Telegram/WhatsApp/Slack.
- Dictate terminal commands or explanations, but never auto-execute them.
- Use a normal USB webcam microphone or USB microphone as the audio input.

## Important safety rule

Never press Enter automatically.

Even in terminal mode, the app must only paste text. It must not execute commands. This is critical because speech recognition can produce dangerous or incorrect commands.

## Platform assumptions

- OS: Ubuntu Desktop, modern GNOME, likely Wayland.
- Audio stack: PipeWire / PulseAudio compatibility.
- Clipboard: Wayland clipboard preferred.
- Terminal paste shortcut: `Ctrl+Shift+V`.
- Browser/chat/editor paste shortcut: `Ctrl+V`.
- Primary language: Russian and English. The app should support `ru`, `en`, and `auto` if the selected transcription backend supports it.

## MVP scope

Implement version 0.1 as a command-line utility with this flow:

```text
Start command or hotkey
→ record audio
→ stop recording
→ transcribe audio
→ copy text to clipboard
→ show desktop notification
```

Default behavior must be clipboard-only. Auto-paste is optional and must be disabled by default.

## Non-goals for v0.1

Do not build a full GUI in the first version.

Do not implement automatic command execution.

Do not require root access.

Do not rely on X11-only tools as the only path, because the target system may run Wayland.

## Preferred implementation stack

Use Python.

Recommended project layout:

```text
voice-paste/
  pyproject.toml
  README.md
  voice_paste/
    __init__.py
    cli.py
    config.py
    recorder.py
    transcriber.py
    clipboard.py
    paste.py
    notify.py
    postprocess.py
  scripts/
    install_hotkey_example.md
```

Use `uv` for dependency management if possible.

## CLI design

The app should expose a command named:

```bash
voice-paste
```

Suggested commands:

```bash
voice-paste record
voice-paste record --duration 15
voice-paste record --language ru
voice-paste record --language en
voice-paste record --language auto
voice-paste record --target clipboard
voice-paste record --target terminal
voice-paste record --target active
voice-paste devices
voice-paste test-mic
voice-paste config-path
```

Default command behavior:

```bash
voice-paste record --duration 15 --language auto --target clipboard
```

If no duration is provided, a simple duration-based recording is acceptable for v0.1. Push-to-talk can be added later.

## Recording options

Prefer using system tools first because they are reliable on Ubuntu:

- `pw-record` if available.
- Fallback to `parecord` if available.
- Fallback to Python `sounddevice` only if system tools are unavailable.

For v0.1, recording to a temporary WAV file is fine.

Example internal command:

```bash
pw-record --duration 15 /tmp/voice-paste-XXXX.wav
```

If `pw-record` does not support `--duration` on the user's system, implement process start + sleep + terminate.

The app should detect missing dependencies and print clear installation instructions.

## Transcription backends

Implement a simple backend interface:

```python
class Transcriber:
    def transcribe(self, audio_path: Path, language: str | None) -> str:
        ...
```

Support at least one backend in v0.1.

Preferred backends:

### Option A: OpenAI API backend

Pros:
- Simple to implement.
- Good accuracy.
- Works well for Russian and English.

Requirements:
- Use environment variable `OPENAI_API_KEY`.
- Do not hardcode credentials.
- Fail gracefully if the variable is missing.

Suggested config key:

```toml
transcriber = "openai"
```

### Option B: local faster-whisper backend

Pros:
- Local/offline.
- Good for privacy.
- Can use GPU on a machine with NVIDIA.

Cons:
- More setup.
- Larger dependencies.

Suggested config key:

```toml
transcriber = "faster-whisper"
model = "small"
device = "auto"
compute_type = "auto"
```

For v0.1, one backend is enough, but design the code so another backend can be added later.

## Clipboard behavior

On Wayland, prefer `wl-copy`.

On X11, use `xclip` or `xsel`.

Implementation should:

1. Detect session type through `XDG_SESSION_TYPE`.
2. Use `wl-copy` if `XDG_SESSION_TYPE=wayland`.
3. Use `xclip` or `xsel` on X11.
4. If no clipboard tool exists, print installation instructions.

Example install commands:

```bash
sudo apt update
sudo apt install wl-clipboard libnotify-bin pipewire-bin
```

For X11 fallback:

```bash
sudo apt install xclip xdotool
```

## Notification behavior

Use `notify-send` if available.

Examples:

```text
Recording...
Transcribing...
Copied to clipboard
Transcription failed
```

If notifications are unavailable, print to stdout.

## Paste behavior

Default target: `clipboard`.

Supported targets:

### `clipboard`

Only copy text to clipboard and notify the user. This is the safest default.

### `terminal`

Copy text to clipboard and optionally send `Ctrl+Shift+V`.

This mode must never send Enter.

On Wayland, auto-paste may be unavailable unless a safe supported tool is configured. If auto-paste is not available, fall back to clipboard-only and notify the user.

### `active`

Copy text to clipboard and optionally send `Ctrl+V`.

Same Wayland caveat.

## Wayland caveat

GNOME/Wayland intentionally restricts programs from injecting keystrokes into other apps. Do not fight this aggressively in v0.1.

The recommended v0.1 behavior is:

```text
Copy to clipboard → show notification → user manually presses paste shortcut
```

Auto-paste can be a later optional feature using tools such as `ydotool`, but this may require additional setup and permissions.

## Post-processing

Implement a small post-processing step before copying text:

- Trim whitespace.
- Collapse excessive blank lines.
- Remove accidental trailing punctuation only if clearly safe.
- Do not alter shell commands aggressively.
- Do not append Enter/newline automatically.

For terminal mode:

- Prefer single-line output by default.
- Replace newlines with spaces unless the user passes `--multiline`.

For chat/browser mode:

- Preserve punctuation and natural text.

## Configuration

Create a config file at:

```text
~/.config/voice-paste/config.toml
```

Example:

```toml
[general]
language = "auto"
target = "clipboard"
duration = 15
auto_paste = false

[audio]
device = "default"
sample_rate = 16000

[transcription]
backend = "openai"
model = "gpt-4o-mini-transcribe"

[postprocess]
terminal_single_line = true
```

The app should work without a config file by using sane defaults.

## Suggested dependencies

Python dependencies:

```toml
typer
rich
pydantic
tomli-w
```

Optional, depending on backend:

```toml
openai
faster-whisper
sounddevice
soundfile
```

System dependencies:

```bash
sudo apt update
sudo apt install wl-clipboard libnotify-bin pipewire-bin
```

Optional:

```bash
sudo apt install xclip xdotool
```

## Hotkey integration

The app itself does not need to register a global hotkey in v0.1.

Instead, document how to add a GNOME custom shortcut:

1. Open Settings.
2. Keyboard.
3. View and Customize Shortcuts.
4. Custom Shortcuts.
5. Add new shortcut.
6. Name: `Voice Paste`.
7. Command:

```bash
voice-paste record --duration 15 --target clipboard
```

8. Shortcut example:

```text
Ctrl+Alt+Space
```

Terminal-specific shortcut command:

```bash
voice-paste record --duration 15 --target terminal
```

But for v0.1, terminal target may still behave as clipboard-only on Wayland.

## Acceptance criteria for v0.1

The implementation is done when:

- `voice-paste record --duration 10` records audio from the default microphone.
- The audio is transcribed.
- The resulting text is copied to the clipboard.
- A desktop notification says the text was copied.
- The utility does not press Enter.
- The utility handles missing dependencies with clear error messages.
- The README explains how to install, configure, and bind a GNOME hotkey.
- The app runs on Ubuntu GNOME/Wayland without requiring root.

## Manual test plan

### Test microphone detection

```bash
voice-paste devices
voice-paste test-mic
```

Expected result: the app lists or confirms the default input device.

### Test transcription

```bash
voice-paste record --duration 5 --language ru
```

Say:

```text
Привет, это тестовая диктовка.
```

Expected result: the text appears in clipboard.

### Test browser/chat usage

Run:

```bash
voice-paste record --duration 5 --target clipboard
```

Then paste manually into a browser text field with `Ctrl+V`.

Expected result: text is pasted.

### Test terminal usage

Run:

```bash
voice-paste record --duration 5 --target clipboard
```

Then paste manually into terminal with `Ctrl+Shift+V`.

Expected result: text is inserted but not executed.

### Safety test

Dictate:

```text
rm dash rf slash tmp slash test
```

Expected result: the app must not press Enter and must not execute anything.

## Future version 0.2

Add push-to-talk behavior:

```text
press hotkey once → start recording
press hotkey again → stop recording and transcribe
```

Possible approaches:

- Background daemon with tray icon.
- DBus command interface.
- Simple local socket.
- GNOME extension later, if needed.

## Future version 0.3

Add optional auto-paste:

- `--auto-paste`
- `--target terminal`
- `--target active`

Rules:

- Never auto-press Enter.
- On Wayland, only enable if a supported tool is installed and configured.
- If auto-paste fails, silently fall back to clipboard and notify.

## Future version 0.4

Add a minimal tray/GUI:

- Recording indicator.
- Backend selector.
- Language selector.
- Microphone selector.
- Last transcription preview.
- Retry button.
- Copy again button.

## Coding instructions for the agent

Start by creating a minimal but working version.

Do not over-engineer.

Use small modules with clear boundaries:

- `recorder.py`: capture audio to a temp WAV.
- `transcriber.py`: convert audio file to text.
- `clipboard.py`: copy text.
- `notify.py`: desktop notifications.
- `postprocess.py`: clean transcription text.
- `cli.py`: Typer CLI and orchestration.

Write robust subprocess wrappers with:

- clear stderr messages,
- timeouts where appropriate,
- dependency checks,
- no shell=True unless absolutely necessary.

Include a README with:

- Ubuntu install commands,
- Python install commands,
- OpenAI API key setup if using OpenAI backend,
- GNOME hotkey setup,
- Wayland limitations,
- safety notes.

## Suggested first implementation path

1. Create the project structure.
2. Implement `voice-paste record --duration N`.
3. Use `pw-record` to record a temporary WAV file.
4. Implement one transcription backend.
5. Copy result with `wl-copy`.
6. Notify with `notify-send`.
7. Add README.
8. Add basic error handling.
9. Add a simple config file reader only after the core flow works.

## Example desired user experience

```bash
$ voice-paste record --duration 7 --language ru
🎙 Recording for 7 seconds...
🧠 Transcribing...
✅ Copied to clipboard:
"Привет, это тестовая диктовка."
```

Then the user pastes manually into the terminal or browser.

## Final reminder

Reliability beats cleverness.

For v0.1, clipboard-only on Wayland is a perfectly acceptable result. Auto-paste can come later.
