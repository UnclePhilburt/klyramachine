"""
Klyra Machine Client with VOICE INPUT
Speak to Klyra instead of typing!
"""

import cv2
import pyaudio
import wave
import io
import requests
import json
import time
import pygame
import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import io as textio
    sys.stdout = textio.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class KlyraVoiceClient:
    """Raspberry Pi client for Klyra Machine with voice input"""

    def __init__(self, config_path="config.json"):
        """Initialize the client"""
        print("Initializing Klyra Voice Client...")

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

    def record_audio(self, duration=5):
        """Record audio from microphone"""
        print(f"[Recording for {duration} seconds...]")

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

    def transcribe_audio(self, audio_data):
        """Send audio to server for transcription using Whisper"""
        try:
            print("Transcribing your speech...")

            files = {"audio": ("speech.wav", audio_data, "audio/wav")}
            response = requests.post(
                f"{self.server_url}/api/speech-to-text",
                files=files,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("text", "")

            return None

        except Exception as e:
            print(f"Error transcribing: {e}")
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

        except Exception as e:
            print(f"Error playing audio: {e}")

    def interact_voice(self, include_vision=True):
        """
        Voice interaction cycle:
        1. Record user speaking
        2. Transcribe speech to text
        3. Optionally capture image
        4. Send to server
        5. Receive and play audio response
        """

        # Record audio
        audio_duration = self.config.get("audio_record_duration", 5)
        audio_data = self.record_audio(duration=audio_duration)

        if not audio_data:
            print("Failed to record audio")
            return None

        # Transcribe audio
        user_message = self.transcribe_audio(audio_data)

        if not user_message:
            print("Could not understand speech")
            return None

        print(f"\nYou said: {user_message}")

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
                print("Captured image")

        # Send to server
        print("Waiting for Klyra...")

        try:
            response = requests.post(
                f"{self.server_url}/api/process-interaction",
                data=data,
                files=files,
                timeout=30
            )

            if response.status_code == 200:
                # Get response text from header
                response_text = response.headers.get("X-Response-Text", "")

                if response_text:
                    print(f"\nKlyra: {response_text}\n")

                # Play audio response
                if len(response.content) > 0:
                    try:
                        audio_data = response.content
                        self.play_audio(audio_data)
                    except Exception as e:
                        print(f"(Audio playback issue)")

                return response_text
            else:
                print(f"Server error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Error: {e}")
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

    def run_voice_mode(self):
        """Run in voice mode - press Enter to start recording"""
        print("\n" + "="*50)
        print("KLYRA MACHINE - VOICE MODE")
        print("="*50)
        print("Press Enter, then SPEAK your message")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            print("Please make sure the server is running!")
            return

        self.running = True

        try:
            while self.running:
                # Wait for user to press Enter
                input("\n[Press Enter to speak] ")

                # Record and interact
                self.interact_voice(include_vision=True)

        except KeyboardInterrupt:
            print("\nShutting down...")

        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Client shut down")


def main():
    """Main entry point"""
    client = KlyraVoiceClient()
    client.run_voice_mode()


if __name__ == "__main__":
    main()
