#!/bin/bash
# Quick start script for Klyra

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Use virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    python client_companion.py
else
    python3 client_companion.py
fi
