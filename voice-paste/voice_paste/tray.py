"""System tray icon for voice-paste (v0.4).

Install tray extra:  uv sync --extra tray
Run:                 uv run voice-paste-tray

On Wayland: needs XWayland or AppIndicator3
  sudo apt install gir1.2-appindicator3-0.1
"""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Callable

try:
    import pystray
    from PIL import Image, ImageDraw
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

from voice_paste import clipboard, hotkey as hotkey_mod, notify, recorder
from voice_paste.config import Config, default_config_path, load_config
from voice_paste.transcriber import create_transcriber

LANGUAGES = ["auto", "en", "ru"]
BACKENDS = ["whisperx", "docker", "openai"]

_STATE_COLOURS: dict[str, tuple[int, int, int]] = {
    "idle": (80, 200, 80),
    "recording": (220, 50, 50),
    "transcribing": (220, 140, 0),
}


class TrayApp:
    def __init__(self) -> None:
        self._cfg: Config = load_config()
        self.state: str = "idle"
        self.last_text: str = ""
        self.last_wav: Path | None = None
        self._on_state_change: Callable[[str], None] | None = None
        self._icon = None
        self._stop_event = threading.Event()

    # ── icon ------------------------------------------------------------------

    def _make_icon(self, state: str) -> "Image.Image":
        from PIL import Image, ImageDraw

        colour = _STATE_COLOURS.get(state, (128, 128, 128))
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill=colour + (255,))
        return img

    # ── config ----------------------------------------------------------------

    def _save_cfg(self) -> None:
        path = default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "[general]\n"
            f'language = "{self._cfg.language}"\n'
            f'target = "{self._cfg.target}"\n'
            f"duration = {self._cfg.duration}\n"
            f"auto_paste = {str(self._cfg.auto_paste).lower()}\n"
            "\n[transcription]\n"
            f'backend = "{self._cfg.transcription.backend}"\n'
            f'model = "{self._cfg.transcription.model}"\n'
            f'device = "{self._cfg.transcription.device}"\n'
            f'compute_type = "{self._cfg.transcription.compute_type}"\n'
            f'vad_method = "{self._cfg.transcription.vad_method}"\n'
        )
        path.write_text(content)

    def set_language(self, lang: str) -> None:
        self._cfg.language = lang
        self._save_cfg()

    def set_backend(self, backend: str) -> None:
        self._cfg.transcription.backend = backend
        self._save_cfg()

    # ── clipboard actions -----------------------------------------------------

    def copy_again(self) -> None:
        if not self.last_text:
            return
        clipboard.copy(self.last_text)

    def retry(self) -> None:
        if self.last_wav is None:
            return
        self._transcribe_wav(self.last_wav)

    # ── recording pipeline ----------------------------------------------------

    def _set_state(self, state: str) -> None:
        self.state = state
        if self._on_state_change is not None:
            self._on_state_change(state)
        if self._icon is not None:
            try:
                self._icon.icon = self._make_icon(state)
                self._icon.update_menu()
            except Exception:
                pass

    def _transcribe_wav(self, wav_path: Path) -> None:
        self._set_state("transcribing")
        try:
            cfg = self._cfg
            t = create_transcriber(
                cfg.transcription.backend,
                cfg.transcription.model,
                cfg.transcription.device,
                cfg.transcription.compute_type,
                cfg.transcription.vad_method,
            )
            lang = cfg.language if cfg.language != "auto" else None
            text = t.transcribe(wav_path, lang)
            self.last_text = text
            clipboard.copy(text)
            preview = text[:60] + ("…" if len(text) > 60 else "")
            notify.notify(f'Copied: "{preview}"', "voice-paste")
        finally:
            self._set_state("idle")

    def _do_record(
        self,
        duration: int | None = None,
        language: str | None = None,
        wav_path: Path | None = None,
    ) -> None:
        if duration is None:
            duration = self._cfg.duration
        if language is None:
            language = self._cfg.language

        owned_tmp = False
        if wav_path is None:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                wav_path = Path(f.name)
            owned_tmp = True

        self._stop_event.clear()
        self._set_state("recording")
        stream = recorder.RecordingStream(wav_path)
        try:
            stream.start()
            self._stop_event.wait(timeout=duration)
        except Exception as exc:
            notify.notify(f"Recording failed: {exc}", "voice-paste")
            self._set_state("idle")
            return
        finally:
            stream.stop()

        self.last_wav = wav_path
        self._transcribe_wav(wav_path)

        if owned_tmp:
            wav_path.unlink(missing_ok=True)

    def toggle_record(self) -> None:
        if self.state == "idle":
            threading.Thread(target=self._do_record, daemon=True).start()
        elif self.state == "recording":
            self._stop_event.set()

    def _record_in_thread(self) -> None:
        if self.state != "idle":
            return
        threading.Thread(target=self._do_record, daemon=True).start()

    # ── tray menu -------------------------------------------------------------

    def _build_menu(self) -> "pystray.Menu":
        import pystray as _pystray

        def lang_item(lang: str) -> "_pystray.MenuItem":
            def on_click(icon, item):
                self.set_language(lang)

            return _pystray.MenuItem(
                lang,
                on_click,
                checked=lambda item: self._cfg.language == lang,
                radio=True,
            )

        def backend_item(b: str) -> "_pystray.MenuItem":
            def on_click(icon, item):
                self.set_backend(b)

            return _pystray.MenuItem(
                b,
                on_click,
                checked=lambda item: self._cfg.transcription.backend == b,
                radio=True,
            )

        def hotkey_label(item: object) -> str:
            try:
                b = hotkey_mod.current_binding()
                return f"Hotkey: {b}" if b else "Hotkey: not set"
            except Exception:
                return "Hotkey: unavailable"

        def last_text_label(item: object) -> str:
            if self.last_text:
                preview = self.last_text[:40] + ("…" if len(self.last_text) > 40 else "")
                return f'Last: "{preview}"'
            return "Last: —"

        def record_label(item: object) -> str:
            return "Stop" if self.state == "recording" else "Record"

        return _pystray.Menu(
            _pystray.MenuItem(record_label, lambda icon, item: self.toggle_record()),
            _pystray.Menu.SEPARATOR,
            _pystray.MenuItem(
                "Language",
                _pystray.Menu(*[lang_item(l) for l in LANGUAGES]),
            ),
            _pystray.MenuItem(
                "Backend",
                _pystray.Menu(*[backend_item(b) for b in BACKENDS]),
            ),
            _pystray.Menu.SEPARATOR,
            _pystray.MenuItem(hotkey_label, None, enabled=False),
            _pystray.Menu.SEPARATOR,
            _pystray.MenuItem(last_text_label, None, enabled=False),
            _pystray.MenuItem("Copy Again", lambda icon, item: self.copy_again()),
            _pystray.MenuItem("Retry", lambda icon, item: self.retry()),
            _pystray.Menu.SEPARATOR,
            _pystray.MenuItem("Quit", lambda icon, item: icon.stop()),
        )

    # ── run ------------------------------------------------------------------

    def run(self) -> None:
        if not _HAS_TRAY:
            raise RuntimeError(
                "pystray / pillow not installed.\n"
                "Install tray extra:  uv sync --extra tray"
            )
        import pystray as _pystray

        self._icon = _pystray.Icon(
            "voice-paste",
            self._make_icon("idle"),
            "voice-paste",
            menu=self._build_menu(),
        )
        self._icon.run()


def main() -> None:
    TrayApp().run()
