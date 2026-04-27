#!/bin/bash
# Download Vosk model for offline wake word detection

echo "=========================================="
echo "  VOSK MODEL DOWNLOADER"
echo "=========================================="
echo ""

MODEL_NAME="vosk-model-small-en-us-0.15"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Model: $MODEL_NAME"
echo "Size: ~40MB"
echo "Location: $MODEL_DIR/$MODEL_NAME"
echo ""

# Check if model already exists
if [ -d "$MODEL_DIR/$MODEL_NAME" ]; then
    echo "✓ Model already downloaded!"
    echo "Location: $MODEL_DIR/$MODEL_NAME"
    exit 0
fi

# Download model
echo "Downloading Vosk model..."
echo "This may take a few minutes..."
echo ""

if command -v wget &> /dev/null; then
    wget -O "$MODEL_DIR/${MODEL_NAME}.zip" "$MODEL_URL"
elif command -v curl &> /dev/null; then
    curl -L -o "$MODEL_DIR/${MODEL_NAME}.zip" "$MODEL_URL"
else
    echo "ERROR: Neither wget nor curl found!"
    echo "Please install wget or curl"
    exit 1
fi

# Extract model
echo ""
echo "Extracting model..."
cd "$MODEL_DIR"
unzip -q "${MODEL_NAME}.zip"

# Cleanup
rm "${MODEL_NAME}.zip"

echo ""
echo "✓ Vosk model installed successfully!"
echo "Location: $MODEL_DIR/$MODEL_NAME"
echo ""
echo "You can now run: python client_vosk.py"
echo ""
