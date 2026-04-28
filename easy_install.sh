#!/bin/bash
# Easy Installer for Klyra Machine
# One-click setup for Raspberry Pi

set -e  # Exit on error
# set -x  # Uncomment for extreme debugging (shows every command)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

echo "=========================================="
echo "   KLYRA MACHINE - EASY INSTALLER"
echo "   (Verbose Debug Mode)"
echo "=========================================="
echo ""

log_info "Installer started at: $(date)"
log_info "Running as user: $USER"
log_info "Home directory: $HOME"
log_info "Current directory: $(pwd)"
log_info "OS Type: $OSTYPE"

# Check if running on Raspberry Pi or Linux
if [[ ! "$OSTYPE" == "linux-gnu"* ]]; then
    log_error "This installer is for Linux/Raspberry Pi only"
    log_info "For Windows, see the client folder for manual setup"
    exit 1
fi

log_success "OS check passed"

# Detect Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    log_info "Detected: $PI_MODEL"
else
    log_info "Running on generic Linux system"
fi

# Get current directory
INSTALL_DIR="$HOME/klyramachine"
log_info "Installation directory: $INSTALL_DIR"

# Check if we need to download the code (install git first if needed)
log_step "STEP 0: Download Klyra Code"
if [ ! -d "$INSTALL_DIR/.git" ]; then
    log_info "Klyra code not found, will download from GitHub..."

    # Install git first if not present
    if ! command -v git &> /dev/null; then
        log_info "Installing git..."
        sudo apt update -qq
        sudo apt install -y git
    fi

    # Remove incomplete installation if exists
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "Removing incomplete installation at $INSTALL_DIR"
        rm -rf "$INSTALL_DIR"
    fi

    # Clone the repository
    log_info "Cloning from https://github.com/UnclePhilburt/klyramachine.git"
    if git clone https://github.com/UnclePhilburt/klyramachine.git "$INSTALL_DIR"; then
        log_success "Code downloaded successfully"
        cd "$INSTALL_DIR"
    else
        log_error "Failed to download code from GitHub"
        log_info "Please check your internet connection and try again"
        exit 1
    fi
else
    log_info "Klyra code already present, updating..."
    cd "$INSTALL_DIR"
    git pull || log_warning "Could not update code (continuing with existing version)"
fi

log_step "STEP 1: Installing System Dependencies"
log_info "Updating package lists..."
if sudo apt update; then
    log_success "Package lists updated"
else
    log_error "Failed to update package lists"
    exit 1
fi

log_info "Installing required packages..."
log_info "  - git (version control)"
log_info "  - python3-pip (Python package manager)"
log_info "  - python3-venv (virtual environments)"
log_info "  - python3-dev (Python development headers)"
log_info "  - build-essential (compiler tools)"
log_info "  - python3-pyaudio (audio input/output)"
log_info "  - portaudio19-dev (audio library)"
log_info "  - python3-opencv (camera/vision)"
log_info "  - python3-scipy (scientific computing)"
log_info "  - python3-numpy (numerical arrays)"

# Install core packages first
if sudo apt install -y git python3-pip python3-venv python3-dev build-essential python3-pyaudio portaudio19-dev python3-opencv python3-scipy python3-numpy; then
    log_success "Core system dependencies installed"
else
    log_error "Failed to install core system dependencies"
    exit 1
fi

# Try to install optional OpenCV dependencies (may not exist on all Pi versions)
log_info "Installing optional OpenCV dependencies..."
if sudo apt install -y libatlas-base-dev 2>/dev/null; then
    log_success "libatlas-base-dev installed"
else
    log_warning "libatlas-base-dev not available (optional)"
fi

if sudo apt install -y libopenblas-dev 2>/dev/null; then
    log_success "libopenblas-dev installed"
else
    log_warning "libopenblas-dev not available (optional)"
fi

# Verify key installations
log_info "Verifying installations..."
git --version && log_success "git installed: $(git --version)"
python3 --version && log_success "python3 installed: $(python3 --version)"
pip3 --version && log_success "pip3 installed: $(pip3 --version)"

log_step "STEP 2: Downloading Klyra Machine"

if [ -d "$INSTALL_DIR" ]; then
    log_warning "Klyra already exists at $INSTALL_DIR"
    log_info "Directory size: $(du -sh $INSTALL_DIR 2>/dev/null | cut -f1 || echo 'unknown')"

    # Stop the service if it's running
    if systemctl is-active klyra.service &>/dev/null; then
        log_info "Stopping running service..."
        sudo systemctl stop klyra.service
        log_success "Service stopped"
    fi

    log_info "Automatically removing old installation for fresh install..."
    rm -rf "$INSTALL_DIR"
    log_success "Old installation removed"
fi

log_info "Cloning from GitHub: https://github.com/UnclePhilburt/klyramachine.git"
if git clone https://github.com/UnclePhilburt/klyramachine.git "$INSTALL_DIR"; then
    log_success "Repository cloned successfully"
    log_info "Repository size: $(du -sh $INSTALL_DIR | cut -f1)"
else
    log_error "Failed to clone repository"
    log_info "Check your internet connection and try again"
    exit 1
fi

log_info "Changing to client directory: $INSTALL_DIR/client"
cd "$INSTALL_DIR/client"
log_info "Current directory: $(pwd)"
log_info "Files in client directory:"
ls -lah | head -15

log_step "STEP 3: Setting up Python Environment"

# Create virtual environment
if [ ! -d "venv" ]; then
    log_info "Creating virtual environment..."
    log_info "Command: python3 -m venv venv --system-site-packages"

    if python3 -m venv venv --system-site-packages; then
        log_success "Virtual environment created"
        log_info "venv size: $(du -sh venv | cut -f1)"
    else
        log_error "Failed to create virtual environment"
        exit 1
    fi
else
    log_info "Virtual environment already exists"
fi

# Activate virtual environment
log_info "Activating virtual environment..."
source venv/bin/activate

if [ -n "$VIRTUAL_ENV" ]; then
    log_success "Virtual environment activated: $VIRTUAL_ENV"
    log_info "Python: $(which python)"
    log_info "Pip: $(which pip)"
else
    log_error "Failed to activate virtual environment"
    exit 1
fi

log_info "Installing Python dependencies from requirements.txt..."
log_info "Requirements file contents:"
cat requirements.txt

echo ""
log_info "Running: pip install -r requirements.txt"
if pip install -r requirements.txt 2>&1 | tee /tmp/pip-install.log; then
    log_success "Python dependencies installed"
else
    log_warning "Some packages may have failed to install"
    log_info "Check /tmp/pip-install.log for details"
fi

log_info "Note: webrtcvad might fail to build - that's okay, fallback speech detection will be used"

log_info "Installed Python packages:"
pip list | grep -E "requests|opencv|pygame|pyaudio|numpy|scipy|pvporcupine|vosk" || log_info "Listing all packages..."
pip list

log_step "STEP 3.5: Configuring Audio System (ALSA)"

log_info "Fixing ALSA configuration to prevent spam errors..."

# Create ALSA config to suppress errors about missing surround sound configs
if [ ! -f /etc/asound.conf ]; then
    log_info "Creating /etc/asound.conf..."
    sudo tee /etc/asound.conf > /dev/null <<'ALSAEOF'
# Simple ALSA configuration for Raspberry Pi
# Prevents errors about missing surround sound configurations

pcm.!default {
    type hw
    card 0
}

ctl.!default {
    type hw
    card 0
}
ALSAEOF
    log_success "ALSA configuration created"
else
    log_info "/etc/asound.conf already exists, skipping"
fi

log_step "STEP 3.6: Setting up Vosk Model (Offline Wake Word)"

log_info "Checking Vosk model for 100% local wake word detection..."

# Check if model already exists (from git clone)
if [ -f "vosk-model-small-en-us-0.15/conf/mfcc.conf" ]; then
    log_success "Vosk model already present from repository!"
    log_info "Model size: $(du -sh vosk-model-small-en-us-0.15 | cut -f1)"
    log_success "100% offline wake word enabled!"
else
    log_info "Vosk model not in repository, downloading..."
    log_info "This is a one-time download (~40MB)"

    chmod +x download_vosk_model.sh

    # Make sure we have unzip
    if ! command -v unzip &> /dev/null; then
        log_info "Installing unzip (required for Vosk model)..."
        sudo apt install -y unzip
    fi

    # Download Vosk model with better error handling
    if ./download_vosk_model.sh 2>&1 | tee /tmp/vosk-download.log; then
        log_success "Vosk model downloaded!"

        # Verify the model actually exists
        if [ -f "vosk-model-small-en-us-0.15/conf/mfcc.conf" ]; then
            log_success "Vosk model verified - 100% offline wake word enabled!"
        else
            log_warning "Vosk model files incomplete - will use cloud-based wake word"
        fi
    else
        log_warning "Vosk model download failed - will use cloud-based wake word"
        log_info "This is okay! Cloud-based wake word still works."
        log_info "You can manually download later with: ./download_vosk_model.sh"
    fi
fi

log_step "STEP 4: Configuration"

# Check if config already exists
if [ -f "config.json" ]; then
    log_info "Config file already exists"
    log_info "Current config:"
    cat config.json | head -20
else
    log_info "Creating config file..."
    CLIENT_ID="raspberry_pi_$(hostname)"
    log_info "Client ID: $CLIENT_ID"

    cat > config.json <<EOF
{
    "server_url": "https://klyramachine.onrender.com",
    "client_id": "$CLIENT_ID",
    "camera_index": 0,
    "wake_word": "hey buddy",
    "enable_camera": true,
    "vosk_model_path": "vosk-model-small-en-us-0.15"
}
EOF

    if [ -f "config.json" ]; then
        log_success "Config file created"
        log_info "Config contents:"
        cat config.json
    else
        log_error "Failed to create config file"
        exit 1
    fi
fi

log_info "Server URL: https://klyramachine.onrender.com"
log_info "Testing server connection..."
if curl -s --max-time 10 https://klyramachine.onrender.com/ > /dev/null 2>&1; then
    log_success "Server is reachable"
else
    log_warning "Server connection test failed (might be sleeping, will wake up on first request)"
fi

log_info "Checking for ding.mp3..."
if [ -f "ding.mp3" ]; then
    log_success "ding.mp3 found (wake word sound)"
    log_info "File size: $(ls -lh ding.mp3 | awk '{print $5}')"
else
    log_warning "ding.mp3 not found (wake word will be silent)"
fi

log_step "STEP 5: Setting up Auto-Start Service"

log_info "Making scripts executable..."
chmod +x install_service.sh && log_success "install_service.sh is executable"
chmod +x start_klyra.sh && log_success "start_klyra.sh is executable"
chmod +x auto_update.sh && log_success "auto_update.sh is executable"

log_info "Script permissions:"
ls -lh install_service.sh start_klyra.sh auto_update.sh

echo ""
log_info "Running service installer (this will create systemd services)..."
log_info "You may be prompted for your sudo password..."
echo ""

if ./install_service.sh 2>&1 | tee /tmp/service-install.log; then
    log_success "Service installation completed"
else
    log_error "Service installation failed"
    log_info "Check /tmp/service-install.log for details"
    log_info "You can still run manually: cd $INSTALL_DIR/client && ./start_klyra.sh"
fi

echo ""
log_step "STEP 6: Starting Klyra Service"

log_info "Starting Klyra service..."
if sudo systemctl start klyra 2>&1 | tee -a /tmp/service-install.log; then
    log_success "Service start command executed"
    sleep 3  # Give it time to start
else
    log_warning "Service start command had issues"
fi

echo ""
log_info "========================================"
log_info "AUDIO DETECTION TEST (EXTREME DEBUG)"
log_info "========================================"
log_info "Testing PyAudio availability and actual audio devices..."

# More robust audio test - check if there are actual input devices
AUDIO_TEST_OUTPUT=$(python3 -c "
import pyaudio
import sys
try:
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    input_devices = 0
    for i in range(device_count):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            input_devices += 1
            print(f'Found input device: {info[\"name\"]}')
    p.terminate()
    if input_devices > 0:
        print(f'RESULT: {input_devices} input devices found')
        sys.exit(0)
    else:
        print('RESULT: No input devices found')
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>&1 | tee /tmp/audio-test.log; echo "EXIT_CODE: $?")

echo "$AUDIO_TEST_OUTPUT"
if echo "$AUDIO_TEST_OUTPUT" | grep -q "EXIT_CODE: 0"; then
    AUDIO_RESULT="AUDIO_AVAILABLE"
    log_success "Audio test PASSED - input devices detected"
else
    AUDIO_RESULT="NO_AUDIO"
    log_warning "Audio test FAILED - no input devices found"
fi
log_info "Audio test result: $AUDIO_RESULT"
log_info "Full test output:"
cat /tmp/audio-test.log || true
echo ""

# Check if we're in text mode FIRST (before checking service)
if [ "$AUDIO_RESULT" = "NO_AUDIO" ]; then
    log_warning "========================================"
    log_warning "NO AUDIO DETECTED - ENTERING TEXT MODE"
    log_warning "========================================"
    echo ""
    log_info "[DEBUG] Current directory: $(pwd)"
    log_info "[DEBUG] Target directory: $INSTALL_DIR/client"
    log_info "[DEBUG] Checking if client_text.py exists..."
    if [ -f "$INSTALL_DIR/client/client_text.py" ]; then
        log_success "[DEBUG] client_text.py found!"
        log_info "[DEBUG] File size: $(ls -lh $INSTALL_DIR/client/client_text.py | awk '{print $5}')"
    else
        log_error "[DEBUG] client_text.py NOT FOUND!"
        log_info "[DEBUG] Listing client directory:"
        ls -la "$INSTALL_DIR/client/" | head -20
    fi
    echo ""
    log_info "[DEBUG] Disabling auto-start service..."
    sudo systemctl disable klyra.service 2>&1 | head -5 || true
    log_info "[DEBUG] Stopping service..."
    sudo systemctl stop klyra.service 2>&1 | head -5 || true
    log_info "[DEBUG] Service disabled and stopped"
    echo ""
    log_success "==================================================="
    log_success "  LAUNCHING KLYRA TEXT MODE NOW"
    log_success "==================================================="
    log_info "[DEBUG] Changing to client directory..."
    cd "$INSTALL_DIR/client" || { log_error "[DEBUG] Failed to cd!"; exit 1; }
    log_success "[DEBUG] Now in: $(pwd)"
    log_info "[DEBUG] Python3 path: $(which python3)"
    log_info "[DEBUG] Python3 version: $(python3 --version)"
    log_info "[DEBUG] About to exec: python3 client_text.py"
    log_info "[DEBUG] This is the last line before text client starts"
    echo ""
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    echo "EXECUTING: python3 client_text.py"
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    echo ""
    # Start text client interactively directly (skip start_klyra.sh)
    exec python3 client_text.py
else
    log_info "Checking service status..."
    if systemctl is-active klyra.service &>/dev/null; then
        log_success "✓ Klyra is running!"
        echo ""
        log_info "Service output (last 10 lines):"
        sudo journalctl -u klyra -n 10 --no-pager | tail -10 || true
    else
        log_error "Service failed to start"
        echo ""
        log_info "Checking error logs..."
        sudo journalctl -u klyra -n 30 --no-pager || true
    fi
fi

echo ""
log_step "INSTALLATION COMPLETE!"

log_success "Klyra Machine has been installed successfully!"
echo ""

log_info "Installation Summary:"
log_info "  Location: $INSTALL_DIR"
log_info "  Client: client_wake_improved.py or client_vosk.py (auto-detected)"
log_info "  Wake word: 'hey buddy'"
log_info "  Server: https://klyramachine.onrender.com"
echo ""

log_info "System Service Status:"
if systemctl is-enabled klyra.service &>/dev/null; then
    log_success "klyra.service is enabled (will auto-start on boot)"
else
    log_warning "klyra.service is not enabled"
fi

if systemctl is-active klyra.service &>/dev/null; then
    log_success "klyra.service is RUNNING ✓"
else
    log_warning "klyra.service is NOT running - check logs above"
fi

if systemctl is-enabled klyra-update.timer &>/dev/null; then
    log_success "klyra-update.timer is enabled (auto-updates every hour)"
else
    log_warning "klyra-update.timer is not enabled"
fi

echo ""
log_info "Commands to control Klyra:"
echo "  Start:   ${GREEN}sudo systemctl start klyra${NC}"
echo "  Stop:    ${YELLOW}sudo systemctl stop klyra${NC}"
echo "  Restart: ${BLUE}sudo systemctl restart klyra${NC}"
echo "  Status:  ${BLUE}sudo systemctl status klyra${NC}"
echo "  Logs:    ${BLUE}sudo journalctl -u klyra -f${NC}"
echo ""

log_info "Quick test (without service):"
echo "  ${GREEN}cd $INSTALL_DIR/client && ./start_klyra.sh${NC}"
echo ""

# Check if audio is available
if ! python3 -c "import pyaudio; p = pyaudio.PyAudio(); p.terminate()" 2>/dev/null; then
    log_warning "TEXT INPUT MODE (No Audio Detected)"
    echo ""
    log_info "To start Klyra in text mode:"
    echo "  ${GREEN}cd $INSTALL_DIR/client && python3 client_text.py${NC}"
    echo ""
    log_info "In text mode:"
    echo "  • Type your messages instead of speaking"
    echo "  • Camera still works (if available)"
    echo "  • Responses shown as text (no voice)"
    echo ""
else
    log_info "Klyra Features:"
    echo "  ✓ Auto-start on boot"
    echo "  ✓ Auto-update every hour"
    echo "  ✓ Auto-restart if it crashes"
    echo "  ✓ Wake word detection ('Hey Buddy')"
    echo "  ✓ Ding sound on wake word"
    echo ""
    log_success "Say 'Hey Buddy' to talk to Klyra!"
    echo ""
fi
log_info "Installation log saved to: /tmp/service-install.log"
log_info "Completed at: $(date)"
echo "=========================================="
