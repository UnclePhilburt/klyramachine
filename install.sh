#!/bin/bash
# Simple one-line installer for Klyra Machine

set -e

echo "Installing Klyra Machine..."

# Install dependencies
sudo apt update -qq
sudo apt install -y git python3-pip python3-venv python3-pyaudio portaudio19-dev python3-opencv

# Clone repo
cd ~
rm -rf klyramachine
git clone https://github.com/UnclePhilburt/klyramachine.git
cd klyramachine/client

# Create venv and install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create config
cp config.example.json config.json

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start Klyra:"
echo "  cd ~/klyramachine/client"
echo "  source venv/bin/activate"
echo "  python3 client_text.py"
