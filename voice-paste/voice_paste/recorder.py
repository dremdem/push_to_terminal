import shutil
import subprocess
import time
from pathlib import Path


def find_recorder() -> str:
    for tool in ("pw-record", "parecord"):
        if shutil.which(tool):
            return tool
    try:
        import sounddevice  # noqa: F401
        return "sounddevice"
    except ImportError:
        pass
    raise RuntimeError(
        "No audio recorder found.\n"
        "Install PipeWire tools:  sudo apt install pipewire-bin\n"
        "Or install sounddevice: pip install sounddevice soundfile"
    )


def record_fixed(wav_path: Path, duration: int, device: str = "default") -> None:
    tool = find_recorder()
    if tool == "sounddevice":
        _record_sounddevice(wav_path, duration)
        return
    proc = subprocess.Popen([tool, str(wav_path)], stderr=subprocess.DEVNULL)
    try:
        time.sleep(duration)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


class RecordingStream:
    """Open-ended recording for push-to-talk; call stop() when done."""

    def __init__(self, wav_path: Path) -> None:
        self._path = wav_path
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        tool = find_recorder()
        if tool == "sounddevice":
            raise RuntimeError(
                "Streaming recording requires pw-record or parecord.\n"
                "Install:  sudo apt install pipewire-bin"
            )
        self._proc = subprocess.Popen([tool, str(self._path)], stderr=subprocess.DEVNULL)

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None


def _record_sounddevice(wav_path: Path, duration: int) -> None:
    import sounddevice as sd
    import soundfile as sf

    fs = 16000
    data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="int16")
    sd.wait()
    sf.write(str(wav_path), data, fs)
