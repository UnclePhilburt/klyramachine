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

# Get the current directory (absolute path)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
log_info "Script directory: $SCRIPT_DIR"

# Get the parent directory (normalized absolute path) - MUST be absolute, no relative paths
PARENT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
log_info "Parent directory: $PARENT_DIR"

# Verify PARENT_DIR is absolute (starts with /)
if [[ ! "$PARENT_DIR" =~ ^/ ]]; then
    log_error "PARENT_DIR is not absolute: $PARENT_DIR"
    log_info "Attempting to resolve..."
    PARENT_DIR="$(realpath "$SCRIPT_DIR/..")"
    log_info "Resolved to: $PARENT_DIR"
fi

log_info "Current user: $USER"
log_info "Home directory: $HOME"

# Resolve the install user's UID so the systemd service can find their
# Pulse/PipeWire socket at /run/user/$USER_UID/pulse/native. Harmless on Pi
# (ALSA-direct, ignores XDG_RUNTIME_DIR) but required on desktop Ubuntu
# where audio devices live behind a user-session socket.
USER_UID=$(id -u "$USER")
log_info "Install-user UID: $USER_UID"

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
ExecStart=/bin/bash $SCRIPT_DIR/start_klyra.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment variables
Environment="PYTHONUNBUFFERED=1"
Environment="DISPLAY=:0"
# Reach the install user's Pulse/PipeWire socket from the system service.
# Required on desktop Ubuntu; ignored by Pi ALSA-direct audio.
Environment="XDG_RUNTIME_DIR=/run/user/$USER_UID"
Environment="PULSE_RUNTIME_PATH=/run/user/$USER_UID/pulse"

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

# Enable user lingering so /run/user/$USER_UID/pulse/native exists at boot,
# before any login. Required on desktop Ubuntu so the service can reach the
# user's audio socket; harmless on Pi (ALSA-direct doesn't use it).
log_info "Enabling user lingering for $USER (so audio socket is reachable at boot)..."
if sudo loginctl enable-linger "$USER" 2>&1; then
    log_success "Lingering enabled for $USER"
else
    log_warning "loginctl enable-linger failed — fine on Pi, may break audio on Ubuntu"
fi

echo ""
log_success "Klyra service installed successfully!"
echo ""

echo ""
log_info "=========================================="
log_info "Installing Auto-Update Service..."
log_info "=========================================="
echo ""

# Make auto-update scripts executable first
log_info "Making auto-update scripts executable..."
chmod +x $SCRIPT_DIR/auto_update.sh 2>/dev/null && log_success "auto_update.sh is now executable" || log_warning "Could not chmod auto_update.sh"
chmod +x $SCRIPT_DIR/run_update.sh  2>/dev/null && log_success "run_update.sh is now executable"  || log_warning "Could not chmod run_update.sh"

if [ ! -f "$SCRIPT_DIR/run_update.sh" ]; then
    log_error "run_update.sh missing at $SCRIPT_DIR/run_update.sh — cannot install auto-update"
    exit 1
fi

# Try to install auto-update, but don't fail if it doesn't work
if command -v systemctl &> /dev/null; then
    log_info "systemd detected, creating auto-update service..."

    # Remove old service files if they exist (to avoid cached errors)
    UPDATE_SERVICE="/etc/systemd/system/klyra-update.service"
    if [ -f "$UPDATE_SERVICE" ]; then
        log_info "Removing old service file..."
        sudo rm -f "$UPDATE_SERVICE"
    fi

    log_info "Creating auto-update service: $UPDATE_SERVICE"
    # Runs as root: run_update.sh drops to the unprivileged repo owner for
    # the git pull, then restarts klyra.service if a marker was placed.
    sudo tee $UPDATE_SERVICE > /dev/null <<SERVICEEOF
[Unit]
Description=Klyra Auto-Update
After=network.target

[Service]
Type=oneshot
WorkingDirectory=$PARENT_DIR
ExecStart=/bin/bash $SCRIPT_DIR/run_update.sh
StandardOutput=journal
StandardError=journal
SERVICEEOF

    if [ -f "$UPDATE_SERVICE" ]; then
        log_success "Auto-update service file created"
        log_info "Service file contents:"
        echo "---"
        sudo cat $UPDATE_SERVICE
        echo "---"

        log_info "Resolved paths in service:"
        log_info "  User: root (run_update.sh drops privileges internally)"
        log_info "  WorkingDirectory: $PARENT_DIR"
        log_info "  ExecStart: /bin/bash $SCRIPT_DIR/run_update.sh"
    else
        log_error "Failed to create auto-update service"
    fi

    # Verify the service file exists before creating timer
    if [ ! -f "$UPDATE_SERVICE" ]; then
        log_error "Auto-update service file not found at $UPDATE_SERVICE"
        log_info "Skipping timer creation"
    else
        # Remove old timer file if it exists
        UPDATE_TIMER="/etc/systemd/system/klyra-update.timer"
        if [ -f "$UPDATE_TIMER" ]; then
            log_info "Removing old timer file..."
            sudo rm -f "$UPDATE_TIMER"
        fi

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
        echo "---"
        sudo cat $UPDATE_TIMER
        echo "---"
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

    # If systemd timer failed, fall back to cron (MANDATORY AUTO-UPDATE).
    # Installed in ROOT crontab so the cron job can restart klyra.service
    # without sudo. run_update.sh handles dropping privileges for the pull.
    if [ "$AUTO_UPDATE_WORKING" != "true" ]; then
        echo ""
        log_warning "Systemd timer failed - falling back to root cron..."
        log_info "Installing cron-based auto-update (runs every hour)..."

        CRON_JOB="0 * * * * /bin/bash $SCRIPT_DIR/run_update.sh >> /var/log/klyra-update.log 2>&1"

        # Replace any prior klyra auto-update entries (legacy + current names),
        # then append the new one. Done in root crontab.
        if (sudo crontab -l 2>/dev/null \
              | grep -vE 'klyra-update\.sh|auto_update\.sh|run_update\.sh' ; \
            echo "$CRON_JOB") | sudo crontab -; then
            # Ensure user crontabs from older installs no longer fight us.
            (crontab -l 2>/dev/null \
                | grep -vE 'klyra-update\.sh|auto_update\.sh|run_update\.sh') \
                | crontab - 2>/dev/null || true

            log_success "Cron-based auto-update installed in root crontab!"
            log_info "Updates will run every hour via cron"
            log_info "Cron job added:"
            echo "  $CRON_JOB"
            log_info "Check logs: sudo tail -f /var/log/klyra-update.log"
            AUTO_UPDATE_WORKING=true
        else
            log_error "Failed to install cron fallback!"
            log_error "AUTO-UPDATE IS CRITICAL - PLEASE FIX MANUALLY"
            echo ""
            log_info "Manual setup required:"
            log_info "1. Run: sudo crontab -e"
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

    # Give klyra access to hardware (mic, camera, GPU)
    log_info "Adding klyra to audio/video/render/input groups..."
    sudo usermod -a -G audio,video,render,input klyra
    log_success "klyra added to hardware groups"

    # Allow klyra to traverse into the install owner's home dir
    log_info "Granting klyra traversal access to $HOME..."
    sudo chmod o+x "$HOME"
    log_success "$HOME is now traversable"

    # Change ownership to klyra user
    log_info "Changing ownership to klyra user..."
    if sudo chown -R klyra:klyra "$SCRIPT_DIR/.."; then
        log_success "Ownership changed"
    fi

    # Restrict permissions: klyra rwx, others nothing
    # rwx (not r-x) so auto-update can git pull
    log_info "Setting klyra-only permissions..."
    if sudo chmod -R u=rwX,go= "$SCRIPT_DIR/.."; then
        log_success "Permissions restricted"
    fi

    # Make config.json unreadable except by klyra user
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        log_info "Securing config.json..."
        sudo chmod 600 "$SCRIPT_DIR/config.json"
        log_success "config.json secured"
    fi

    # Make conversation storage private
    if [ -d "$SCRIPT_DIR/../server/conversations" ]; then
        log_info "Securing conversations directory..."
        sudo chmod 700 "$SCRIPT_DIR/../server/conversations"
        log_success "conversations directory secured"
    fi

    # .git directory is already restricted by the recursive chmod above

    # Rewrite the systemd service files to run as klyra
    log_info "Updating systemd service to run as klyra..."
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Klyra AI Companion
After=network.target sound.target

[Service]
Type=simple
User=klyra
Group=klyra
SupplementaryGroups=audio video render input
WorkingDirectory=$SCRIPT_DIR
Environment="HOME=$SCRIPT_DIR"
Environment="PYTHONUNBUFFERED=1"
Environment="DISPLAY=:0"
Environment="XDG_RUNTIME_DIR=/tmp"
ExecStart=/bin/bash $SCRIPT_DIR/start_klyra.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    log_success "klyra.service updated for klyra user"

    # klyra-update.service intentionally stays as root — run_update.sh
    # detects the klyra user and drops to it for the unprivileged pull,
    # then restarts klyra.service as root. No rewrite needed here.
    if [ -f "$UPDATE_SERVICE" ]; then
        log_info "klyra-update.service stays as root (run_update.sh drops privileges to klyra)"
    fi

    log_info "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    echo ""
    log_success "Security lockdown enabled!"
    log_info "  - Code: Owned by klyra, hidden from other users"
    log_info "  - Config: Klyra-only readable"
    log_info "  - Conversations: Private"
    log_info "  - Service: Runs as klyra with audio/video/render/input access"
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
elif crontab -l 2>/dev/null | grep -q "auto_update.sh"; then
    log_success "Auto-update: ENABLED via cron"
    log_info "Cron job:"
    crontab -l | grep "auto_update.sh"
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
