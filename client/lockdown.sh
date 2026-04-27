#!/bin/bash
# Lockdown script for Klyra - Restrict access to code and config

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "🔒 Locking down Klyra..."

# Create a dedicated klyra user if it doesn't exist
if ! id "klyra" &>/dev/null; then
    echo "Creating 'klyra' user..."
    sudo useradd -r -s /bin/false klyra
fi

# Change ownership to klyra user
sudo chown -R klyra:klyra "$SCRIPT_DIR/.."

# Restrict permissions
# Owner (klyra): read + execute
# Group: no access
# Others: no access
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

echo "✓ Permissions set:"
echo "  - Code: Read-only for klyra user only"
echo "  - Config: Hidden from all users except klyra"
echo "  - Conversations: Private"
echo ""
echo "⚠️  Regular users can no longer view the code"
echo "⚠️  Use 'sudo' to make changes as root"
