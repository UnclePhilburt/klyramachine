#!/bin/bash
# Klyra Machine — Installer
# One-command setup for Ubuntu (or any Debian-derived Linux).
# Auto-detects PulseAudio/PipeWire vs bare ALSA and configures audio
# accordingly.
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
#   KLYRA_SKIP_BROWSERS — 1 to skip Chrome/Firefox/Brave install (default: install all three)
#   KLYRA_SKIP_WEBUI    — 1 to skip launcher webui auto-start (systemd + XDG autostart)

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

log_info "Hardware: $(uname -m)"
if ! command -v apt-get >/dev/null 2>&1; then
    log_error "apt-get not found — this installer supports Debian/Ubuntu only."
    log_error "On Fedora/Arch/etc., install deps manually and run install_service.sh by hand."
    exit 1
fi

# Detect whether the install user has a PulseAudio/PipeWire user session.
# Yes (Ubuntu Desktop): audio goes through user-session socket; leave
# /etc/asound.conf alone and pass PULSE env vars to the systemd unit.
# No (Ubuntu Server): bare ALSA; write /etc/asound.conf and skip the
# user-session env vars (the socket doesn't exist).
HAS_USER_AUDIO=0
if dpkg -l 2>/dev/null | awk '/^ii/ {print $2}' | grep -qE '^(pulseaudio|pipewire-pulse)$'; then
    HAS_USER_AUDIO=1
    log_info "Audio: PulseAudio/PipeWire installed (user-session audio)"
else
    log_info "Audio: bare ALSA (no PulseAudio/PipeWire installed)"
fi
export HAS_USER_AUDIO

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
log_step "STEP 1b: Browsers (Chrome, Firefox, Brave)"
# Spotify's OAuth pops out to the system default browser, and the launcher's
# home tile launches whichever is set as default. Each install is best-effort
# — a flaky vendor repo or network blip won't abort the rest of the install.
# Skip with KLYRA_SKIP_BROWSERS=1.
if [ "${KLYRA_SKIP_BROWSERS:-0}" = "1" ]; then
    log_info "KLYRA_SKIP_BROWSERS=1, skipping browsers"
else
    # Firefox — already in Ubuntu's repos.
    if command -v firefox >/dev/null 2>&1; then
        log_info "Firefox already installed"
    else
        log_info "Installing Firefox..."
        sudo apt-get install -y firefox \
            && log_success "Firefox installed" \
            || log_warning "Firefox install failed (skipping)"
    fi

    # Google Chrome — needs Google's apt repo + signing key.
    if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
        log_info "Chrome already installed"
    else
        log_info "Installing Google Chrome..."
        if curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
                | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg 2>/dev/null \
            && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
                | sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null \
            && sudo apt-get update -qq \
            && sudo apt-get install -y google-chrome-stable; then
            log_success "Chrome installed"
        else
            log_warning "Chrome install failed (skipping)"
        fi
    fi

    # Brave — needs Brave's apt repo + signing key.
    if command -v brave-browser >/dev/null 2>&1 || command -v brave-browser-stable >/dev/null 2>&1; then
        log_info "Brave already installed"
    else
        log_info "Installing Brave..."
        if sudo curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg \
                https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg \
            && echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg arch=amd64] https://brave-browser-apt-release.s3.brave.com/ stable main" \
                | sudo tee /etc/apt/sources.list.d/brave-browser-release.list >/dev/null \
            && sudo apt-get update -qq \
            && sudo apt-get install -y brave-browser; then
            log_success "Brave installed"
        else
            log_warning "Brave install failed (skipping)"
        fi
    fi
fi

# ----------------------------------------------------------------------------
log_step "STEP 2: Swap (low-RAM systems)"
# Ubuntu Server does not auto-configure swap. A 1 GB host running
# Klyra + Vosk + OpenCV will OOM without it.
TOTAL_RAM_MB=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1024 ))
CURRENT_SWAP_MB=$(( $(awk '/^SwapTotal:/ {print $2}' /proc/meminfo) / 1024 ))
log_info "RAM: ${TOTAL_RAM_MB} MB, Swap: ${CURRENT_SWAP_MB} MB"

if [ "$TOTAL_RAM_MB" -lt 2048 ] && [ "$CURRENT_SWAP_MB" -lt 1024 ]; then
    log_info "Low RAM, insufficient swap — adding 1 GB /swapfile"
    if [ ! -f /swapfile ]; then
        if sudo fallocate -l 1G /swapfile 2>/dev/null; then
            log_info "Allocated /swapfile via fallocate"
        else
            log_info "fallocate unavailable, using dd..."
            sudo dd if=/dev/zero of=/swapfile bs=1M count=1024 status=none
        fi
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile >/dev/null
    else
        log_info "/swapfile already exists — re-using"
    fi
    sudo swapon /swapfile 2>/dev/null || log_info "/swapfile already active"
    if ! grep -qE '^/swapfile' /etc/fstab; then
        echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
        log_info "Added /swapfile to /etc/fstab (persists across reboot)"
    fi
    log_success "Swap configured"
else
    log_info "Sufficient RAM/swap — skipping"
fi

# ----------------------------------------------------------------------------
log_step "STEP 3: uv (Python toolchain)"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &>/dev/null; then
    log_info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
log_success "uv $(uv --version | awk '{print $2}')"

# ----------------------------------------------------------------------------
log_step "STEP 4: Python $PYTHON_VERSION"
uv python install "$PYTHON_VERSION"
log_success "Python $PYTHON_VERSION ready"

# ----------------------------------------------------------------------------
log_step "STEP 5: Klyra source"
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
log_step "STEP 6: Python environment"
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
log_step "STEP 7: ALSA config"
# This file pins the default ALSA card. On a bare-ALSA system (Ubuntu
# Server) we want the USB capture device, not card 0 — which is typically
# HDMI when a monitor is plugged in and has no microphone. Decision driven
# by HAS_USER_AUDIO (detected above): only touch system audio config when
# there's no user-session router in charge.
if [ "$HAS_USER_AUDIO" = "1" ]; then
    # If a prior bare-ALSA install left a hard-card asound.conf behind, it
    # will silently route ALSA's `default` to a hardware card that may not
    # be the user's real mic (e.g. a VM's onboard ICH device). Overwrite
    # so ALSA's `default` flows through pulse like the rest of the stack.
    if [ -f /etc/asound.conf ] && grep -qE '^\s*pcm\.!default\s*\{\s*type\s+hw' /etc/asound.conf; then
        log_info "Replacing legacy hw-routed /etc/asound.conf with pulse routing..."
        sudo tee /etc/asound.conf >/dev/null <<'ALSAEOF'
pcm.!default { type pulse }
ctl.!default { type pulse }
ALSAEOF
        log_success "/etc/asound.conf now routes through pulse"
    fi
elif [ "$HAS_USER_AUDIO" = "0" ]; then
    if [ ! -f /etc/asound.conf ]; then
        # Find the first card with a capture (input) device. /proc/asound
        # lists every card; cards with a /proc/asound/card<N>/pcm*c entry
        # have at least one capture stream.
        CAPTURE_CARD=""
        for card_dir in /proc/asound/card*; do
            [ -d "$card_dir" ] || continue
            n=${card_dir#/proc/asound/card}
            if ls "$card_dir"/pcm*c 2>/dev/null | grep -q .; then
                CAPTURE_CARD=$n
                break
            fi
        done
        CAPTURE_CARD=${CAPTURE_CARD:-0}
        log_info "Bare ALSA — first card with capture: $CAPTURE_CARD"
        log_info "Writing /etc/asound.conf (default card $CAPTURE_CARD)..."
        sudo tee /etc/asound.conf >/dev/null <<ALSAEOF
pcm.!default { type hw; card $CAPTURE_CARD }
ctl.!default { type hw; card $CAPTURE_CARD }
ALSAEOF
        log_success "/etc/asound.conf written (card $CAPTURE_CARD)"
    else
        log_info "/etc/asound.conf already exists, leaving alone"
    fi
fi

# ----------------------------------------------------------------------------
log_step "STEP 8: Vosk model (offline wake word)"
chmod +x download_vosk_model.sh
if ./download_vosk_model.sh; then
    log_success "Vosk model installed (1st try)"
elif log_warning "First attempt failed, retrying..." && ./download_vosk_model.sh; then
    log_success "Vosk model installed (2nd try)"
else
    log_warning "Vosk model download failed both times — wake word will fall back to cloud Whisper"
fi

# ----------------------------------------------------------------------------
log_step "STEP 8b: Piper voice (offline TTS)"
chmod +x download_piper_voice.sh
if ./download_piper_voice.sh; then
    log_success "Piper voice installed"
else
    log_warning "Piper voice download failed — TTS will fall back to cloud"
fi

# ----------------------------------------------------------------------------
log_step "STEP 8c: Widevine CDM (DRM for Spotify in the launcher)"
# QtWebEngine doesn't ship with Widevine. Without it, the embedded Spotify
# Web Player can browse but can't actually play audio ("No such device").
# We borrow Widevine from a Google Chrome install. Best-effort: failure
# here doesn't break the rest of the install — the launcher just won't
# play DRM media until the user runs ./download_widevine.sh manually.
chmod +x download_widevine.sh
if ./download_widevine.sh; then
    log_success "Widevine installed"
else
    log_warning "Widevine install failed — Spotify in the launcher won't play"
    log_info "Run ./download_widevine.sh manually after install completes"
fi

# ----------------------------------------------------------------------------
log_step "STEP 9: config.json"
if [ -f "config.json" ]; then
    log_info "config.json exists, leaving alone"
    log_info "client_id: $(python3 -c "import json;print(json.load(open('config.json'))['client_id'])" 2>/dev/null || echo '?')"
else
    HOSTNAME_SHORT=$(hostname | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]//g')

    # Try common stable interface names first, then any non-loopback interface.
    # The fallback covers Ubuntu Server's predictable enxXXXXXXXXXXXX names.
    MAC_SUFFIX=""
    for f in /sys/class/net/eth0/address /sys/class/net/wlan0/address /sys/class/net/end0/address /sys/class/net/*/address; do
        [ -f "$f" ] || continue
        iface=$(basename "$(dirname "$f")")
        [ "$iface" = "lo" ] && continue
        candidate=$(tr -d : < "$f" | tail -c 7)
        if [ -n "$candidate" ] && [ "$candidate" != "000000" ]; then
            MAC_SUFFIX=$candidate
            break
        fi
    done
    [ -z "$MAC_SUFFIX" ] && MAC_SUFFIX=$(head -c 4 /dev/urandom | xxd -p)

    # Drop the hostname segment when it's a generic default — multiple
    # hosts would otherwise collide on "klyra-ubuntu-..." prefixes; the
    # MAC alone is unique enough.
    case "$HOSTNAME_SHORT" in
        ubuntu|localhost|"")
            CLIENT_ID="klyra-${MAC_SUFFIX}"
            ;;
        *)
            CLIENT_ID="klyra-${HOSTNAME_SHORT}-${MAC_SUFFIX}"
            ;;
    esac
    log_info "Generated client_id: $CLIENT_ID"
    cat > config.json <<EOF
{
    "server_url": "https://klyramachine.onrender.com",
    "client_id": "$CLIENT_ID",
    "camera_index": 0,
    "wake_word": "hey buddy",
    "enable_camera": true,
    "vosk_model_path": "vosk-model-small-en-us-0.15",
    "stt_engine": "local",
    "whisper_model": "tiny.en",
    "tts_engine": "local",
    "piper_voice": "voices/en_US-lessac-medium.onnx"
}
EOF
    log_success "config.json created"
fi

# ----------------------------------------------------------------------------
log_step "STEP 10: systemd service"
chmod +x install_service.sh start_klyra.sh auto_update.sh run_update.sh
log_info "Running install_service.sh (lockdown=$KLYRA_LOCKDOWN)..."
# install_service.sh has an interactive 'read -p' for lockdown — feed it our choice.
echo "$KLYRA_LOCKDOWN" | ./install_service.sh
log_success "Service installed"

# ----------------------------------------------------------------------------
log_step "STEP 11: Start service"
sudo systemctl start klyra
sleep 3

# ----------------------------------------------------------------------------
log_step "STEP 12: Launcher webui (auto-start)"
# Two pieces: a system-level service that runs the FastAPI launcher backend
# (always on, regardless of login), and an XDG autostart .desktop that pops
# the Chrome window after login. Skip with KLYRA_SKIP_WEBUI=1 (e.g. headless
# servers).
if [ "${KLYRA_SKIP_WEBUI:-0}" = "1" ]; then
    log_info "KLYRA_SKIP_WEBUI=1, skipping launcher auto-start"
else
    CLIENT_DIR="$KLYRA_INSTALL_DIR/client"
    WEBUI_SERVICE="/etc/systemd/system/klyra-webui.service"
    chmod +x "$CLIENT_DIR/web/window.sh" 2>/dev/null || true

    log_info "Creating $WEBUI_SERVICE..."
    sudo tee "$WEBUI_SERVICE" > /dev/null <<EOF
[Unit]
Description=Klyra Launcher Webui (FastAPI backend on localhost:8080)
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CLIENT_DIR
ExecStart=$CLIENT_DIR/venv/bin/python $CLIENT_DIR/web/server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    if sudo systemctl enable klyra-webui.service >/dev/null 2>&1; then
        log_success "klyra-webui.service enabled"
    else
        log_warning "Failed to enable klyra-webui.service"
    fi
    if sudo systemctl restart klyra-webui.service; then
        log_success "klyra-webui.service started on http://localhost:8080"
    else
        log_warning "Failed to start klyra-webui.service (check: sudo journalctl -u klyra-webui -n 30)"
    fi

    # XDG autostart entry — only fires in graphical sessions (no-op on headless).
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/klyra-launcher.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Klyra Launcher
Comment=Klyra home screen
Exec=/bin/bash $CLIENT_DIR/web/window.sh
X-GNOME-Autostart-enabled=true
Terminal=false
NoDisplay=false
EOF
    log_success "Autostart entry: $AUTOSTART_DIR/klyra-launcher.desktop"
fi

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

if [ -f "vosk-model-small-en-us-0.15/conf/mfcc.conf" ]; then
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
    log_info "  Update:   sudo $KLYRA_INSTALL_DIR/client/run_update.sh"
else
    log_error "=========================================="
    log_error "  $FAIL_COUNT critical check(s) failed — see above"
    log_error "=========================================="
    exit 1
fi
