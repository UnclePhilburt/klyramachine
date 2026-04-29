#!/bin/bash
# Klyra Machine — Installer
# One-command setup for a Raspberry Pi (or any aarch64/x86_64 Linux).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/UnclePhilburt/klyramachine/main/easy_install.sh | bash
#
# Optional env vars:
#   KLYRA_REPO_URL    — repo to clone (default: github)
#   KLYRA_REPO_BRANCH — branch (default: main)
#   KLYRA_INSTALL_DIR — install location (default: $HOME/klyramachine)
#   KLYRA_LOCKDOWN    — yes|no, dedicated klyra user + restricted perms (default: no)
#   KLYRA_SKIP_CLONE  — 1 to skip git clone (use existing $KLYRA_INSTALL_DIR; for local testing)

set -e
set -o pipefail

KLYRA_REPO_URL="${KLYRA_REPO_URL:-https://github.com/UnclePhilburt/klyramachine.git}"
KLYRA_REPO_BRANCH="${KLYRA_REPO_BRANCH:-main}"
KLYRA_INSTALL_DIR="${KLYRA_INSTALL_DIR:-$HOME/klyramachine}"
KLYRA_LOCKDOWN="${KLYRA_LOCKDOWN:-no}"
KLYRA_SKIP_CLONE="${KLYRA_SKIP_CLONE:-0}"
PYTHON_VERSION="3.12"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'
log_info()    { echo "${BLUE}[INFO]${NC} $1"; }
log_success() { echo "${GREEN}[OK]${NC} $1"; }
log_warning() { echo "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo "${RED}[ERROR]${NC} $1"; }
log_step()    { echo; echo "${GREEN}========================================${NC}"; echo "${GREEN}$1${NC}"; echo "${GREEN}========================================${NC}"; }

echo "=========================================="
echo "   KLYRA MACHINE — INSTALLER"
echo "=========================================="
echo
log_info "Started: $(date)"
log_info "User:    $USER"
log_info "Install: $KLYRA_INSTALL_DIR"
log_info "Repo:    $KLYRA_REPO_URL ($KLYRA_REPO_BRANCH)"
log_info "Python:  $PYTHON_VERSION (managed by uv)"
log_info "Lockdown: $KLYRA_LOCKDOWN"

if [[ ! "$OSTYPE" == "linux-gnu"* ]]; then
    log_error "This installer is for Linux only (got: $OSTYPE)"
    exit 1
fi
if [ -f /proc/device-tree/model ]; then
    log_info "Hardware: $(tr -d '\0' < /proc/device-tree/model)"
else
    log_info "Hardware: generic Linux ($(uname -m))"
fi

# ----------------------------------------------------------------------------
log_step "STEP 1: System libraries (apt)"
log_info "Updating apt..."
sudo apt-get update -qq
log_info "Installing system C libraries needed at runtime/build..."
# Python wheels handle the Python side; apt only provides system C libs.
sudo apt-get install -y --no-install-recommends \
    git curl unzip ca-certificates \
    build-essential \
    portaudio19-dev libasound2-dev \
    libsdl2-2.0-0 libsdl2-mixer-2.0-0
sudo apt-get install -y libatlas-base-dev 2>/dev/null || log_warning "libatlas-base-dev unavailable (optional perf)"
sudo apt-get install -y libopenblas-dev  2>/dev/null || log_warning "libopenblas-dev unavailable (optional perf)"
log_success "System libraries installed"

# ----------------------------------------------------------------------------
log_step "STEP 2: uv (Python toolchain)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &>/dev/null; then
    log_info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
log_success "uv $(uv --version | awk '{print $2}')"

# ----------------------------------------------------------------------------
log_step "STEP 3: Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION"
log_success "Python $PYTHON_VERSION ready"

# ----------------------------------------------------------------------------
log_step "STEP 4: Klyra source"
if [ "$KLYRA_SKIP_CLONE" = "1" ]; then
    log_info "KLYRA_SKIP_CLONE=1 — using existing $KLYRA_INSTALL_DIR"
    [ -d "$KLYRA_INSTALL_DIR/client" ] || { log_error "$KLYRA_INSTALL_DIR/client not found"; exit 1; }
elif [ -d "$KLYRA_INSTALL_DIR/.git" ]; then
    log_info "Existing checkout found — stopping service if running"
    sudo systemctl stop klyra.service 2>/dev/null || true
    log_info "Updating existing checkout..."
    cd "$KLYRA_INSTALL_DIR"
    git fetch origin
    git checkout "$KLYRA_REPO_BRANCH"
    git reset --hard "origin/$KLYRA_REPO_BRANCH"
else
    if [ -d "$KLYRA_INSTALL_DIR" ]; then
        log_warning "$KLYRA_INSTALL_DIR exists but is not a git repo — removing"
        rm -rf "$KLYRA_INSTALL_DIR"
    fi
    log_info "Cloning $KLYRA_REPO_URL ($KLYRA_REPO_BRANCH)..."
    git clone --branch "$KLYRA_REPO_BRANCH" "$KLYRA_REPO_URL" "$KLYRA_INSTALL_DIR"
fi
cd "$KLYRA_INSTALL_DIR"
log_success "Klyra at $KLYRA_INSTALL_DIR ($(git rev-parse --short HEAD 2>/dev/null || echo 'no-git'))"

# ----------------------------------------------------------------------------
log_step "STEP 5: Python environment"
cd "$KLYRA_INSTALL_DIR/client"
log_info "Creating venv (Python $PYTHON_VERSION)..."
uv venv --python "$PYTHON_VERSION" venv
log_info "Installing requirements.txt..."
uv pip install --python venv/bin/python -r requirements.txt
log_info "Installing pygame (audio playback)..."
uv pip install --python venv/bin/python pygame
log_info "Installing webrtcvad (better speech detection — optional)..."
uv pip install --python venv/bin/python webrtcvad || log_warning "webrtcvad install failed; client will use volume-based fallback"
log_success "Python environment ready"

# ----------------------------------------------------------------------------
log_step "STEP 6: ALSA config"
if [ ! -f /etc/asound.conf ]; then
    log_info "Writing /etc/asound.conf (suppresses surround-sound errors)..."
    sudo tee /etc/asound.conf >/dev/null <<'ALSAEOF'
pcm.!default { type hw; card 0 }
ctl.!default { type hw; card 0 }
ALSAEOF
    log_success "/etc/asound.conf written"
else
    log_info "/etc/asound.conf already exists, leaving alone"
fi

# ----------------------------------------------------------------------------
log_step "STEP 7: Vosk model (offline wake word)"
chmod +x download_vosk_model.sh
if ./download_vosk_model.sh; then
    log_success "Vosk model installed (1st try)"
elif log_warning "First attempt failed, retrying..." && ./download_vosk_model.sh; then
    log_success "Vosk model installed (2nd try)"
else
    log_warning "Vosk model download failed both times — wake word will fall back to cloud Whisper"
fi

# ----------------------------------------------------------------------------
log_step "STEP 8: config.json"
if [ -f "config.json" ]; then
    log_info "config.json exists, leaving alone"
    log_info "client_id: $(python3 -c "import json;print(json.load(open('config.json'))['client_id'])" 2>/dev/null || echo '?')"
else
    HOSTNAME_SHORT=$(hostname | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]//g')
    MAC_SUFFIX=""
    for iface in wlan0 eth0 wlp0s1 enp0s3 end0; do
        if [ -f "/sys/class/net/$iface/address" ]; then
            MAC_SUFFIX=$(tr -d : < "/sys/class/net/$iface/address" | tail -c 7)
            [ -n "$MAC_SUFFIX" ] && break
        fi
    done
    if [ -z "$MAC_SUFFIX" ]; then
        # Last resort: any non-loopback interface
        for f in /sys/class/net/*/address; do
            iface=$(basename "$(dirname "$f")")
            [ "$iface" = "lo" ] && continue
            MAC_SUFFIX=$(tr -d : < "$f" | tail -c 7)
            [ -n "$MAC_SUFFIX" ] && break
        done
    fi
    [ -z "$MAC_SUFFIX" ] && MAC_SUFFIX=$(head -c 4 /dev/urandom | xxd -p)
    CLIENT_ID="klyra-${HOSTNAME_SHORT}-${MAC_SUFFIX}"
    log_info "Generated client_id: $CLIENT_ID"
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
    log_success "config.json created"
fi

# ----------------------------------------------------------------------------
log_step "STEP 9: systemd service"
chmod +x install_service.sh start_klyra.sh auto_update.sh
log_info "Running install_service.sh (lockdown=$KLYRA_LOCKDOWN)..."
# install_service.sh has an interactive 'read -p' for lockdown — feed it our choice.
echo "$KLYRA_LOCKDOWN" | ./install_service.sh
log_success "Service installed"

# ----------------------------------------------------------------------------
log_step "STEP 10: Start service"
sudo systemctl start klyra
sleep 3

# ----------------------------------------------------------------------------
log_step "PRE-FLIGHT CHECKS"

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
check() {
    local label="$1"; local result="$2"; local detail="$3"
    case "$result" in
        pass) log_success "  $label  $detail"; PASS_COUNT=$((PASS_COUNT+1)) ;;
        warn) log_warning "  $label  $detail"; WARN_COUNT=$((WARN_COUNT+1)) ;;
        fail) log_error   "  $label  $detail"; FAIL_COUNT=$((FAIL_COUNT+1)) ;;
    esac
}

CLIENT_ID_VAL=$(python3 -c "import json;print(json.load(open('config.json'))['client_id'])" 2>/dev/null || echo "?")
check "client_id      " pass "$CLIENT_ID_VAL"

if curl -fsSL --max-time 15 https://klyramachine.onrender.com/ >/dev/null 2>&1; then
    check "server         " pass "https://klyramachine.onrender.com (reachable)"
else
    check "server         " warn "no response (may be sleeping; will wake on first request)"
fi

MIC_OK=$(venv/bin/python - <<'PY' 2>/dev/null
try:
    import pyaudio
    p = pyaudio.PyAudio()
    n = sum(1 for i in range(p.get_device_count()) if p.get_device_info_by_index(i)['maxInputChannels'] > 0)
    p.terminate()
    print(n)
except Exception:
    print(0)
PY
)
if [ "${MIC_OK:-0}" -gt 0 ]; then
    check "mic            " pass "$MIC_OK input device(s)"
else
    check "mic            " warn "none — Klyra will run text-only"
fi

if venv/bin/python -c "import cv2; c=cv2.VideoCapture(0); ok=c.isOpened(); c.release(); exit(0 if ok else 1)" 2>/dev/null; then
    check "camera         " pass "/dev/video0 opens"
else
    check "camera         " warn "none — Klyra will skip vision"
fi

if [ -f "vosk-model-small-en-us-0.15/mfcc.conf" ]; then
    check "vosk model     " pass "complete"
else
    check "vosk model     " warn "incomplete — wake word uses cloud Whisper"
fi

if systemctl is-active klyra.service &>/dev/null; then
    check "klyra.service  " pass "running"
else
    check "klyra.service  " fail "NOT running — see: sudo journalctl -u klyra -n 50"
fi
if systemctl is-enabled klyra.service &>/dev/null; then
    check "autostart      " pass "enabled at boot"
else
    check "autostart      " fail "NOT enabled"
fi

if systemctl is-active klyra-update.timer &>/dev/null; then
    check "auto-update    " pass "every hour (systemd timer)"
elif crontab -l 2>/dev/null | grep -q auto_update; then
    check "auto-update    " pass "every hour (cron fallback)"
else
    check "auto-update    " fail "NOT scheduled"
fi

echo
log_info "Pass: $PASS_COUNT   Warn: $WARN_COUNT   Fail: $FAIL_COUNT"
echo

if [ "$FAIL_COUNT" -eq 0 ]; then
    log_success "=========================================="
    log_success "  Installation complete!"
    log_success "=========================================="
    echo
    log_info "Say 'Hey Buddy' to talk to Klyra."
    echo
    log_info "Useful commands:"
    log_info "  Status:   sudo systemctl status klyra"
    log_info "  Logs:     sudo journalctl -u klyra -f"
    log_info "  Restart:  sudo systemctl restart klyra"
    log_info "  Update:   cd $KLYRA_INSTALL_DIR && ./client/auto_update.sh"
else
    log_error "=========================================="
    log_error "  $FAIL_COUNT critical check(s) failed — see above"
    log_error "=========================================="
    exit 1
fi
