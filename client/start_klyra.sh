#!/bin/bash
# Smart starter for Klyra - uses best available wake word method

# systemd sets WorkingDirectory, so we're already in the right place
# But if run manually, cd to script directory
if [ -z "$INVOCATION_ID" ]; then
    # Not running under systemd, so cd to script dir
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    cd "$SCRIPT_DIR" || exit 1
fi

echo "=========================================="
echo "  KLYRA SMART STARTER"
echo "=========================================="
echo "Working directory: $(pwd)"
echo ""

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    echo "Python: $(which python)"
elif [ -f "../venv/bin/activate" ]; then
    echo "Activating virtual environment (parent dir)..."
    source ../venv/bin/activate
    echo "Python: $(which python)"
else
    echo "WARNING: No virtual environment found"
    echo "Python: $(which python3)"
fi

echo ""

# Check which wake word method to use
echo "Checking for wake word detection methods..."
echo ""

if [ -f "vosk-model-small-en-us-0.15/mfcc.conf" ]; then
    echo "✓ Vosk model found - using 100% offline wake word detection"
    echo "Starting: client_vosk.py"
    echo ""
    exec python client_vosk.py
elif python -c "import pvporcupine" 2>/dev/null && [ -f "config.json" ] && grep -q "porcupine_access_key" config.json; then
    echo "✓ Porcupine available - using Porcupine wake word detection"
    echo "Starting: client_porcupine.py"
    echo ""
    exec python client_porcupine.py
else
    echo "✓ Using cloud-based wake word detection (Vosk model not found)"
    echo "  To use offline detection, run: ./download_vosk_model.sh"
    echo "Starting: client_wake_improved.py"
    echo ""
    exec python client_wake_improved.py
fi
