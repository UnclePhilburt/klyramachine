#!/bin/bash
set -e

echo "================================"
echo "KLYRA MACHINE QUICK INSTALLER"
echo "================================"

# Install system packages
echo "[1/4] Installing system packages..."
sudo apt update -qq
echo "Installing SDL libraries first..."
sudo apt install -y libsdl2-dev libsdl2-mixer-dev pkg-config
echo "Installing other dependencies..."
sudo apt install -y git python3-pip python3-venv python3-full portaudio19-dev python3-opencv

# Go to home and clone
echo "[2/4] Downloading code..."
cd ~
if [ -d "klyramachine" ]; then
    rm -rf klyramachine
fi
git clone -q https://github.com/UnclePhilburt/klyramachine.git

# Setup Python environment
echo "[3/4] Setting up Python environment..."
cd ~/klyramachine/client
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create config
echo "[4/4] Creating config..."
cp config.example.json config.json

echo ""
echo "✅ INSTALLATION COMPLETE!"
echo ""
echo "Start Klyra with:"
echo "  cd ~/klyramachine/client && source venv/bin/activate && python3 client_companion.py"
echo ""
