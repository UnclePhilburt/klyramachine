#!/bin/bash
# Build Qt 6 WebEngine with proprietary codecs (AAC, H.264, MP3) and slot
# the resulting libs into the client venv's PyQt6-Qt6 install.
#
# This unlocks Spotify, YouTube, Netflix, etc. inside klyra_display.py's
# embedded web views — the open-source QtWebEngine that ships from PyPI
# can't decode those codecs.
#
# REALITY CHECK before you start:
#   • Build time: 3-4 hours on a modern desktop (mostly QtWebEngine).
#   • Disk usage: ~15 GB during build, ~3 GB after.
#   • Network: ~700 MB Qt source download.
#   • Sudo: required for apt-get install of build deps and for installing
#     the result to /opt/qt6-codecs.
#   • Risk: ABI mismatch with PyQt6's Python bindings is possible. We back
#     up the venv's WebEngine libs first and the script tells you how to
#     restore if the new build doesn't load.
#
# Usage: ./build_qt_with_codecs.sh

set -e
set -o pipefail

QT_VERSION=6.11.0
QT_MAJMIN=6.11
PREFIX=/opt/qt6-codecs
SRC_DIR="$HOME/qt-build"
JOBS=$(nproc)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG="$SCRIPT_DIR/build_qt_with_codecs.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo; echo -e "${GREEN}========================================${NC}"; echo -e "${GREEN}$1${NC}"; echo -e "${GREEN}========================================${NC}"; }

# Detect venv Qt6 location
PYVER=$(ls "$SCRIPT_DIR/venv/lib/" 2>/dev/null | grep ^python | head -1)
VENV_QT_DIR="$SCRIPT_DIR/venv/lib/$PYVER/site-packages/PyQt6/Qt6"
if [ ! -d "$VENV_QT_DIR" ]; then
    log_error "Venv Qt6 dir not found at $VENV_QT_DIR"
    log_error "Run from $SCRIPT_DIR (the client directory) with PyQt6 installed in venv."
    exit 1
fi

echo "=========================================="
echo "  Qt 6 + proprietary codecs build"
echo "=========================================="
log_info "Qt version:   $QT_VERSION  (matching PyQt6-Qt6 installed in venv)"
log_info "Prefix:       $PREFIX"
log_info "Source dir:   $SRC_DIR"
log_info "Venv target:  $VENV_QT_DIR"
log_info "Parallel:     $JOBS jobs"
log_info "Log file:     $LOG"
echo

# Disk-space sanity (need ~15 GB free in $HOME)
FREE_GB=$(df --output=avail -BG "$HOME" | tail -1 | tr -dc '0-9')
if [ "${FREE_GB:-0}" -lt 20 ]; then
    log_warn "Less than 20 GB free in $HOME — build needs ~15 GB. You may run out."
fi

read -r -p "Continue? This takes 3-4 hours. [y/N] " ans
case "$ans" in
    y|Y|yes|Yes) ;;
    *) log_info "Aborted."; exit 0 ;;
esac

# All output past this point also goes into the log file.
exec > >(tee -a "$LOG") 2>&1

START_TIME=$(date +%s)
log_info "Started at: $(date)"

# ----------------------------------------------------------------------------
log_step "STEP 1: Install apt build deps"
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake ninja-build perl python3 python3-html5lib \
    libgl1-mesa-dev libglu1-mesa-dev mesa-common-dev libegl1-mesa-dev \
    libfontconfig1-dev libfreetype6-dev \
    libx11-dev libx11-xcb-dev libxext-dev libxfixes-dev \
    libxi-dev libxrender-dev libxcb1-dev libxcb-glx0-dev \
    libxcb-keysyms1-dev libxcb-image0-dev libxcb-shm0-dev \
    libxcb-icccm4-dev libxcb-sync-dev libxcb-xfixes0-dev \
    libxcb-shape0-dev libxcb-randr0-dev libxcb-render-util0-dev \
    libxcb-util-dev libxcb-cursor-dev libxkbcommon-dev \
    libxkbcommon-x11-dev libxshmfence-dev libdrm-dev \
    libnss3-dev libdbus-1-dev libssl-dev libsqlite3-dev \
    libpulse-dev libasound2-dev libcups2-dev \
    libxml2-dev libxslt1-dev libwebp-dev libjpeg-dev libpng-dev \
    libopus-dev libsnappy-dev libxss-dev libavcodec-dev \
    libavformat-dev libswresample-dev \
    bison flex gperf nodejs

# ----------------------------------------------------------------------------
log_step "STEP 2: Download Qt $QT_VERSION source"
mkdir -p "$SRC_DIR"
cd "$SRC_DIR"
TARBALL="qt-everywhere-src-$QT_VERSION.tar.xz"
URL="https://download.qt.io/official_releases/qt/$QT_MAJMIN/$QT_VERSION/single/$TARBALL"
if [ ! -f "$TARBALL" ]; then
    log_info "Downloading $URL ..."
    curl -fL -o "$TARBALL.partial" "$URL"
    mv "$TARBALL.partial" "$TARBALL"
fi
if [ ! -d "qt-everywhere-src-$QT_VERSION" ]; then
    log_info "Extracting (this is the slowest extract — ~3.5 GB)..."
    tar xf "$TARBALL"
fi

# ----------------------------------------------------------------------------
log_step "STEP 3: Configure Qt"
mkdir -p "$SRC_DIR/build"
cd "$SRC_DIR/build"

# Skip every Qt module we don't need. We're only after qtwebengine + its
# direct deps (qtbase, qtdeclarative, qtwebchannel, qtpositioning).
"$SRC_DIR/qt-everywhere-src-$QT_VERSION/configure" \
    -prefix "$PREFIX" \
    -opensource -confirm-license \
    -release \
    -nomake examples -nomake tests \
    -skip qt3d -skip qt5compat -skip qtactiveqt -skip qtcharts \
    -skip qtcoap -skip qtconnectivity -skip qtdatavis3d \
    -skip qtgrpc -skip qthttpserver -skip qtlanguageserver \
    -skip qtlocation -skip qtlottie -skip qtmultimedia \
    -skip qtnetworkauth -skip qtopcua -skip qtquick3d \
    -skip qtquick3dphysics -skip qtquickeffectmaker \
    -skip qtquicktimeline -skip qtremoteobjects -skip qtscxml \
    -skip qtsensors -skip qtserialbus -skip qtserialport \
    -skip qtshadertools -skip qtspeech -skip qtsvg \
    -skip qttranslations -skip qtvirtualkeyboard -skip qtwayland \
    -skip qtwebsockets -skip qtwebview \
    -- -DQT_FEATURE_webengine_proprietary_codecs=ON \
       -DQT_FEATURE_webengine_system_ffmpeg=OFF

# ----------------------------------------------------------------------------
log_step "STEP 4: Build (this is the long part — go get coffee)"
log_info "Build start: $(date)"
cmake --build . --parallel "$JOBS"
log_info "Build end:   $(date)"

# ----------------------------------------------------------------------------
log_step "STEP 5: Install to $PREFIX"
sudo cmake --install .

# ----------------------------------------------------------------------------
log_step "STEP 6: Slot QtWebEngine into the venv"

# 6a — back up the venv's existing WebEngine bits so we can roll back.
BACKUP_DIR="$VENV_QT_DIR/.backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR/lib" "$BACKUP_DIR/libexec" "$BACKUP_DIR/resources" "$BACKUP_DIR/translations"
log_info "Backing up existing WebEngine files to $BACKUP_DIR"
for f in "$VENV_QT_DIR/lib/"libQt6WebEngine*; do
    [ -e "$f" ] && cp -P "$f" "$BACKUP_DIR/lib/"
done
[ -f "$VENV_QT_DIR/libexec/QtWebEngineProcess" ] && \
    cp -P "$VENV_QT_DIR/libexec/QtWebEngineProcess" "$BACKUP_DIR/libexec/"
[ -d "$VENV_QT_DIR/resources" ] && \
    cp -r "$VENV_QT_DIR/resources/"* "$BACKUP_DIR/resources/" 2>/dev/null || true
[ -d "$VENV_QT_DIR/translations/qtwebengine_locales" ] && \
    cp -r "$VENV_QT_DIR/translations/qtwebengine_locales" "$BACKUP_DIR/translations/" 2>/dev/null || true

# 6b — copy our build's WebEngine libs over the venv's.
log_info "Copying libQt6WebEngine*.so*"
for f in "$PREFIX/lib/"libQt6WebEngine*.so*; do
    [ -e "$f" ] && cp -P "$f" "$VENV_QT_DIR/lib/"
done

# QtWebEngineProcess lives at libexec/ in modern Qt installs.
log_info "Copying QtWebEngineProcess"
mkdir -p "$VENV_QT_DIR/libexec"
PROC_CANDIDATES=(
    "$PREFIX/libexec/QtWebEngineProcess"
    "$PREFIX/lib/qt6/libexec/QtWebEngineProcess"
    "$PREFIX/bin/QtWebEngineProcess"
)
for c in "${PROC_CANDIDATES[@]}"; do
    if [ -x "$c" ]; then
        cp "$c" "$VENV_QT_DIR/libexec/QtWebEngineProcess"
        log_success "Used $c"
        break
    fi
done

# Resources (.pak, icudtl.dat, v8 snapshots) — required at runtime.
log_info "Copying QtWebEngine resources"
RES_CANDIDATES=(
    "$PREFIX/resources"
    "$PREFIX/share/qt6/resources"
)
for c in "${RES_CANDIDATES[@]}"; do
    if [ -d "$c" ]; then
        mkdir -p "$VENV_QT_DIR/resources"
        cp -r "$c/"* "$VENV_QT_DIR/resources/" 2>/dev/null || true
        log_success "Used $c"
        break
    fi
done

# Translations (locale .pak files for the web UI).
log_info "Copying qtwebengine_locales"
LOC_CANDIDATES=(
    "$PREFIX/translations/qtwebengine_locales"
    "$PREFIX/share/qt6/translations/qtwebengine_locales"
)
for c in "${LOC_CANDIDATES[@]}"; do
    if [ -d "$c" ]; then
        mkdir -p "$VENV_QT_DIR/translations"
        cp -r "$c" "$VENV_QT_DIR/translations/" 2>/dev/null || true
        break
    fi
done

# ----------------------------------------------------------------------------
log_step "STEP 7: Verify"
log_info "Smoke test: import QtWebEngine in the venv..."
if "$SCRIPT_DIR/venv/bin/python" -c "
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
print('imports OK')
"; then
    log_success "QtWebEngine imports cleanly with the rebuilt libs."
else
    log_error "Import test FAILED. To restore the original libs:"
    log_error "  cp -P $BACKUP_DIR/lib/* $VENV_QT_DIR/lib/"
    log_error "  cp $BACKUP_DIR/libexec/QtWebEngineProcess $VENV_QT_DIR/libexec/"
    log_error "  cp -r $BACKUP_DIR/resources/* $VENV_QT_DIR/resources/"
    exit 1
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
HOURS=$((ELAPSED / 3600))
MIN=$(( (ELAPSED % 3600) / 60 ))

echo
log_success "=========================================="
log_success "  Build complete (${HOURS}h ${MIN}m)"
log_success "=========================================="
log_info "Test it: python klyra_display.py"
log_info "Open the Music tile — Spotify should now play audio."
log_info ""
log_info "If something is broken, restore the originals:"
log_info "  cp -P $BACKUP_DIR/lib/* $VENV_QT_DIR/lib/"
log_info "  cp $BACKUP_DIR/libexec/QtWebEngineProcess $VENV_QT_DIR/libexec/"
log_info "  cp -r $BACKUP_DIR/resources/* $VENV_QT_DIR/resources/"
echo
