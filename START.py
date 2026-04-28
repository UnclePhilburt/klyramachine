#!/usr/bin/env python3
"""
Quick launcher for Klyra Machine
Just run: python3 START.py
"""
import os
import sys
import subprocess

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
client_dir = os.path.join(script_dir, "client")
venv_python = os.path.join(client_dir, "venv", "bin", "python3")

# Check if venv exists
if not os.path.exists(venv_python):
    print("ERROR: Virtual environment not found!")
    print("Please run the installer first:")
    print("  curl -s https://raw.githubusercontent.com/UnclePhilburt/klyramachine/main/install.sh | bash")
    sys.exit(1)

# Launch the companion client
print("🚀 Starting Klyra Machine...")
os.chdir(client_dir)
subprocess.run([venv_python, "client_companion.py"])
