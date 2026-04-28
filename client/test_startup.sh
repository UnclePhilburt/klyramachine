#!/bin/bash
# Test script to diagnose startup issues

echo "==========================================="
echo "  KLYRA STARTUP DIAGNOSTIC TEST"
echo "==========================================="
echo ""

# Get to the right directory
if [ -z "$INVOCATION_ID" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    cd "$SCRIPT_DIR" || exit 1
fi

echo "Working directory: $(pwd)"
echo ""

# Check Python
echo "1. Testing Python..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "   ✓ Virtual environment activated"
else
    echo "   ❌ No virtual environment found!"
    exit 1
fi

python --version
echo ""

# Check imports
echo "2. Testing Python imports..."
python -c "import cv2; print('   ✓ OpenCV imported')" || echo "   ❌ OpenCV failed"
python -c "import pyaudio; print('   ✓ PyAudio imported')" || echo "   ❌ PyAudio failed"
python -c "import requests; print('   ✓ Requests imported')" || echo "   ❌ Requests failed"
python -c "import pygame; print('   ✓ Pygame imported')" || echo "   ❌ Pygame failed"
python -c "import numpy; print('   ✓ NumPy imported')" || echo "   ❌ NumPy failed"
python -c "from vosk import Model; print('   ✓ Vosk imported')" || echo "   ⚠️  Vosk not available (optional)"
echo ""

# Check files
echo "3. Testing required files..."
[ -f "config.json" ] && echo "   ✓ config.json exists" || echo "   ❌ config.json missing"
[ -f "client_wake_improved.py" ] && echo "   ✓ client_wake_improved.py exists" || echo "   ❌ client_wake_improved.py missing"
[ -f "client_vosk.py" ] && echo "   ✓ client_vosk.py exists" || echo "   ❌ client_vosk.py missing"
[ -d "vosk-model-small-en-us-0.15" ] && echo "   ✓ Vosk model downloaded" || echo "   ⚠️  Vosk model not downloaded (run ./download_vosk_model.sh)"
echo ""

# Check server connection
echo "4. Testing server connection..."
SERVER_URL=$(python -c "import json; print(json.load(open('config.json'))['server_url'])")
echo "   Server: $SERVER_URL"
if curl -s --max-time 10 "$SERVER_URL/" > /dev/null 2>&1; then
    echo "   ✓ Server is reachable"
else
    echo "   ⚠️  Server not reachable (might be sleeping)"
fi
echo ""

# Check audio devices
echo "5. Testing audio devices..."
python -c "
import pyaudio
p = pyaudio.PyAudio()
device_count = p.get_device_count()
print(f'   Found {device_count} audio devices')
for i in range(device_count):
    info = p.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:
        print(f'   ✓ Input device: {info[\"name\"]}')
p.terminate()
" 2>&1 || echo "   ❌ Audio device check failed"
echo ""

echo "==========================================="
echo "  DIAGNOSTIC TEST COMPLETE"
echo "==========================================="
echo ""
echo "Next steps:"
echo "1. If all checks passed, try: ./start_klyra.sh"
echo "2. If Vosk model missing, run: ./download_vosk_model.sh"
echo "3. If server unreachable, wait 30 seconds and retry"
echo ""
