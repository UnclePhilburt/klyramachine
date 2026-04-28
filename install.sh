#!/bin/bash
set -e

echo "INSTALLING KLYRA MACHINE..."

# Install EVERYTHING from system packages
sudo apt update -qq
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    python3-pyaudio \
    python3-pygame libsdl2-2.0-0 libsdl2-mixer-2.0-0 \
    python3-opencv \
    python3-scipy \
    python3-numpy \
    python3-requests \
    python3-dotenv \
    portaudio19-dev

# Clone
cd ~
rm -rf klyramachine
git clone https://github.com/UnclePhilburt/klyramachine.git
cd klyramachine/client

# Create venv with system packages
python3 -m venv --system-site-packages venv
source venv/bin/activate

# Only install what's NOT available as system package
pip install -q pvporcupine vosk Pillow

# Config
cp config.example.json config.json

echo ""
echo "✅ DONE!"
echo ""
echo "Run: cd ~/klyramachine/client && source venv/bin/activate && python3 client_companion.py"
