"""
Simple push-to-talk client - press and hold any key to record
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
import keyboard  # We'll use keyboard library instead

# Fix Windows console encoding
if sys.platform == 'win32':
    import io as textio
    sys.stdout = textio.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class SimpleVoiceClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra Voice Client...")

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]

        # Initialize camera
        print("Initializing camera...")
        self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))

        # Initialize audio
        print("Initializing audio...")
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024

        # Initialize pygame
        print("Initializing pygame...")
        pygame.mixer.init()

        print("Ready!")

    def capture_image(self):
        """Capture from camera"""
        if not self.camera.isOpened():
            return None
        ret, frame = self.camera.read()
        if not ret:
            return None
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def record_audio_simple(self, duration=3):
        """Record for a fixed duration"""
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
            print(f"Error: {e}")
            return None

    def transcribe_audio(self, audio_data):
        """Transcribe with Whisper"""
        print("Transcribing...")
        try:
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
            print(f"Error: {e}")
            return None

    def play_audio(self, audio_data):
        """Play audio"""
        try:
            pygame.mixer.music.unload()
            with open("temp_response.mp3", 'wb') as f:
                f.write(audio_data)
            pygame.mixer.music.load("temp_response.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Audio error: {e}")

    def interact(self):
        """Full interaction"""
        # Record
        audio_data = self.record_audio_simple(duration=3)
        if not audio_data:
            return

        # Transcribe
        text = self.transcribe_audio(audio_data)
        if not text:
            print("Couldn't understand")
            return

        print(f"\nYou: {text}")

        # Get image
        image_data = self.capture_image()

        # Send to server
        print("Thinking...")
        data = {"client_id": self.client_id, "user_message": text}
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
                # Decode base64 encoded text
                import base64
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")
                response_text = ""
                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"Klyra: {response_text}\n")
                    except:
                        pass

                # Play audio
                if len(response.content) > 0:
                    self.play_audio(response.content)

        except Exception as e:
            print(f"Error: {e}")

    def run(self):
        """Run the client"""
        print("\n" + "="*50)
        print("KLYRA - SIMPLE VOICE MODE")
        print("="*50)
        print("Press ENTER to record 3 seconds")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            print("Server offline!")
            return

        try:
            while True:
                input("[Press ENTER to talk] ")
                self.interact()
        except KeyboardInterrupt:
            print("\nBye!")
            self.cleanup()

    def check_server(self):
        """Check server"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                print("Server online!\n")
                return True
        except:
            pass
        return False

    def cleanup(self):
        """Cleanup"""
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()


if __name__ == "__main__":
    client = SimpleVoiceClient()
    client.run()
