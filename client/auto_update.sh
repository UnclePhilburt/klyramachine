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
    if [ ! -x "venv/bin/python" ]; then
        echo "❌ venv missing at client/venv — re-run easy_install.sh to repair"
        exit 1
    fi
    # Prefer uv if available (faster); fall back to plain pip in the venv.
    export PATH="$HOME/.local/bin:$PATH"
    if command -v uv &>/dev/null; then
        uv pip install --python venv/bin/python -r requirements.txt --upgrade
    else
        venv/bin/pip install -r requirements.txt --upgrade
    fi
    cd ..
fi

# Re-apply lockdown if klyra user exists (lockdown was previously enabled)
if id "klyra" &>/dev/null; then
    echo "🔒 Re-applying security lockdown..."

    # Change ownership to klyra user
    sudo chown -R klyra:klyra "$SCRIPT_DIR/.."

    # Restrict permissions
    sudo chmod -R 500 "$SCRIPT_DIR/.."

    # Make config.json unreadable except by klyra user
    if [ -f "$SCRIPT_DIR/client/config.json" ]; then
        sudo chmod 400 "$SCRIPT_DIR/client/config.json"
    fi

    # Make conversation storage private
    if [ -d "$SCRIPT_DIR/server/conversations" ]; then
        sudo chmod 700 "$SCRIPT_DIR/server/conversations"
    fi

    # Hide .git directory
    if [ -d "$SCRIPT_DIR/.git" ]; then
        sudo chmod 700 "$SCRIPT_DIR/.git"
    fi

    echo "✓ Security lockdown reapplied!"
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
