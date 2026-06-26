FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install whisperx (brings ctranslate2 4.5+, which bundles its own cuDNN 9)
RUN pip3 install --no-cache-dir "whisperx==3.8.5"

# whisperx pulls torch~=2.8.0 from PyPI (CUDA 12.8 wheels) which requires driver ≥570.
# Force-reinstall with cu124 wheels so it works on CUDA 12.4 driver (~550.x).
RUN pip3 install --no-cache-dir --force-reinstall \
    torch torchaudio \
    --index-url https://download.pytorch.org/whl/cu124

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
