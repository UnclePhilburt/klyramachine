"""
Simple test script to test Klyra Machine without camera
Just tests conversation and audio playback
"""

import requests
import json
import pygame
import time

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

server_url = config["server_url"]
client_id = config["client_id"]

print("="*50)
print("KLYRA MACHINE - TEXT-ONLY TEST")
print("="*50)
print(f"Server: {server_url}")
print("="*50)

# Initialize pygame for audio
pygame.mixer.init()

# Test server connection
print("\nTesting server connection...")
try:
    response = requests.get(f"{server_url}/", timeout=5)
    if response.status_code == 200:
        print("[OK] Server is online!")
    else:
        print("[ERROR] Server returned error")
        exit(1)
except Exception as e:
    print(f"[ERROR] Cannot connect to server: {e}")
    exit(1)

# Main conversation loop
print("\n" + "="*50)
print("Type messages to talk to Klyra (without vision)")
print("Type 'quit' to exit")
print("="*50 + "\n")

while True:
    # Get user input
    user_input = input("\nYou: ").strip()

    if not user_input:
        continue

    if user_input.lower() in ['quit', 'exit', 'bye']:
        print("Goodbye!")
        break

    # Send to server
    print("Waiting for Klyra...")

    try:
        data = {
            "client_id": client_id,
            "user_message": user_input
        }

        response = requests.post(
            f"{server_url}/api/conversation",
            data=data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            if result.get("success"):
                response_text = result.get("response", "")
                print(f"Klyra: {response_text}")

                # Convert to speech
                print("Generating speech...")
                tts_response = requests.post(
                    f"{server_url}/api/text-to-speech",
                    data={"text": response_text},
                    timeout=30
                )

                if tts_response.status_code == 200:
                    # Save and play audio
                    with open("temp_response.mp3", "wb") as f:
                        f.write(tts_response.content)

                    pygame.mixer.music.load("temp_response.mp3")
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)

                    print("[OK] Finished speaking")
                else:
                    print("[ERROR] Failed to generate speech")
            else:
                print(f"[ERROR] {result.get('error')}")
        else:
            print(f"[ERROR] Server error: {response.status_code}")

    except Exception as e:
        print(f"[ERROR] {e}")

pygame.mixer.quit()
