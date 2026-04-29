#!/bin/bash
# klyra-doctor — diagnostic / health-check script
#
# Runs the same pre-flight checks the installer does, anytime. Useful for
# remote debugging: "ssh in and run klyra-doctor.sh" gives you a one-page
# summary of what's working and what isn't.
#
# Exit code: 0 if no failures, 1 if any failures.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'; NC=$'\033[0m'

echo "=========================================="
echo "  KLYRA DOCTOR"
echo "=========================================="
echo "Run at: $(date)"
echo "Host:   $(hostname) ($(uname -m))"
[ -f /proc/device-tree/model ] && echo "Model:  $(tr -d '\0' < /proc/device-tree/model)"
echo

PASS=0; WARN=0; FAIL=0
pass() { echo "${GREEN}[OK]${NC}   $1"; PASS=$((PASS+1)); }
warn() { echo "${YELLOW}[WARN]${NC} $1"; WARN=$((WARN+1)); }
fail() { echo "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); }
info() { echo "${BLUE}[INFO]${NC} $1"; }

# -- config.json --------------------------------------------------------------
echo "=== config ==="
if [ -f "config.json" ]; then
    SERVER_URL=$(python3 -c "import json;print(json.load(open('config.json'))['server_url'])" 2>/dev/null || echo "")
    CLIENT_ID=$(python3 -c "import json;print(json.load(open('config.json'))['client_id'])" 2>/dev/null || echo "")
    [ -n "$CLIENT_ID" ] && pass "client_id: $CLIENT_ID" || fail "client_id missing from config.json"
    [ -n "$SERVER_URL" ] && pass "server_url: $SERVER_URL" || fail "server_url missing"
else
    fail "config.json not found in $SCRIPT_DIR"
    SERVER_URL=""
fi
echo

# -- system resources ---------------------------------------------------------
echo "=== resources ==="
RAM_MB=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1024 ))
SWAP_MB=$(( $(awk '/^SwapTotal:/ {print $2}' /proc/meminfo) / 1024 ))
AVAIL_MB=$(( $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) / 1024 ))
info "RAM total: ${RAM_MB} MB, available: ${AVAIL_MB} MB, swap: ${SWAP_MB} MB"
if [ "$RAM_MB" -lt 2048 ] && [ "$SWAP_MB" -lt 1024 ]; then
    warn "low RAM with no swap — Klyra may OOM under load (run easy_install.sh again to add swap)"
else
    pass "memory headroom looks ok"
fi
DISK_FREE_MB=$(df -m . | awk 'NR==2 {print $4}')
if [ "$DISK_FREE_MB" -lt 500 ]; then
    fail "disk free: ${DISK_FREE_MB} MB (under 500 MB — auto-update may fail)"
else
    pass "disk free: ${DISK_FREE_MB} MB"
fi
echo

# -- network ------------------------------------------------------------------
echo "=== network ==="
if getent hosts github.com >/dev/null 2>&1; then
    pass "DNS works (github.com resolves)"
else
    fail "DNS failed (github.com does not resolve)"
fi
if [ -n "$SERVER_URL" ]; then
    if curl -fsSL --max-time 15 "$SERVER_URL/" >/dev/null 2>&1; then
        pass "Render server reachable: $SERVER_URL"
    else
        warn "Render server unreachable (may be asleep; will wake on first request)"
    fi
fi
echo

# -- audio --------------------------------------------------------------------
echo "=== audio ==="
if dpkg -l 2>/dev/null | awk '/^ii/ {print $2}' | grep -qE '^(pulseaudio|pipewire-pulse)$'; then
    info "user-session audio: PulseAudio/PipeWire installed"
else
    info "user-session audio: none (bare ALSA)"
fi
CARD_COUNT=0
for d in /proc/asound/card*; do
    [ -d "$d" ] && CARD_COUNT=$((CARD_COUNT+1))
done
if [ "$CARD_COUNT" -eq 0 ]; then
    fail "no ALSA cards found (no audio hardware?)"
else
    pass "ALSA cards: $CARD_COUNT"
    arecord -l 2>/dev/null | grep -E "^card" | sed 's/^/      /' || info "      (arecord not installed — install alsa-utils for device listing)"
fi
if [ -f /etc/asound.conf ]; then
    DEFAULT_CARD=$(grep -oE 'card [0-9]+' /etc/asound.conf | head -1 | awk '{print $2}')
    info "/etc/asound.conf pins default card: ${DEFAULT_CARD:-unknown}"
fi

# Python-level audio probe (the path Klyra actually uses)
if [ -x venv/bin/python ]; then
    MIC_INFO=$(venv/bin/python - <<'PY' 2>/dev/null
try:
    import pyaudio
    p = pyaudio.PyAudio()
    inputs = []
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d['maxInputChannels'] > 0:
            inputs.append(f"#{i} {d['name']}")
    p.terminate()
    print(f"COUNT={len(inputs)}")
    for name in inputs:
        print(f"DEV={name}")
except Exception as e:
    print(f"ERR={e}")
PY
    )
    MIC_COUNT=$(echo "$MIC_INFO" | awk -F= '/^COUNT=/ {print $2}')
    if [ "${MIC_COUNT:-0}" -gt 0 ]; then
        pass "PyAudio sees $MIC_COUNT input device(s)"
        echo "$MIC_INFO" | awk -F= '/^DEV=/ {print "      " $2}'
    elif echo "$MIC_INFO" | grep -q "^ERR="; then
        fail "PyAudio probe failed: $(echo "$MIC_INFO" | sed -n 's/^ERR=//p')"
    else
        fail "PyAudio sees no input devices"
    fi
fi
echo

# -- camera -------------------------------------------------------------------
echo "=== camera ==="
if ls /dev/video* >/dev/null 2>&1; then
    info "video devices: $(ls /dev/video* | tr '\n' ' ')"
    if id -nG "$USER" 2>/dev/null | grep -qw video; then
        pass "user '$USER' is in 'video' group"
    else
        warn "user '$USER' is NOT in 'video' group — camera access may fail (sudo usermod -aG video $USER && re-login)"
    fi
    if [ -x venv/bin/python ]; then
        if venv/bin/python -c "import cv2; c=cv2.VideoCapture(0); ok=c.isOpened(); c.release(); exit(0 if ok else 1)" 2>/dev/null; then
            pass "OpenCV opens /dev/video0"
        else
            warn "OpenCV cannot open /dev/video0 (in use? wrong index? CSI ribbon cam needs USB)"
        fi
    fi
else
    warn "no /dev/video* found — Klyra will skip vision (set enable_camera: false to silence)"
fi
echo

# -- vosk model ---------------------------------------------------------------
echo "=== wake word ==="
if [ -f "vosk-model-small-en-us-0.15/conf/mfcc.conf" ]; then
    pass "Vosk model complete"
else
    warn "Vosk model missing/incomplete — wake word will fall back to cloud Whisper (slower)"
fi
echo

# -- service ------------------------------------------------------------------
echo "=== service ==="
if systemctl list-unit-files klyra.service >/dev/null 2>&1; then
    pass "klyra.service installed"
    if systemctl is-enabled klyra.service >/dev/null 2>&1; then
        pass "klyra.service enabled at boot"
    else
        warn "klyra.service NOT enabled at boot"
    fi
    if systemctl is-active klyra.service >/dev/null 2>&1; then
        pass "klyra.service running ($(systemctl show -p ActiveEnterTimestamp --value klyra.service))"
    else
        fail "klyra.service NOT running"
        echo "      Last 5 log lines:"
        journalctl -u klyra.service -n 5 --no-pager 2>/dev/null | sed 's/^/        /'
    fi
    if systemctl list-unit-files klyra-update.timer >/dev/null 2>&1 \
       && systemctl is-active klyra-update.timer >/dev/null 2>&1; then
        pass "auto-update timer active"
    elif crontab -l 2>/dev/null | grep -q auto_update; then
        pass "auto-update via cron"
    else
        warn "auto-update not scheduled"
    fi
else
    warn "klyra.service not installed (run install_service.sh)"
fi
echo

# -- summary ------------------------------------------------------------------
echo "=========================================="
echo "  ${GREEN}Pass: $PASS${NC}   ${YELLOW}Warn: $WARN${NC}   ${RED}Fail: $FAIL${NC}"
echo "=========================================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
