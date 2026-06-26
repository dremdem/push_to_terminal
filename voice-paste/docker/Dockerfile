FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# whisperx 3.8.5 pulls torch~=2.8.0 with self-contained CUDA 12.8 runtime.
# Requires NVIDIA driver ≥ 570 (driver 595 on this host: OK).
# ctranslate2 4.8.0 bundles cuDNN 9 — no host cuDNN needed.
RUN pip3 install --no-cache-dir "whisperx==3.8.5"

WORKDIR /app
COPY server.py .

ENV VP_SOCK=/run/voice-paste/docker-transcribe.sock
ENV VP_MODEL=base
ENV VP_DEVICE=cuda
ENV VP_COMPUTE_TYPE=float16
ENV VP_VAD_METHOD=silero

HEALTHCHECK --interval=2s --timeout=2s --retries=90 --start-period=5s \
    CMD python3 -c \
      "import socket,os; s=socket.socket(socket.AF_UNIX); s.settimeout(1); s.connect(os.environ['VP_SOCK']); s.close()" \
    || exit 1

CMD ["python3", "server.py"]
