#!/bin/bash
# Smart starter for Klyra - uses best available wake word method
# EXTREME DEBUG MODE - logs everything!

set -e  # Exit on error
# Uncomment for extreme debugging: set -x

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=========================================="
echo "  KLYRA SMART STARTER (DEBUG MODE)"
echo "=========================================="
log_info "Startup timestamp: $(date)"
log_info "System: $(uname -a)"
log_info "User: $USER (UID: $(id -u))"
log_info "Home: $HOME"
echo ""

# Check if running under systemd
log_info "Checking execution environment..."
if [ -z "$INVOCATION_ID" ]; then
    log_info "Running MANUALLY (not via systemd)"
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    log_info "Script directory: $SCRIPT_DIR"

    log_info "Changing to script directory..."
    if cd "$SCRIPT_DIR"; then
        log_success "Changed to: $(pwd)"
    else
        log_error "Failed to cd to $SCRIPT_DIR"
        exit 1
    fi
else
    log_info "Running via SYSTEMD (INVOCATION_ID: $INVOCATION_ID)"
    log_info "WorkingDirectory set by systemd"
fi

log_info "Current working directory: $(pwd)"
log_info "Directory contents:"
ls -lah | head -20
echo ""

# Check disk space
log_info "Disk space:"
df -h . | grep -v "Filesystem"
echo ""

# Check memory
log_info "Memory available:"
free -h | grep -E "Mem:|Swap:"
echo ""

# Check CPU
log_info "CPU info:"
cat /proc/cpuinfo | grep -E "model name|Hardware|Revision" | head -3 || log_warning "Could not read CPU info"
echo ""

# Activate virtual environment
log_info "Looking for virtual environment..."
if [ -f "venv/bin/activate" ]; then
    log_success "Found venv/bin/activate"
    log_info "Activating virtual environment..."
    source venv/bin/activate

    if [ -n "$VIRTUAL_ENV" ]; then
        log_success "Virtual environment activated: $VIRTUAL_ENV"
        log_info "Python path: $(which python)"
        log_info "Python version: $(python --version 2>&1)"
        log_info "Pip path: $(which pip)"
        log_info "Pip version: $(pip --version 2>&1)"
    else
        log_error "Failed to activate virtual environment!"
        exit 1
    fi
elif [ -f "../venv/bin/activate" ]; then
    log_info "Found ../venv/bin/activate (parent dir)"
    log_info "Activating virtual environment..."
    source ../venv/bin/activate
    log_success "Virtual environment activated: $VIRTUAL_ENV"
    log_info "Python: $(which python)"
else
    log_error "No virtual environment found!"
    log_info "Looking for venv in common locations..."
    find . -name "activate" -type f 2>/dev/null | head -5
    log_warning "Using system Python (not recommended)"
    log_info "Python: $(which python3)"
fi
echo ""

# Check Python packages
log_info "Checking installed Python packages..."
log_info "Checking critical packages:"

python -c "import sys; print(f'   Python {sys.version}')"

python -c "import cv2; print(f'   ✓ OpenCV: {cv2.__version__}')" 2>&1 || log_error "   ✗ OpenCV (cv2) import failed!"
python -c "import pyaudio; print('   ✓ PyAudio available')" 2>&1 || log_error "   ✗ PyAudio import failed!"
python -c "import pygame; print(f'   ✓ Pygame: {pygame.version.ver}')" 2>&1 || log_error "   ✗ Pygame import failed!"
python -c "import numpy as np; print(f'   ✓ NumPy: {np.__version__}')" 2>&1 || log_error "   ✗ NumPy import failed!"
python -c "import requests; print(f'   ✓ Requests: {requests.__version__}')" 2>&1 || log_error "   ✗ Requests import failed!"
python -c "from vosk import Model; print('   ✓ Vosk available')" 2>&1 || log_warning "   ⚠  Vosk not available (will use cloud wake word)"
python -c "import pvporcupine; print('   ✓ Porcupine available')" 2>&1 || log_warning "   ⚠  Porcupine not available (optional)"
echo ""

# Check required files
log_info "Checking required files..."
[ -f "config.json" ] && log_success "config.json exists" || log_error "config.json MISSING!"
[ -f "client_wake_improved.py" ] && log_success "client_wake_improved.py exists" || log_error "client_wake_improved.py MISSING!"
[ -f "client_vosk.py" ] && log_success "client_vosk.py exists" || log_error "client_vosk.py MISSING!"
[ -f "ding.ogg" ] && log_success "ding.ogg exists (wake sound)" || log_warning "ding.ogg missing (wake will be silent)"
echo ""

# Check config.json contents
if [ -f "config.json" ]; then
    log_info "Config file contents:"
    cat config.json | head -20
    echo ""

    log_info "Parsing config values..."
    SERVER_URL=$(python -c "import json; print(json.load(open('config.json'))['server_url'])" 2>&1) || SERVER_URL="unknown"
    CLIENT_ID=$(python -c "import json; print(json.load(open('config.json'))['client_id'])" 2>&1) || CLIENT_ID="unknown"
    WAKE_WORD=$(python -c "import json; print(json.load(open('config.json')).get('wake_word', 'unknown'))" 2>&1) || WAKE_WORD="unknown"
    CAMERA_ENABLED=$(python -c "import json; print(json.load(open('config.json')).get('enable_camera', True))" 2>&1) || CAMERA_ENABLED="unknown"

    log_info "  Server URL: $SERVER_URL"
    log_info "  Client ID: $CLIENT_ID"
    log_info "  Wake word: $WAKE_WORD"
    log_info "  Camera enabled: $CAMERA_ENABLED"
    echo ""
fi

# Check audio devices
log_info "Checking audio devices..."
AUDIO_AVAILABLE=$(python -c "
try:
    import pyaudio
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    print(f'   Found {device_count} audio devices:')
    for i in range(device_count):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f'   ✓ Input #{i}: {info[\"name\"]} ({info[\"maxInputChannels\"]} channels)')
        if info['maxOutputChannels'] > 0:
            print(f'   ✓ Output #{i}: {info[\"name\"]} ({info[\"maxOutputChannels\"]} channels)')
    p.terminate()
    print('AUDIO_OK')
except Exception as e:
    print(f'   ✗ Audio not available: {e}')
    print('AUDIO_FAILED')
" 2>&1)

if echo "$AUDIO_AVAILABLE" | grep -q "AUDIO_OK"; then
    log_success "Audio devices available"
    export KLYRA_TEXT_MODE=false
else
    log_warning "No audio devices - will use TEXT INPUT MODE"
    export KLYRA_TEXT_MODE=true
fi
echo ""

# Check camera
log_info "Checking camera availability..."
python -c "
import cv2
cam = cv2.VideoCapture(0)
if cam.isOpened():
    print('   ✓ Camera 0 is available')
    ret, frame = cam.read()
    if ret:
        print(f'   ✓ Camera resolution: {frame.shape[1]}x{frame.shape[0]}')
    else:
        print('   ⚠  Camera opened but cannot read frames')
    cam.release()
else:
    print('   ✗ Camera 0 not available')
" 2>&1 || log_warning "Camera check failed"
echo ""

# Check server connection
if [ -f "config.json" ]; then
    log_info "Testing server connection..."
    log_info "Server: $SERVER_URL"

    if curl -s --max-time 10 "$SERVER_URL/" > /dev/null 2>&1; then
        log_success "Server is REACHABLE"

        # Test API endpoints
        log_info "Testing API health..."
        curl -s --max-time 5 "$SERVER_URL/health" 2>&1 | head -3 || log_warning "Health endpoint unavailable"
    else
        log_warning "Server NOT reachable (may be sleeping on Render)"
        log_info "Server will wake up on first request (takes ~30 seconds)"
    fi
    echo ""
fi

# Check which wake word method to use
log_info "=========================================="
log_info "Determining wake word detection method..."
log_info "=========================================="
echo ""

# Check for Vosk model
log_info "Checking for Vosk model..."
if [ -d "vosk-model-small-en-us-0.15" ]; then
    log_info "vosk-model-small-en-us-0.15 directory exists"

    if [ -f "vosk-model-small-en-us-0.15/mfcc.conf" ]; then
        log_success "Vosk model COMPLETE (mfcc.conf found)"
        log_info "Model size: $(du -sh vosk-model-small-en-us-0.15 | cut -f1)"
        log_info "Model files:"
        ls -lh vosk-model-small-en-us-0.15/ | head -10

        WAKE_METHOD="vosk"
        CLIENT_SCRIPT="client_vosk.py"
    else
        log_warning "Vosk model directory exists but mfcc.conf missing!"
        log_info "Model may be incomplete. Run: ./download_vosk_model.sh"
        WAKE_METHOD="cloud"
        CLIENT_SCRIPT="client_wake_improved.py"
    fi
else
    log_info "Vosk model not found"
    log_info "To enable offline wake word, run: ./download_vosk_model.sh"
    WAKE_METHOD="cloud"
    CLIENT_SCRIPT="client_wake_improved.py"
fi
echo ""

# Check for Porcupine (alternative)
if [ "$WAKE_METHOD" != "vosk" ]; then
    log_info "Checking for Porcupine..."
    if python -c "import pvporcupine" 2>/dev/null; then
        log_info "Porcupine library installed"

        if [ -f "config.json" ] && grep -q "porcupine_access_key" config.json; then
            ACCESS_KEY=$(python -c "import json; print(json.load(open('config.json')).get('porcupine_access_key', ''))" 2>&1)

            if [ -n "$ACCESS_KEY" ] && [ "$ACCESS_KEY" != "YOUR_PORCUPINE_ACCESS_KEY_HERE" ]; then
                log_success "Porcupine configured with access key"
                WAKE_METHOD="porcupine"
                CLIENT_SCRIPT="client_porcupine.py"
            else
                log_info "Porcupine key not configured"
            fi
        fi
    else
        log_info "Porcupine not available"
    fi
    echo ""
fi

# Check if we should use text mode instead
if [ "$KLYRA_TEXT_MODE" = "true" ]; then
    log_warning "Audio not available - switching to TEXT INPUT MODE"
    CLIENT_SCRIPT="client_text.py"
    WAKE_METHOD="text"
fi

# Final decision
log_info "=========================================="
log_success "WAKE WORD METHOD: $WAKE_METHOD"
log_success "CLIENT SCRIPT: $CLIENT_SCRIPT"
log_info "=========================================="
echo ""

# Verify client script exists
if [ ! -f "$CLIENT_SCRIPT" ]; then
    log_error "Client script not found: $CLIENT_SCRIPT"
    log_info "Available Python files:"
    ls -lh *.py 2>/dev/null || log_error "No Python files found!"
    exit 1
fi

log_info "Client script size: $(ls -lh $CLIENT_SCRIPT | awk '{print $5}')"
log_info "Client script permissions: $(ls -l $CLIENT_SCRIPT | awk '{print $1}')"
echo ""

# Final pre-flight checks
log_info "Running pre-flight checks..."

log_info "1. Testing Python syntax of $CLIENT_SCRIPT..."
if python -m py_compile "$CLIENT_SCRIPT" 2>&1; then
    log_success "   Python syntax valid"
else
    log_error "   Syntax errors in $CLIENT_SCRIPT!"
    exit 1
fi

log_info "2. Testing imports in $CLIENT_SCRIPT..."
python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('client', '$CLIENT_SCRIPT')
# Just check if file loads, don't execute
print('   ✓ Import check passed')
" 2>&1 || log_warning "   Import check had issues"

log_success "Pre-flight checks complete!"
echo ""

log_info "=========================================="
log_info "STARTING KLYRA CLIENT"
log_info "=========================================="
log_info "Method: $WAKE_METHOD"
log_info "Script: $CLIENT_SCRIPT"
log_info "Starting at: $(date)"
log_info "=========================================="
echo ""

# Execute the client
log_info "Executing: python $CLIENT_SCRIPT"
echo ""

exec python "$CLIENT_SCRIPT"
