#!/usr/bin/env bash
# voice-paste installer for Ubuntu 22.04 / 24.04+
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing system dependencies..."
sudo apt-get install -y \
    libgirepository-2.0-dev \
    libcairo2-dev \
    gir1.2-appindicator3-0.1 \
    pipewire-bin \
    wl-clipboard \
    libnotify-bin \
    ffmpeg

echo "==> Checking for uv..."
if ! command -v uv &>/dev/null; then
    echo "    uv not found — installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in this shell session
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Installing Python dependencies..."
cd "$SCRIPT_DIR"
uv sync --extra tray

echo "==> Installing desktop entry..."
uv run voice-paste install --autostart

echo ""
echo "Done! voice-paste is installed."
echo ""
echo "  Launch:  search 'Voice Paste' in GNOME Activities"
echo "  Hotkey:  uv run voice-paste hotkey set ctrl+alt+shift+p"
echo "  Tray:    uv run voice-paste-tray"
