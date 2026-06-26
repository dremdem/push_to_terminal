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

echo "==> Linking binaries to ~/.local/bin ..."
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/.venv/bin/voice-paste"      "$HOME/.local/bin/voice-paste"
ln -sf "$SCRIPT_DIR/.venv/bin/voice-paste-tray" "$HOME/.local/bin/voice-paste-tray"

# Ensure ~/.local/bin is on PATH for the rest of this script
export PATH="$HOME/.local/bin:$PATH"

echo "==> Installing desktop entry..."
voice-paste install --autostart

echo ""
echo "Done! voice-paste is installed."
echo ""
echo "  Launch:  search 'Voice Paste' in GNOME Activities (or run: voice-paste-tray)"
echo "  Hotkey:  voice-paste hotkey set ctrl+alt+shift+p"
echo ""
echo "  If 'voice-paste' is not found in a new terminal, add this to ~/.zshrc or ~/.bashrc:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
