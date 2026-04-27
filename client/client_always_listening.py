"""
Klyra Machine - Always Listening Mode
Waits for "Hey Klyra" wake word
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
import threading

# Fix Windows console encoding
if sys.platform == 'win32':
    import io as textio
    sys.stdout = textio.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class AlwaysListeningClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra - Always Listening Mode...")

        # Load configuration
        print("Loading config...")
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]
        self.wake_word = "hey klyra"
        print(f"Server: {self.server_url}")

        # Initialize camera
        print("Initializing camera...")
        self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
        time.sleep(1)  # Give camera time to initialize
        print("Camera ready!")

        # Initialize audio
        print("Initializing audio...")
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        print("Audio ready!")

        # Initialize pygame
        print("Initializing pygame...")
        pygame.mixer.init()
        print("Pygame ready!")

        self.running = False
        print("All systems ready!")

    def capture_image(self):
        """Capture from camera"""
        if not self.camera.isOpened():
            return None
        ret, frame = self.camera.read()
        if not ret:
            return None
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def record_audio(self, duration=3):
        """Record audio for specified duration"""
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
                data = stream.read(self.chunk, exception_on_overflow=False)
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
            print(f"Recording error: {e}")
            return None

    def transcribe_audio(self, audio_data):
        """Transcribe with Whisper"""
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
                    return result.get("text", "").lower()
            return None
        except Exception as e:
            print(f"Transcription error: {e}")
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

    def process_command(self, text):
        """Send command to Klyra"""
        print(f"You: {text}")

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

    def listen_for_wake_word(self):
        """Continuously listen for wake word"""
        print("Listening for wake word...")

        # Record short clip
        audio_data = self.record_audio(duration=2)
        if not audio_data:
            return False

        # Transcribe
        text = self.transcribe_audio(audio_data)
        if not text:
            return False

        # Check for wake word
        if self.wake_word in text:
            print(f"\n🎤 Wake word detected!")

            # Remove wake word from text
            command = text.replace(self.wake_word, "").strip()

            if command:
                # There was a command after the wake word
                self.process_command(command)
            else:
                # Just wake word, listen for command
                print("Listening for your command...")
                audio_data = self.record_audio(duration=5)
                if audio_data:
                    command = self.transcribe_audio(audio_data)
                    if command:
                        self.process_command(command)

            return True

        return False

    def run(self):
        """Run always-listening mode"""
        print("\n" + "="*50)
        print("KLYRA - ALWAYS LISTENING")
        print("="*50)
        print(f"Wake word: '{self.wake_word}'")
        print("Say 'Hey Klyra' followed by your command")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            print("Server offline!")
            return

        self.running = True

        try:
            while self.running:
                # Listen for wake word
                self.listen_for_wake_word()
                time.sleep(0.1)  # Small delay

        except KeyboardInterrupt:
            print("\nShutting down...")
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
        print("Server offline!")
        return False

    def cleanup(self):
        """Cleanup"""
        self.running = False
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Goodbye!")


if __name__ == "__main__":
    client = AlwaysListeningClient()
    client.run()
