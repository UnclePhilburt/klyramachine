#!/bin/bash
# Auto-update script for Klyra
# Checks for updates from GitHub and restarts the service

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "Checking for updates..."

# Fetch latest changes from GitHub
git fetch origin main

# Check if there are updates
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "✓ Already up to date!"
    exit 0
fi

echo "📦 Updates found! Pulling latest code..."

# Pull the latest code
git pull origin main

if [ $? -ne 0 ]; then
    echo "❌ Error updating code"
    exit 1
fi

echo "✓ Code updated successfully!"

# Update dependencies if requirements.txt changed
if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
    echo "📦 Installing updated dependencies..."
    cd client
    pip3 install -r requirements.txt --upgrade
    cd ..
fi

# Restart the service if it's running
if systemctl is-active --quiet klyra; then
    echo "🔄 Restarting Klyra service..."
    sudo systemctl restart klyra
    echo "✓ Klyra restarted with latest updates!"
else
    echo "ℹ️  Klyra service not running. Start it with: sudo systemctl start klyra"
fi

echo ""
echo "🎉 Update complete!"
