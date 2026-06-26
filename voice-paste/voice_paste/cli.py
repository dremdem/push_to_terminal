"""voice-paste CLI — Ubuntu voice-to-clipboard utility."""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from voice_paste import clipboard, daemon, notify, paste as paste_mod, postprocess, recorder
from voice_paste import transcriber as trans_mod
from voice_paste.config import load_config

app = typer.Typer(help="Ubuntu voice-to-clipboard utility (Wayland-safe).")
console = Console()


@app.command()
def record(
    duration: int = typer.Option(15, "--duration", "-d", help="Recording duration in seconds"),
    language: str = typer.Option("auto", "--language", "-l", help="Language: auto, ru, en"),
    target: str = typer.Option("clipboard", "--target", "-t", help="Target: clipboard, terminal, active"),
    auto_paste: Optional[bool] = typer.Option(None, "--auto-paste/--no-auto-paste", help="Inject paste keystroke after copy"),
) -> None:
    """Record for a fixed duration, transcribe, and copy to clipboard."""
    cfg = load_config()
    cfg.language = language  # type: ignore[assignment]
    cfg.target = target  # type: ignore[assignment]
    do_paste = cfg.auto_paste if auto_paste is None else auto_paste

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = Path(f.name)

    console.print(f"[bold]🎙  Recording for {duration} seconds...[/bold]")
    notify.notify(f"Recording for {duration}s...", "voice-paste")

    try:
        recorder.record_fixed(wav_path, duration)

        console.print("[bold]🧠  Transcribing...[/bold]")
        notify.notify("Transcribing...", "voice-paste")

        t = trans_mod.create_transcriber(
            cfg.transcription.backend,
            cfg.transcription.model,
            cfg.transcription.device,
            cfg.transcription.compute_type,
            cfg.transcription.vad_method,
        )
        lang = cfg.language if cfg.language != "auto" else None
        text = t.transcribe(wav_path, lang)
        text = postprocess.process(text, terminal_mode=(target == "terminal"))

        clipboard.copy(text)
        console.print(f'[green]✅  Copied to clipboard:[/green]\n"{text}"')
        notify.notify(f'Copied: "{text[:60]}"', "voice-paste")

        if do_paste:
            try:
                paste_mod.paste(target)
            except paste_mod.PasteError as exc:
                console.print(f"[yellow]⚠   Auto-paste unavailable (clipboard fallback):[/yellow] {exc}")
                notify.notify("Auto-paste unavailable — text copied to clipboard.", "voice-paste")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    finally:
        wav_path.unlink(missing_ok=True)


@app.command()
def start(
    language: str = typer.Option("auto", "--language", "-l", help="Language: auto, ru, en"),
    target: str = typer.Option("clipboard", "--target", "-t", help="Target: clipboard, terminal, active"),
    auto_paste: Optional[bool] = typer.Option(None, "--auto-paste/--no-auto-paste", help="Inject paste keystroke after copy"),
) -> None:
    """Start push-to-talk recording. Run 'voice-paste stop' to finish."""
    if daemon.is_running():
        console.print("[red]Already recording. Run 'voice-paste stop' to finish.[/red]")
        raise typer.Exit(1)

    cfg = load_config()
    do_paste = cfg.auto_paste if auto_paste is None else auto_paste
    daemon.spawn(language=language, target=target, auto_paste=do_paste)

    for _ in range(20):
        time.sleep(0.1)
        if daemon.is_running():
            console.print("[green]🎙  Recording started. Run 'voice-paste stop' when done.[/green]")
            return

    console.print("[red]Daemon did not start. Check that pw-record is installed.[/red]")
    raise typer.Exit(1)


@app.command()
def toggle() -> None:
    """Start recording if idle, stop if already recording."""
    if daemon.is_running():
        daemon.send_stop()
        console.print("[green]⏹  Stopped. Transcription in progress...[/green]")
    else:
        cfg = load_config()
        daemon.spawn(language=cfg.language, target=cfg.target, auto_paste=cfg.auto_paste)
        for _ in range(20):
            time.sleep(0.1)
            if daemon.is_running():
                console.print("[green]🎙  Recording started.[/green]")
                return
        console.print("[red]Daemon did not start.[/red]")
        raise typer.Exit(1)


@app.command()
def stop() -> None:
    """Stop push-to-talk recording and transcribe."""
    if not daemon.is_running():
        console.print("[red]No recording in progress.[/red]")
        raise typer.Exit(1)

    daemon.send_stop()
    console.print("[green]⏹  Stopped. Transcription in progress...[/green]")


@app.command()
def devices() -> None:
    """List available audio input devices."""
    for cmd in (["pw-record", "--list-targets"], ["pactl", "list", "sources", "short"]):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(result.stdout)
            return
    console.print("[yellow]Could not list devices. Install pipewire-bin or pulseaudio-utils.[/yellow]")
    raise typer.Exit(1)


@app.command("test-mic")
def test_mic(
    duration: int = typer.Option(3, "--duration", "-d", help="Recording duration in seconds"),
) -> None:
    """Record a short clip and confirm audio is detected."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = Path(f.name)
    try:
        console.print(f"[bold]Recording {duration}s test clip...[/bold]")
        recorder.record_fixed(wav_path, duration)
        size = wav_path.stat().st_size
        if size > 44:  # WAV header alone is 44 bytes
            console.print(f"[green]✅  Microphone OK — {size} bytes recorded[/green]")
        else:
            console.print("[yellow]⚠   No audio data detected — check your microphone[/yellow]")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    finally:
        wav_path.unlink(missing_ok=True)


@app.command("config-path")
def config_path() -> None:
    """Print the path to the config file."""
    from voice_paste.config import default_config_path

    console.print(str(default_config_path()))


hotkey_app = typer.Typer(help="Manage the global GNOME keyboard shortcut.")
app.add_typer(hotkey_app, name="hotkey")


@hotkey_app.command("set")
def hotkey_set(
    binding: str = typer.Argument(..., help="Binding, e.g. ctrl+alt+space"),
    command: str = typer.Option("start", "--command", "-c", help="'start' (push-to-talk) or 'record' (fixed)"),
) -> None:
    """Register a global GNOME keyboard shortcut for voice-paste."""
    import sys
    from voice_paste import hotkey as hk

    # Use the absolute path to this binary so GNOME can find it outside the venv.
    exe = Path(sys.argv[0]).resolve()
    cmd = f"{exe} {command}"
    hk.register(binding, cmd)
    gnome_fmt = hk.binding_to_gnome(binding)
    console.print(f"[green]✅  Hotkey registered:[/green] {gnome_fmt} → {cmd}")
    console.print("Visible in GNOME Settings → Keyboard → Custom Shortcuts.")


@hotkey_app.command("unset")
def hotkey_unset() -> None:
    """Remove the voice-paste GNOME keyboard shortcut."""
    from voice_paste import hotkey as hk

    hk.unregister()
    console.print("[green]✅  Hotkey removed.[/green]")


@hotkey_app.command("show")
def hotkey_show() -> None:
    """Show the currently registered hotkey, if any."""
    from voice_paste import hotkey as hk

    binding = hk.current_binding()
    if binding:
        console.print(f"[green]Hotkey:[/green] {binding}")
    else:
        console.print("[yellow]No hotkey registered.[/yellow]")
        console.print("Run: voice-paste hotkey set ctrl+alt+space")


@app.command("_daemon", hidden=True)
def daemon_cmd(
    language: str = typer.Option("auto", "--language"),
    target: str = typer.Option("clipboard", "--target"),
    auto_paste: bool = typer.Option(False, "--auto-paste/--no-auto-paste"),
) -> None:
    """Internal: run the push-to-talk daemon process."""
    cfg = load_config()
    cfg.language = language  # type: ignore[assignment]
    cfg.target = target  # type: ignore[assignment]
    cfg.auto_paste = auto_paste
    daemon.run(cfg)
