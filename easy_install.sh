#!/bin/bash
# Easy Installer for Klyra Machine
# One-click setup for Raspberry Pi

echo "=========================================="
echo "   KLYRA MACHINE - EASY INSTALLER"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi or Linux
if [[ ! "$OSTYPE" == "linux-gnu"* ]]; then
    echo "❌ This installer is for Linux/Raspberry Pi only"
    echo "   For Windows, see the client folder for manual setup"
    exit 1
fi

# Get current directory
INSTALL_DIR="$HOME/klyramachine"

echo "📦 Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y git python3-pip python3-pyaudio portaudio19-dev python3-opencv

echo ""
echo "📥 Step 2: Downloading Klyra Machine..."

if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  Klyra already exists at $INSTALL_DIR"
    read -p "Delete and reinstall? (yes/no): " reinstall
    if [ "$reinstall" = "yes" ]; then
        rm -rf "$INSTALL_DIR"
    else
        echo "Installation cancelled."
        exit 0
    fi
fi

git clone https://github.com/UnclePhilburt/klyramachine.git "$INSTALL_DIR"
cd "$INSTALL_DIR/client"

echo ""
echo "📦 Step 3: Installing Python dependencies..."
# Try with --break-system-packages flag (needed for newer Raspberry Pi OS)
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt --user

echo ""
echo "⚙️  Step 4: Configuration"
echo ""

# Check if config already exists
if [ -f "config.json" ]; then
    echo "✓ Config file already exists"
else
    echo "Creating config file..."
    cat > config.json <<EOF
{
    "server_url": "https://klyramachine.onrender.com",
    "client_id": "raspberry_pi_$(hostname)",
    "camera_index": 0
}
EOF
    echo "✓ Config created with default settings"
fi

echo ""
echo "Server URL: https://klyramachine.onrender.com"
read -p "Change server URL? (press Enter to keep default, or type new URL): " new_url
if [ ! -z "$new_url" ]; then
    # Update server URL in config.json
    python3 -c "import json; f=open('config.json','r+'); data=json.load(f); data['server_url']='$new_url'; f.seek(0); json.dump(data,f,indent=4); f.truncate()"
    echo "✓ Server URL updated"
fi

echo ""
echo "🚀 Step 5: Setting up auto-start..."
chmod +x install_service.sh
./install_service.sh

echo ""
echo "=========================================="
echo "   ✓ INSTALLATION COMPLETE!"
echo "=========================================="
echo ""
echo "To start Klyra now, run:"
echo "  sudo systemctl start klyra"
echo ""
echo "To check status:"
echo "  sudo systemctl status klyra"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u klyra -f"
echo ""
echo "Klyra will now:"
echo "  ✓ Auto-start on boot"
echo "  ✓ Auto-update every minute"
echo "  ✓ Auto-restart if it crashes"
echo ""
echo "Say 'Hey Buddy' to talk to Klyra!"
echo "=========================================="
