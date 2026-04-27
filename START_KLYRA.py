#!/usr/bin/env python3
"""
Klyra Machine - Easy Starter
Double-click this file to start Klyra!
"""

import os
import sys
import subprocess
import platform

def main():
    print("="*50)
    print("   KLYRA MACHINE - STARTING...")
    print("="*50)
    print()

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.join(script_dir, "client")
    client_script = os.path.join(client_dir, "client_companion.py")

    # Check if client script exists
    if not os.path.exists(client_script):
        print("❌ Error: client_companion.py not found!")
        print(f"   Looking for: {client_script}")
        print()
        print("Make sure you have the complete klyramachine folder.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Check if config exists
    config_file = os.path.join(client_dir, "config.json")
    if not os.path.exists(config_file):
        print("⚠️  Warning: config.json not found!")
        print(f"   Creating default config at: {config_file}")
        print()

        # Create default config
        import json
        default_config = {
            "server_url": "https://klyramachine.onrender.com",
            "client_id": f"user_{platform.node()}",
            "camera_index": 0
        }

        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)

        print("✓ Config created with default settings")
        print()

    print("Starting Klyra Companion Mode...")
    print()
    print("Say 'HEY BUDDY' followed by your command!")
    print("Press Ctrl+C to exit")
    print("="*50)
    print()

    # Change to client directory
    os.chdir(client_dir)

    # Run the client
    try:
        subprocess.run([sys.executable, "client_companion.py"])
    except KeyboardInterrupt:
        print("\n\nShutting down Klyra...")
        print("Goodbye! 👋")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
