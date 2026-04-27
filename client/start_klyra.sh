#!/bin/bash
# Smart starter for Klyra - uses best available wake word method

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  KLYRA SMART STARTER"
echo "=========================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

echo "Working directory: $(pwd)"
echo "Python: $(which python)"
echo ""

# Check which wake word method to use
if [ -d "vosk-model-small-en-us-0.15" ]; then
    echo "✓ Vosk model found - using 100% offline wake word detection"
    echo "Starting: client_vosk.py"
    echo ""
    python client_vosk.py
elif python -c "import pvporcupine" 2>/dev/null && [ -f "config.json" ] && grep -q "porcupine_access_key" config.json; then
    echo "✓ Porcupine available - using Porcupine wake word detection"
    echo "Starting: client_porcupine.py"
    echo ""
    python client_porcupine.py
else
    echo "✓ Using cloud-based wake word detection"
    echo "Starting: client_wake_improved.py"
    echo ""
    python client_wake_improved.py
fi
