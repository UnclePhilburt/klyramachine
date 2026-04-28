#!/bin/bash
# Klyra Machine Launcher
# Double-click this file to start Klyra

cd "$(dirname "$0")/client"
source venv/bin/activate
python3 client_companion.py
