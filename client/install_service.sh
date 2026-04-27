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
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/client_companion.py
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

# Auto-update is optional - skipping for now to simplify installation
echo "[SKIP] Auto-update service (can be added later)"
echo ""

# Ask about lockdown
read -p "Do you want to enable security lockdown? (yes/no): " lockdown_choice

if [ "$lockdown_choice" = "yes" ] || [ "$lockdown_choice" = "y" ]; then
    echo ""
    echo "Applying security lockdown..."

    # Create a dedicated klyra user if it doesn't exist
    if ! id "klyra" &>/dev/null; then
        echo "Creating 'klyra' user..."
        sudo useradd -r -s /bin/false klyra
    fi

    # Change ownership to klyra user
    sudo chown -R klyra:klyra "$SCRIPT_DIR/.."

    # Restrict permissions
    sudo chmod -R 500 "$SCRIPT_DIR/.."

    # Make config.json unreadable except by klyra user
    if [ -f "$SCRIPT_DIR/config.json" ]; then
        sudo chmod 400 "$SCRIPT_DIR/config.json"
    fi

    # Make conversation storage private
    if [ -d "$SCRIPT_DIR/../server/conversations" ]; then
        sudo chmod 700 "$SCRIPT_DIR/../server/conversations"
    fi

    # Hide .git directory
    if [ -d "$SCRIPT_DIR/../.git" ]; then
        sudo chmod 700 "$SCRIPT_DIR/../.git"
    fi

    echo "✓ Security lockdown enabled!"
    echo "  - Code: Read-only for klyra user only"
    echo "  - Config: Hidden from all users except klyra"
    echo "  - Conversations: Private"
else
    echo "Security lockdown skipped."
fi

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
if [ "$lockdown_choice" = "yes" ] || [ "$lockdown_choice" = "y" ]; then
    echo "Security:"
    echo "  To undo lockdown: sudo chmod -R 755 $SCRIPT_DIR/.."
    echo ""
fi
echo "To start Klyra now, run: sudo systemctl start klyra"
