"""
Klyra Machine - Text Input Client (No Microphone Needed)
For testing on Raspberry Pi without audio setup
"""

import cv2
import requests
import json
import sys
import os

print("="*60)
print("KLYRA TEXT CLIENT - NO MICROPHONE REQUIRED")
print("="*60)
print("")

class TextClient:
    def __init__(self, config_path="config.json"):
        print("[INIT] Loading configuration...")

        if not os.path.exists(config_path):
            print(f"[ERROR] Config file not found: {config_path}")
            sys.exit(1)

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]

        print(f"[INIT]   Server: {self.server_url}")
        print(f"[INIT]   Client ID: {self.client_id}")
        print("")

        # Initialize camera (optional)
        print("[INIT] Checking camera...")
        camera_enabled = self.config.get("enable_camera", True)

        if camera_enabled:
            try:
                self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
                if self.camera.isOpened():
                    ret, test_frame = self.camera.read()
                    if ret:
                        print(f"[INIT]   ✓ Camera ready! Resolution: {test_frame.shape[1]}x{test_frame.shape[0]}")
                    else:
                        print("[INIT]   ⚠ Camera opened but can't read frames, disabling")
                        self.camera = None
                else:
                    print("[INIT]   ⚠ Camera not available, disabling")
                    self.camera = None
            except Exception as e:
                print(f"[INIT]   ⚠ Camera error: {e}, disabling")
                self.camera = None
        else:
            self.camera = None
            print("[INIT]   Camera disabled in config")

        print("")

    def capture_image(self):
        """Capture image from camera if available"""
        if not self.camera or not self.camera.isOpened():
            return None

        ret, frame = self.camera.read()
        if not ret:
            return None

        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def send_message(self, text):
        """Send text message to Klyra"""
        print(f"\n[YOU] {text}")

        # Capture image if camera available
        image_data = self.capture_image()
        if image_data:
            print("[INFO] Including camera image")

        print("[INFO] Sending to server...")

        data = {
            "client_id": self.client_id,
            "user_message": text
        }

        files = {}
        if image_data:
            files["image"] = ("image.jpg", image_data, "image/jpeg")

        try:
            response = requests.post(
                f"{self.server_url}/api/process-interaction",
                data=data,
                files=files,
                timeout=30
            )

            if response.status_code == 200:
                # Try to get response text from header
                import base64
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")

                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"[KLYRA] {response_text}")
                    except:
                        print("[KLYRA] (Response received but couldn't decode text)")
                else:
                    print("[KLYRA] (Response received)")

                # Note: Audio response is ignored in text mode
                if len(response.content) > 0:
                    print(f"[INFO] Audio response received ({len(response.content)} bytes) - skipped in text mode")
            else:
                print(f"[ERROR] Server error: {response.status_code}")

        except requests.exceptions.Timeout:
            print("[ERROR] Server timeout - is the server sleeping? Try again in 30 seconds.")
        except Exception as e:
            print(f"[ERROR] {e}")

    def check_server(self):
        """Check if server is reachable"""
        print("[INFO] Checking server connection...")
        try:
            response = requests.get(f"{self.server_url}/", timeout=10)
            if response.status_code == 200:
                print("[INFO] ✓ Server is online!")
                return True
        except:
            pass

        print("[WARN] Server not responding (may be sleeping on Render)")
        print("[WARN] It will wake up on first request (takes ~30 seconds)")
        return False

    def run(self):
        """Run interactive text client"""
        print("="*60)
        print("KLYRA TEXT MODE - TYPE YOUR MESSAGES")
        print("="*60)
        print("")

        self.check_server()

        print("")
        print("Commands:")
        print("  - Type your message and press Enter")
        print("  - Type 'quit' or 'exit' to stop")
        print("  - Press Ctrl+C to stop")
        print("")
        print("="*60)
        print("")

        try:
            while True:
                try:
                    # Get user input
                    user_input = input("You: ").strip()

                    if not user_input:
                        continue

                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        print("\n[INFO] Goodbye! 👋")
                        break

                    # Send to server
                    self.send_message(user_input)

                except EOFError:
                    print("\n[INFO] EOF received, exiting...")
                    break

        except KeyboardInterrupt:
            print("\n\n[INFO] Interrupted by user")
        finally:
            self.cleanup()

    def cleanup(self):
        """Cleanup resources"""
        if self.camera and self.camera.isOpened():
            self.camera.release()
        print("[INFO] Cleanup complete")


if __name__ == "__main__":
    try:
        client = TextClient()
        client.run()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
