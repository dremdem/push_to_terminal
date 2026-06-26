"""
Unix socket transcription server for the Docker container.

Protocol (both directions use length-prefixed messages):
  Request:  [4B: header_len][JSON header][4B: wav_len][wav bytes]
  Response: [4B: resp_len][JSON: {"text": "..."} | {"error": "..."}]

The model is loaded once at startup and reused for all requests.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import struct
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

SOCK_PATH = Path(os.environ.get("VP_SOCK", "/run/voice-paste/docker-transcribe.sock"))
MODEL_NAME = os.environ.get("VP_MODEL", "base")
DEVICE = os.environ.get("VP_DEVICE", "cuda")
COMPUTE_TYPE = os.environ.get("VP_COMPUTE_TYPE", "float16")
VAD_METHOD = os.environ.get("VP_VAD_METHOD", "silero")


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed mid-message")
        buf += chunk
    return buf


def _read_message(conn: socket.socket) -> tuple[dict, bytes]:
    hdr_len = struct.unpack(">I", _recv_exact(conn, 4))[0]
    header = json.loads(_recv_exact(conn, hdr_len))
    wav_len = struct.unpack(">I", _recv_exact(conn, 4))[0]
    wav_bytes = _recv_exact(conn, wav_len) if wav_len else b""
    return header, wav_bytes


def _send_response(conn: socket.socket, payload: dict) -> None:
    data = json.dumps(payload).encode()
    conn.sendall(struct.pack(">I", len(data)) + data)


def _load_model():
    import whisperx
    log.info("Loading whisperx model=%s device=%s compute_type=%s vad=%s",
             MODEL_NAME, DEVICE, COMPUTE_TYPE, VAD_METHOD)
    model = whisperx.load_model(
        MODEL_NAME,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        vad_method=VAD_METHOD,
    )
    log.info("Model loaded.")
    return model


def _transcribe(model, wav_bytes: bytes, language: str) -> str:
    import whisperx
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        wav_path = f.name
    try:
        audio = whisperx.load_audio(wav_path)
        kwargs = {}
        if language and language != "auto":
            kwargs["language"] = language
        result = model.transcribe(audio, **kwargs)
        segments = result.get("segments", [])
        return " ".join(s["text"].strip() for s in segments).strip()
    finally:
        Path(wav_path).unlink(missing_ok=True)


def _handle(conn: socket.socket, model) -> None:
    try:
        header, wav_bytes = _read_message(conn)
        language = header.get("language", "auto")
        log.info("Transcribing %d bytes, language=%s", len(wav_bytes), language)
        text = _transcribe(model, wav_bytes, language)
        log.info("Result: %r", text)
        _send_response(conn, {"text": text})
    except Exception as exc:
        log.exception("Transcription error")
        try:
            _send_response(conn, {"error": str(exc)})
        except Exception:
            pass


def main() -> None:
    SOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOCK_PATH.unlink(missing_ok=True)

    model = _load_model()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCK_PATH))
    server.listen(8)
    SOCK_PATH.chmod(0o666)
    log.info("Listening on %s", SOCK_PATH)

    def _shutdown(sig, _frame):
        log.info("Shutting down.")
        server.close()
        SOCK_PATH.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            conn, _ = server.accept()
        except OSError:
            break
        with conn:
            _handle(conn, model)


if __name__ == "__main__":
    main()
