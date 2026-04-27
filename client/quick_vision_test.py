"""
Quick test: Capture image from camera and ask Klyra what it sees
"""

import cv2
import requests
import json

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

server_url = config["server_url"]
client_id = config["client_id"]

print("="*50)
print("KLYRA VISION TEST")
print("="*50)

# Capture image
print("\nCapturing image from camera...")
cam = cv2.VideoCapture(0)
ret, frame = cam.read()
cam.release()

if not ret:
    print("[ERROR] Could not capture image")
    exit(1)

print("[OK] Image captured!")

# Encode as JPEG
_, buffer = cv2.imencode('.jpg', frame)
image_data = buffer.tobytes()

# Send to server
print("Sending image to Klyra for analysis...")

try:
    files = {"image": ("image.jpg", image_data, "image/jpeg")}
    response = requests.post(
        f"{server_url}/api/analyze-image",
        files=files,
        timeout=30
    )

    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            description = result.get("description")
            print("\n" + "="*50)
            print("KLYRA SEES:")
            print("="*50)
            print(description)
            print("="*50)
        else:
            print(f"[ERROR] {result.get('error')}")
    else:
        print(f"[ERROR] Server returned {response.status_code}")

except Exception as e:
    print(f"[ERROR] {e}")
