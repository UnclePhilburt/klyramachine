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
echo "Commands:"
echo "  Start:   sudo systemctl start klyra"
echo "  Stop:    sudo systemctl stop klyra"
echo "  Restart: sudo systemctl restart klyra"
echo "  Status:  sudo systemctl status klyra"
echo "  Logs:    sudo journalctl -u klyra -f"
echo ""
echo "To start Klyra now, run: sudo systemctl start klyra"
