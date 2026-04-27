"""
Klyra Machine Client (Raspberry Pi)
Captures camera/audio and communicates with the server
"""

import cv2
import pyaudio
import wave
import io
import requests
import json
import time
import pygame
from datetime import datetime
from pathlib import Path


class KlyraClient:
    """Raspberry Pi client for Klyra Machine"""

    def __init__(self, config_path="config.json"):
        """Initialize the client"""
        print("Initializing Klyra Client...")

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]

        # Initialize camera
        self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
        if not self.camera.isOpened():
            print("Warning: Could not open camera")

        # Initialize audio
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024

        # Initialize pygame for audio playback
        pygame.mixer.init()

        # State
        self.running = False
        self.last_vision_time = 0

        print(f"Client initialized! Connected to server: {self.server_url}")

    def capture_image(self):
        """Capture image from camera"""
        if not self.camera.isOpened():
            print("Camera not available")
            return None

        ret, frame = self.camera.read()
        if not ret:
            print("Failed to capture image")
            return None

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def record_audio(self, duration=None):
        """Record audio from microphone"""
        if duration is None:
            duration = self.config.get("audio_record_duration", 5)

        print("Listening...")

        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            frames = []
            for i in range(0, int(self.rate / self.chunk * duration)):
                data = stream.read(self.chunk)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            # Convert to WAV
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))

            wav_buffer.seek(0)
            return wav_buffer.read()

        except Exception as e:
            print(f"Error recording audio: {e}")
            return None

    def play_audio(self, audio_data):
        """Play audio through speaker"""
        try:
            # Save to temporary file
            temp_file = "temp_response.mp3"
            with open(temp_file, 'wb') as f:
                f.write(audio_data)

            # Play with pygame
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            print("Finished speaking")

        except Exception as e:
            print(f"Error playing audio: {e}")

    def send_to_server(self, endpoint, data=None, files=None):
        """Send request to server"""
        try:
            url = f"{self.server_url}{endpoint}"
            response = requests.post(url, data=data, files=files, timeout=30)

            if response.status_code == 200:
                return response
            else:
                print(f"Server error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error communicating with server: {e}")
            return None

    def interact(self, user_message, include_vision=True):
        """
        Complete interaction cycle:
        1. Optionally capture image
        2. Send to server with message
        3. Receive and play audio response
        """
        print(f"\nYou: {user_message}")

        # Prepare data
        data = {
            "client_id": self.client_id,
            "user_message": user_message
        }

        files = {}
        if include_vision:
            image_data = self.capture_image()
            if image_data:
                files["image"] = ("image.jpg", image_data, "image/jpeg")
                print("Sending image to server...")

        # Send to server
        print("Waiting for Klyra...")
        response = self.send_to_server("/api/process-interaction", data=data, files=files)

        if response:
            # Get response text from header
            response_text = response.headers.get("X-Response-Text", "")

            if response_text:
                print(f"Klyra: {response_text}")
            else:
                print("Klyra: [No text response received]")

            # Try to play audio response
            if len(response.content) > 0:
                try:
                    audio_data = response.content
                    self.play_audio(audio_data)
                except Exception as e:
                    print(f"(Audio playback failed, but text response shown above)")

            return response_text
        else:
            print("No response from server")
            return None

    def check_server(self):
        """Check if server is online"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                print("Server is online!")
                return True
        except:
            pass

        print("Cannot connect to server")
        return False

    def run_interactive(self):
        """Run in interactive mode - manual text input"""
        print("\n" + "="*50)
        print("KLYRA MACHINE CLIENT")
        print("="*50)
        print("Type your messages and press Enter")
        print("Type 'quit' to exit")
        print("="*50 + "\n")

        if not self.check_server():
            print("Please start the server first!")
            return

        self.running = True

        try:
            while self.running:
                # Get user input
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("Goodbye!")
                    break

                # Interact with server
                self.interact(user_input, include_vision=True)

        except KeyboardInterrupt:
            print("\nShutting down...")

        self.cleanup()

    def run_voice_mode(self):
        """Run in voice mode - press Enter to speak"""
        print("\n" + "="*50)
        print("KLYRA MACHINE CLIENT - VOICE MODE")
        print("="*50)
        print("Press Enter, then speak your message")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            print("Please start the server first!")
            return

        # Note: Voice recognition happens on the server side (Whisper API)
        # For now, this is still text-based. Full voice mode would require
        # sending audio to server and having server do speech-to-text

        print("Voice mode coming soon!")
        print("For now, using text input mode...")
        self.run_interactive()

    def cleanup(self):
        """Clean up resources"""
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Client shut down")


def main():
    """Main entry point"""
    import sys

    client = KlyraClient()

    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "voice":
        client.run_voice_mode()
    else:
        client.run_interactive()


if __name__ == "__main__":
    main()
