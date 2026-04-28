#!/bin/bash
# Klyra Machine Launcher with Auto-Restart
# Double-click this file to start Klyra

cd "$(dirname "$0")/client"
source venv/bin/activate

echo "Starting Klyra with auto-restart..."
echo "Press Ctrl+C twice to stop completely"

while true; do
    python3 client_companion.py
    echo ""
    echo "Klyra crashed! Restarting in 3 seconds..."
    sleep 3
done
