#!/bin/bash
# Download a Piper voice for offline text-to-speech.
# Default voice: en_US-lessac-medium (~63MB). Override with VOICE=name env var.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=========================================="
echo "  PIPER VOICE DOWNLOADER"
echo "=========================================="
echo ""

# Voice naming: <lang>-<voice>-<quality>. The HuggingFace path encodes the
# same parts: <lang_code>/<lang_locale>/<voice>/<quality>.
VOICE="${VOICE:-en_US-lessac-medium}"
LANG_CODE="${VOICE%%_*}"          # en
LOCALE="${VOICE%%-*}"             # en_US
REST="${VOICE#*-}"                # lessac-medium
VOICE_NAME="${REST%-*}"           # lessac
QUALITY="${REST##*-}"             # medium

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOICE_DIR="$SCRIPT_DIR/voices"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/${LANG_CODE}/${LOCALE}/${VOICE_NAME}/${QUALITY}"
ONNX_URL="${BASE_URL}/${VOICE}.onnx"
JSON_URL="${BASE_URL}/${VOICE}.onnx.json"

log_info "Voice: $VOICE"
log_info "Location: $VOICE_DIR"
log_info "ONNX URL: $ONNX_URL"
echo ""

mkdir -p "$VOICE_DIR"

ONNX_PATH="$VOICE_DIR/${VOICE}.onnx"
JSON_PATH="$VOICE_DIR/${VOICE}.onnx.json"

# Skip if both files exist and the .onnx looks the right size (>10MB).
if [ -f "$ONNX_PATH" ] && [ -f "$JSON_PATH" ]; then
    SIZE=$(stat -c%s "$ONNX_PATH" 2>/dev/null || stat -f%z "$ONNX_PATH" 2>/dev/null)
    if [ "$SIZE" -gt 10000000 ]; then
        log_success "Voice already installed ($(du -sh "$ONNX_PATH" | cut -f1))"
        exit 0
    fi
    log_warning "Existing .onnx is suspiciously small — re-downloading"
    rm -f "$ONNX_PATH" "$JSON_PATH"
fi

# Pick downloader
if command -v wget &>/dev/null; then
    DL="wget --show-progress -q -O"
elif command -v curl &>/dev/null; then
    DL="curl -L --progress-bar -o"
else
    log_info "Installing wget..."
    sudo apt update && sudo apt install -y wget
    DL="wget --show-progress -q -O"
fi

log_info "Downloading $VOICE.onnx (~63MB)..."
if ! $DL "$ONNX_PATH" "$ONNX_URL"; then
    log_error "Download failed for $ONNX_URL"
    exit 1
fi

log_info "Downloading $VOICE.onnx.json..."
if ! $DL "$JSON_PATH" "$JSON_URL"; then
    log_error "Download failed for $JSON_URL"
    exit 1
fi

# Sanity check: .onnx should be much bigger than the .json
SIZE=$(stat -c%s "$ONNX_PATH" 2>/dev/null || stat -f%z "$ONNX_PATH" 2>/dev/null)
if [ "$SIZE" -lt 10000000 ]; then
    log_error "Downloaded .onnx is too small ($SIZE bytes) — likely an error page"
    head -5 "$ONNX_PATH" || true
    rm -f "$ONNX_PATH" "$JSON_PATH"
    exit 1
fi

echo ""
log_success "✓ Piper voice installed: $VOICE"
log_info "  $ONNX_PATH  ($(du -sh "$ONNX_PATH" | cut -f1))"
log_info "  $JSON_PATH"
echo ""
log_info "config.json should set:"
log_info '  "tts_engine": "local",'
log_info "  \"piper_voice\": \"voices/${VOICE}.onnx\""
