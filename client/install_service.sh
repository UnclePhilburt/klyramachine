#!/bin/bash
# Install Klyra as a systemd service on Raspberry Pi

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

echo ""
echo "=========================================="
echo "  KLYRA SERVICE INSTALLER"
echo "=========================================="
echo ""

log_info "Starting service installation..."
log_info "Timestamp: $(date)"

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
log_info "Script directory: $SCRIPT_DIR"
log_info "Current user: $USER"
log_info "Home directory: $HOME"

# Verify required files exist
log_info "Verifying required files..."
if [ -f "$SCRIPT_DIR/client_wake_improved.py" ]; then
    log_success "client_wake_improved.py found"
else
    log_error "client_wake_improved.py not found!"
    exit 1
fi

if [ -d "$SCRIPT_DIR/venv" ]; then
    log_success "venv directory found"
    log_info "Python: $SCRIPT_DIR/venv/bin/python"
    $SCRIPT_DIR/venv/bin/python --version
else
    log_error "venv directory not found!"
    exit 1
fi

# Update the service file with the correct path
SERVICE_FILE="/etc/systemd/system/klyra.service"
log_info "Creating service file: $SERVICE_FILE"

# Create the service file with correct paths
log_info "Service configuration:"
log_info "  User: $USER"
log_info "  WorkingDirectory: $SCRIPT_DIR"
log_info "  ExecStart: $SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/client_wake_improved.py"

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Klyra AI Companion
After=network.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/client_wake_improved.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment variables
Environment="PYTHONUNBUFFERED=1"
Environment="DISPLAY=:0"

[Install]
WantedBy=multi-user.target
EOF

if [ -f "$SERVICE_FILE" ]; then
    log_success "Service file created: $SERVICE_FILE"
    log_info "Service file contents:"
    sudo cat $SERVICE_FILE
else
    log_error "Failed to create service file"
    exit 1
fi

# Reload systemd
log_info "Reloading systemd daemon..."
if sudo systemctl daemon-reload; then
    log_success "Systemd daemon reloaded"
else
    log_error "Failed to reload systemd daemon"
    exit 1
fi

# Verify service file
log_info "Verifying service file syntax..."
if systemd-analyze verify $SERVICE_FILE 2>&1; then
    log_success "Service file syntax is valid"
else
    log_warning "Service file validation warnings (may be non-critical)"
fi

# Enable the service (start on boot)
log_info "Enabling klyra.service to start on boot..."
if sudo systemctl enable klyra.service 2>&1; then
    log_success "klyra.service enabled"
else
    log_error "Failed to enable klyra.service"
    exit 1
fi

echo ""
log_success "Klyra service installed successfully!"
echo ""

echo ""
log_info "=========================================="
log_info "Installing Auto-Update Service..."
log_info "=========================================="
echo ""

# Make auto-update script executable first
log_info "Making auto_update.sh executable..."
if chmod +x $SCRIPT_DIR/auto_update.sh 2>&1; then
    log_success "auto_update.sh is now executable"
    ls -lh $SCRIPT_DIR/auto_update.sh
else
    log_warning "Could not make auto_update.sh executable"
fi

# Try to install auto-update, but don't fail if it doesn't work
if command -v systemctl &> /dev/null; then
    log_info "systemd detected, creating auto-update service..."

    # Create auto-update service file
    UPDATE_SERVICE="/etc/systemd/system/klyra-update.service"
    log_info "Creating auto-update service: $UPDATE_SERVICE"
    sudo tee $UPDATE_SERVICE > /dev/null <<SERVICEEOF
[Unit]
Description=Klyra Auto-Update
After=network.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$SCRIPT_DIR/..
ExecStart=/bin/bash $SCRIPT_DIR/auto_update.sh
StandardOutput=journal
StandardError=journal
SERVICEEOF

    if [ -f "$UPDATE_SERVICE" ]; then
        log_success "Auto-update service file created"
        log_info "Service file contents:"
        sudo cat $UPDATE_SERVICE
    else
        log_error "Failed to create auto-update service"
    fi

    # Verify the service file exists before creating timer
    if [ ! -f "$UPDATE_SERVICE" ]; then
        log_error "Auto-update service file not found at $UPDATE_SERVICE"
        log_info "Skipping timer creation"
    else
        # Create auto-update timer file
        UPDATE_TIMER="/etc/systemd/system/klyra-update.timer"
        log_info "Creating auto-update timer: $UPDATE_TIMER"
        sudo tee $UPDATE_TIMER > /dev/null <<TIMEREOF
[Unit]
Description=Klyra Auto-Update Timer
After=multi-user.target

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
Unit=klyra-update.service
Persistent=true

[Install]
WantedBy=timers.target
TIMEREOF
    fi

    if [ -f "$UPDATE_TIMER" ]; then
        log_success "Auto-update timer file created"
        log_info "Timer file contents:"
        sudo cat $UPDATE_TIMER
    else
        log_error "Failed to create auto-update timer"
    fi

    # Reload systemd
    log_info "Reloading systemd daemon for new timer..."
    if sudo systemctl daemon-reload 2>&1; then
        log_success "Systemd daemon reloaded"
    else
        log_error "Failed to reload systemd daemon"
    fi

    # Verify the timer file is valid
    log_info "Verifying timer file syntax..."
    if systemd-analyze verify $UPDATE_TIMER 2>&1; then
        log_success "Timer file syntax is valid"
    else
        log_warning "Timer file validation warnings:"
        systemd-analyze verify $UPDATE_TIMER 2>&1 || true
    fi

    # Verify the service file is valid
    log_info "Verifying auto-update service syntax..."
    if systemd-analyze verify $UPDATE_SERVICE 2>&1; then
        log_success "Auto-update service syntax is valid"
    else
        log_warning "Service validation warnings:"
        systemd-analyze verify $UPDATE_SERVICE 2>&1 || true
    fi

    # Try to enable timer - THIS IS MANDATORY
    echo ""
    log_info "Enabling auto-update timer (REQUIRED)..."

    TIMER_ENABLE_OUTPUT=$(sudo systemctl enable klyra-update.timer 2>&1)
    TIMER_ENABLE_STATUS=$?

    if [ $TIMER_ENABLE_STATUS -eq 0 ]; then
        log_success "klyra-update.timer enabled"

        # Try to start timer
        log_info "Starting auto-update timer..."

        TIMER_START_OUTPUT=$(sudo systemctl start klyra-update.timer 2>&1)
        TIMER_START_STATUS=$?

        if [ $TIMER_START_STATUS -eq 0 ]; then
            log_success "Auto-update timer started successfully!"
            echo ""
            log_info "Timer status:"
            sudo systemctl status klyra-update.timer --no-pager --lines=10 || true
            echo ""
            log_info "Timer schedule:"
            sudo systemctl list-timers klyra-update.timer --no-pager || true
            AUTO_UPDATE_WORKING=true
        else
            log_error "Systemd timer failed to start!"
            log_info "Error output:"
            echo "$TIMER_START_OUTPUT"
            log_info "Checking journal for details..."
            sudo journalctl -u klyra-update.timer -n 20 --no-pager 2>&1 || true
            AUTO_UPDATE_WORKING=false
        fi
    else
        log_error "Systemd timer failed to enable!"
        log_info "Error output:"
        echo "$TIMER_ENABLE_OUTPUT"
        AUTO_UPDATE_WORKING=false
    fi

    # If systemd timer failed, fall back to cron (MANDATORY AUTO-UPDATE)
    if [ "$AUTO_UPDATE_WORKING" != "true" ]; then
        echo ""
        log_warning "Systemd timer failed - falling back to cron..."
        log_info "Installing cron-based auto-update (runs every hour)..."

        # Create cron job
        CRON_JOB="0 * * * * cd $SCRIPT_DIR/.. && $SCRIPT_DIR/auto_update.sh >> /tmp/klyra-update.log 2>&1"

        # Add to crontab if not already there
        (crontab -l 2>/dev/null | grep -v "klyra-update.sh" ; echo "$CRON_JOB") | crontab -

        if [ $? -eq 0 ]; then
            log_success "Cron-based auto-update installed!"
            log_info "Updates will run every hour via cron"
            log_info "Cron job added:"
            echo "  $CRON_JOB"
            log_info "Check logs: tail -f /tmp/klyra-update.log"
            AUTO_UPDATE_WORKING=true
        else
            log_error "Failed to install cron fallback!"
            log_error "AUTO-UPDATE IS CRITICAL - PLEASE FIX MANUALLY"
            echo ""
            log_info "Manual setup required:"
            log_info "1. Run: crontab -e"
            log_info "2. Add this line:"
            echo "   $CRON_JOB"
            exit 1
        fi
    fi
else
    log_warning "systemd not available, skipping auto-update timer"
    log_info "You can manually update with: cd $SCRIPT_DIR/.. && git pull"
fi

echo ""
log_info "=========================================="
log_success "Service Installation Complete"
log_info "=========================================="
echo ""

# Ask about lockdown
log_info "Security lockdown (optional):"
log_info "  This will restrict file permissions for security"
read -p "Do you want to enable security lockdown? (yes/no): " lockdown_choice

if [ "$lockdown_choice" = "yes" ] || [ "$lockdown_choice" = "y" ]; then
    echo ""
    log_info "Applying security lockdown..."

    # Create a dedicated klyra user if it doesn't exist
    if ! id "klyra" &>/dev/null; then
        log_info "Creating 'klyra' system user..."
        if sudo useradd -r -s /bin/false klyra; then
            log_success "klyra user created"
        else
            log_error "Failed to create klyra user"
        fi
    else
        log_info "klyra user already exists"
    fi

    # Change ownership to klyra user
    log_info "Changing ownership to klyra user..."
    if sudo chown -R klyra:klyra "$SCRIPT_DIR/.."; then
        log_success "Ownership changed"
    fi

    # Restrict permissions
    log_info "Setting read-only permissions..."
    if sudo chmod -R 500 "$SCRIPT_DIR/.."; then
        log_success "Permissions restricted"
    fi

    # Make config.json unreadable except by klyra user
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        log_info "Securing config.json..."
        sudo chmod 400 "$SCRIPT_DIR/config.json"
        log_success "config.json secured"
    fi

    # Make conversation storage private
    if [ -d "$SCRIPT_DIR/../server/conversations" ]; then
        log_info "Securing conversations directory..."
        sudo chmod 700 "$SCRIPT_DIR/../server/conversations"
        log_success "conversations directory secured"
    fi

    # Hide .git directory
    if [ -d "$SCRIPT_DIR/../.git" ]; then
        log_info "Hiding .git directory..."
        sudo chmod 700 "$SCRIPT_DIR/../.git"
        log_success ".git directory hidden"
    fi

    echo ""
    log_success "Security lockdown enabled!"
    log_info "  - Code: Read-only for klyra user only"
    log_info "  - Config: Hidden from all users except klyra"
    log_info "  - Conversations: Private"
else
    log_info "Security lockdown skipped."
fi

echo ""
log_info "=========================================="
log_info "FINAL VERIFICATION"
log_info "=========================================="
echo ""

# Verify auto-update is actually working
log_info "Verifying auto-update system..."
if systemctl is-enabled klyra-update.timer &>/dev/null && systemctl is-active klyra-update.timer &>/dev/null; then
    log_success "Auto-update: ENABLED via systemd timer"
    sudo systemctl list-timers klyra-update.timer --no-pager | grep klyra-update || true
elif crontab -l 2>/dev/null | grep -q "klyra-update.sh"; then
    log_success "Auto-update: ENABLED via cron"
    log_info "Cron job:"
    crontab -l | grep "klyra-update.sh"
else
    log_error "AUTO-UPDATE NOT WORKING!"
    log_error "This is CRITICAL - installation cannot continue"
    exit 1
fi

echo ""
log_success "Auto-update verification PASSED!"
echo ""

echo "Commands:"
echo "  Start:   sudo systemctl start klyra"
echo "  Stop:    sudo systemctl stop klyra"
echo "  Restart: sudo systemctl restart klyra"
echo "  Status:  sudo systemctl status klyra"
echo "  Logs:    sudo journalctl -u klyra -f"
echo ""
echo "Auto-update:"
echo "  Manual update: cd $SCRIPT_DIR/.. && ./client/auto_update.sh"
if systemctl is-active klyra-update.timer &>/dev/null; then
    echo "  Update logs:   sudo journalctl -u klyra-update -f"
    echo "  Update status: sudo systemctl status klyra-update.timer"
else
    echo "  Update logs:   tail -f /tmp/klyra-update.log"
    echo "  Cron status:   crontab -l | grep klyra"
fi
echo ""
if [ "$lockdown_choice" = "yes" ] || [ "$lockdown_choice" = "y" ]; then
    echo "Security:"
    echo "  To undo lockdown: sudo chmod -R 755 $SCRIPT_DIR/.."
    echo ""
fi
echo "To start Klyra now, run: sudo systemctl start klyra"
