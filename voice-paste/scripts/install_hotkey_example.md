# GNOME hotkey setup for voice-paste

## Push-to-talk (v0.2 — recommended)

1. Open **Settings**
2. Go to **Keyboard → Keyboard Shortcuts → View and Customize Shortcuts → Custom Shortcuts**
3. Click **+** and add the following two shortcuts:

### Start recording

- **Name:** Voice Paste: Start
- **Command:** `voice-paste start --language auto --target clipboard`
- **Shortcut:** `Ctrl+Alt+Space`

### Stop recording

- **Name:** Voice Paste: Stop
- **Command:** `voice-paste stop`
- **Shortcut:** `Ctrl+Alt+X`  *(or bind to the same key as start — the daemon checks state)*

**How it works:** Press `Ctrl+Alt+Space` → speak → press `Ctrl+Alt+X` → text appears in clipboard → paste with `Ctrl+V`.

---

## Fixed-duration (v0.1 — simpler)

| Name | Command | Shortcut |
|------|---------|----------|
| Voice Paste (auto) | `voice-paste record --duration 15 --target clipboard` | `Ctrl+Alt+Space` |
| Voice Paste (Russian) | `voice-paste record --duration 15 --language ru` | `Ctrl+Alt+R` |
| Voice Paste (terminal) | `voice-paste record --duration 15 --target terminal` | `Ctrl+Alt+T` |

---

## Verify the shortcut works

After binding, open a terminal and run:

```bash
voice-paste test-mic
```

If you see `✅ Microphone OK`, the audio stack is working.

Then try a full cycle:

```bash
voice-paste record --duration 5 --language ru
```

Say: *"Привет, это тестовая диктовка."*

Expected output:
```
🎙  Recording for 5 seconds...
🧠  Transcribing...
✅  Copied to clipboard:
"Привет, это тестовая диктовка."
```

Paste into any app with `Ctrl+V`.
