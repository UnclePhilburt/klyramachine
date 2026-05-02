#!/bin/bash
# Install Widevine CDM for QtWebEngine — required for Spotify Web Player
# (and any other DRM media) inside klyra_display.py.
#
# QtWebEngine ships without Widevine. We borrow it from Google Chrome's
# install, which provides libwidevinecdm.so under
# /opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/.
#
# Idempotent: skips Chrome install if already present, skips symlink if
# the destination already points at Widevine.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=========================================="
echo "  WIDEVINE CDM INSTALLER"
echo "=========================================="
echo ""

WV_PATH="/opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so"
QT_DIR="$HOME/.config/QtWebEngine/Default"

# Step 1: Install Google Chrome if Widevine isn't already on disk.
if [ -f "$WV_PATH" ]; then
    log_success "Widevine already present at $WV_PATH"
else
    log_info "Widevine not found — installing Google Chrome to provide it..."
    if ! command -v sudo >/dev/null 2>&1; then
        log_error "sudo not available; cannot install Chrome system-wide."
        exit 1
    fi

    TMP_DEB=$(mktemp --suffix=.deb)
    log_info "Downloading google-chrome-stable_current_amd64.deb..."
    if ! curl -fsSL -o "$TMP_DEB" \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb; then
        log_error "Failed to download Chrome .deb"
        rm -f "$TMP_DEB"
        exit 1
    fi

    log_info "Installing Chrome (sudo apt install)..."
    if ! sudo apt install -y "$TMP_DEB"; then
        log_error "Chrome install failed"
        rm -f "$TMP_DEB"
        exit 1
    fi
    rm -f "$TMP_DEB"

    if [ ! -f "$WV_PATH" ]; then
        log_error "Chrome installed but Widevine still not at $WV_PATH"
        log_info "Look for it under /opt/google/chrome/WidevineCdm/ and update this script."
        exit 1
    fi
    log_success "Widevine present at $WV_PATH"
fi

# Step 2: Symlink into QtWebEngine's lookup directory.
mkdir -p "$QT_DIR"
DEST="$QT_DIR/libwidevinecdm.so"

if [ -L "$DEST" ] && [ "$(readlink -f "$DEST")" = "$(readlink -f "$WV_PATH")" ]; then
    log_success "Symlink already in place: $DEST"
else
    log_info "Linking $DEST → $WV_PATH"
    rm -f "$DEST"
    ln -sf "$WV_PATH" "$DEST"
    log_success "Symlink created"
fi

echo ""
log_success "Widevine setup complete."
log_info "Spotify (and other DRM media) should now play in klyra_display.py."
echo ""
