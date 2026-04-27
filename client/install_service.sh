#!/bin/bash
# Install Klyra as a systemd service on Raspberry Pi

echo "Installing Klyra AI Companion service..."

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Update the service file with the correct path
SERVICE_FILE="/etc/systemd/system/klyra.service"

# Create the service file with correct paths
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Klyra AI Companion
After=network.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/client_companion.py
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

echo "Service file created at $SERVICE_FILE"

# Reload systemd
sudo systemctl daemon-reload

# Enable the service (start on boot)
sudo systemctl enable klyra.service

echo ""
echo "✓ Klyra service installed!"
echo ""

# Install auto-update service and timer
echo "Installing auto-update service..."

# Create auto-update service file
UPDATE_SERVICE="/etc/systemd/system/klyra-update.service"
sudo tee $UPDATE_SERVICE > /dev/null <<EOF
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
EOF

# Create auto-update timer file
UPDATE_TIMER="/etc/systemd/system/klyra-update.timer"
sudo tee $UPDATE_TIMER > /dev/null <<EOF
[Unit]
Description=Klyra Auto-Update Timer
Requires=klyra-update.service

[Timer]
# Check for updates every hour
OnBootSec=5min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
EOF

# Make auto-update script executable
chmod +x $SCRIPT_DIR/auto_update.sh

# Reload systemd and enable timer
sudo systemctl daemon-reload
sudo systemctl enable klyra-update.timer
sudo systemctl start klyra-update.timer

echo "✓ Auto-update enabled! Checks for updates every hour."
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
echo "  Update logs:   sudo journalctl -u klyra-update -f"
echo "  Update status: sudo systemctl status klyra-update.timer"
echo ""
echo "To start Klyra now, run: sudo systemctl start klyra"
