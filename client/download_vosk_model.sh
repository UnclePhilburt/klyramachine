#!/bin/bash
# Download Vosk model for offline wake word detection

set -e  # Exit on error

# Colors
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
echo "  VOSK MODEL DOWNLOADER"
echo "=========================================="
echo ""

MODEL_NAME="vosk-model-small-en-us-0.15"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
MODEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info "Model: $MODEL_NAME"
log_info "Size: ~40MB"
log_info "Location: $MODEL_DIR/$MODEL_NAME"
log_info "Download URL: $MODEL_URL"
echo ""

# Check if model already exists and is complete
if [ -d "$MODEL_DIR/$MODEL_NAME" ]; then
    log_info "Model directory exists, checking if complete..."

    if [ -f "$MODEL_DIR/$MODEL_NAME/mfcc.conf" ]; then
        log_success "Model already downloaded and complete!"
        log_info "Model size: $(du -sh $MODEL_DIR/$MODEL_NAME | cut -f1)"
        log_info "Files in model:"
        ls -lh "$MODEL_DIR/$MODEL_NAME" | head -10
        exit 0
    else
        log_warning "Model directory exists but incomplete!"
        log_info "Removing incomplete model..."
        rm -rf "$MODEL_DIR/$MODEL_NAME"
    fi
fi

# Check for download tools
log_info "Checking for download tools..."
HAS_WGET=false
HAS_CURL=false

if command -v wget &> /dev/null; then
    log_success "wget is available"
    HAS_WGET=true
    wget --version | head -1
fi

if command -v curl &> /dev/null; then
    log_success "curl is available"
    HAS_CURL=true
    curl --version | head -1
fi

if [ "$HAS_WGET" = false ] && [ "$HAS_CURL" = false ]; then
    log_error "Neither wget nor curl found!"
    log_info "Installing wget..."
    sudo apt update && sudo apt install -y wget
    HAS_WGET=true
fi

# Check for unzip
if ! command -v unzip &> /dev/null; then
    log_warning "unzip not found, installing..."
    sudo apt update && sudo apt install -y unzip
fi

echo ""
log_info "Downloading Vosk model..."
log_info "This may take a few minutes on slow connections..."
log_info "Download size: ~40MB"
echo ""

# Download with progress
if [ "$HAS_WGET" = true ]; then
    log_info "Using wget to download..."
    if wget --show-progress -O "$MODEL_DIR/${MODEL_NAME}.zip" "$MODEL_URL" 2>&1; then
        log_success "Download completed!"
    else
        log_error "wget download failed!"
        exit 1
    fi
elif [ "$HAS_CURL" = true ]; then
    log_info "Using curl to download..."
    if curl -L --progress-bar -o "$MODEL_DIR/${MODEL_NAME}.zip" "$MODEL_URL" 2>&1; then
        log_success "Download completed!"
    else
        log_error "curl download failed!"
        exit 1
    fi
fi

# Verify download
if [ ! -f "$MODEL_DIR/${MODEL_NAME}.zip" ]; then
    log_error "Download failed - zip file not found!"
    exit 1
fi

DOWNLOAD_SIZE=$(ls -lh "$MODEL_DIR/${MODEL_NAME}.zip" | awk '{print $5}')
log_info "Downloaded file size: $DOWNLOAD_SIZE"

# Check if file is too small (likely error page)
FILE_SIZE=$(stat -c%s "$MODEL_DIR/${MODEL_NAME}.zip" 2>/dev/null || stat -f%z "$MODEL_DIR/${MODEL_NAME}.zip" 2>/dev/null)
if [ "$FILE_SIZE" -lt 1000000 ]; then
    log_error "Downloaded file is too small ($DOWNLOAD_SIZE) - download may have failed!"
    log_info "Contents of downloaded file:"
    head -20 "$MODEL_DIR/${MODEL_NAME}.zip"
    rm "$MODEL_DIR/${MODEL_NAME}.zip"
    exit 1
fi

# Extract model
echo ""
log_info "Extracting model..."
log_info "Extraction directory: $MODEL_DIR"

cd "$MODEL_DIR"

if unzip -o "${MODEL_NAME}.zip" 2>&1 | tee /tmp/vosk-extract.log; then
    log_success "Extraction completed!"
else
    log_error "Extraction failed!"
    cat /tmp/vosk-extract.log
    exit 1
fi

# Verify extraction
if [ -d "$MODEL_DIR/$MODEL_NAME" ]; then
    log_success "Model directory created"

    if [ -f "$MODEL_DIR/$MODEL_NAME/mfcc.conf" ]; then
        log_success "Model verification passed (mfcc.conf found)"
    else
        log_error "Model verification failed - mfcc.conf not found!"
        log_info "Contents of model directory:"
        ls -lah "$MODEL_DIR/$MODEL_NAME"
        exit 1
    fi
else
    log_error "Model directory not created after extraction!"
    log_info "Contents of current directory:"
    ls -lah "$MODEL_DIR"
    exit 1
fi

# Cleanup
log_info "Cleaning up..."
rm "${MODEL_NAME}.zip"
log_success "Cleanup done"

echo ""
log_success "✓ Vosk model installed successfully!"
log_info "Location: $MODEL_DIR/$MODEL_NAME"
log_info "Model size: $(du -sh $MODEL_DIR/$MODEL_NAME | cut -f1)"
log_info "Files in model:"
ls -lh "$MODEL_DIR/$MODEL_NAME" | head -10
echo ""
log_success "You can now run: python client_vosk.py"
log_success "Or use: ./start_klyra.sh (will auto-detect Vosk)"
echo ""
