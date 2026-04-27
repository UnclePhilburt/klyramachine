"""
Klyra Machine - Optimized Wake Word Detection
Only transcribes when sound is detected
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
import numpy as np

print("DEBUG: All imports loaded successfully")


class WakeWordClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra Wake Word Client...")
        print("Step 1: Loading config...")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]
        self.wake_word = "hey buddy"
        print(f"Step 2: Config loaded - {self.server_url}")

        # Initialize camera
        print("Step 3: Starting camera...")
        self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
        time.sleep(0.5)
        print("Step 4: Camera ready!")

        # Initialize audio
        print("Step 5: Starting audio...")
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        print("Step 6: Audio ready!")

        # Initialize pygame
        print("Step 7: Starting pygame mixer...")
        pygame.mixer.init()
        print("Step 8: Pygame ready!")

        self.running = False
        print("Step 9: All systems ready!\n")

    def detect_speech(self, audio_chunk):
        """Check if audio chunk has speech (simple volume detection)"""
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        return volume > 500  # Threshold for speech detection

    def record_with_speech_detection(self, duration=2):
        """Record audio, return None if no speech detected"""
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            frames = []
            has_speech = False

            for i in range(0, int(self.rate / self.chunk * duration)):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                # Check if this chunk has speech
                if self.detect_speech(data):
                    has_speech = True

            stream.stop_stream()
            stream.close()

            if not has_speech:
                return None  # No speech detected, don't transcribe

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
            return None

    def record_audio(self, duration=4):
        """Record audio for command"""
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

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))

            wav_buffer.seek(0)
            return wav_buffer.read()

        except Exception as e:
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
        except:
            return None

    def capture_image(self):
        """Capture from camera"""
        if not self.camera.isOpened():
            return None
        ret, frame = self.camera.read()
        if not ret:
            return None
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

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
        except:
            pass

    def process_command(self, text):
        """Send command to Klyra"""
        print(f"You: {text}")

        image_data = self.capture_image()

        print("💭 Thinking...")
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
                import base64
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")
                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"Klyra: {response_text}\n")
                    except:
                        pass

                if len(response.content) > 0:
                    self.play_audio(response.content)

        except Exception as e:
            print(f"Error: {e}")

    def listen_for_wake_word(self):
        """Listen for wake word with speech detection"""
        # Record short clip with speech detection
        audio_data = self.record_with_speech_detection(duration=2)

        if not audio_data:
            # No speech detected, skip transcription
            print(".", end="", flush=True)  # Show it's listening
            return False

        # Speech detected, transcribe it
        print("\n🎤 (heard speech, checking...)")
        text = self.transcribe_audio(audio_data)

        if not text:
            return False

        # Show what was heard (for debugging)
        print(f"   Heard: '{text}'")

        # Remove punctuation for better matching
        text_clean = text.replace(",", "").replace(".", "").replace("!", "").replace("?", "")

        # Check for wake word (flexible matching)
        wake_word_variants = ["hey buddy", "hey body", "hey budy", "hey buddie"]
        wake_word_detected = any(variant in text_clean for variant in wake_word_variants)

        if wake_word_detected:
            print(f"✓ Wake word detected!")

            # Remove wake word (try all variants)
            command = text_clean
            for variant in wake_word_variants:
                command = command.replace(variant, "").strip()

            if command and len(command) > 3:
                # Command included
                self.process_command(command)
            else:
                # Listen for full command
                print("👂 Listening...")
                audio_data = self.record_audio(duration=4)
                if audio_data:
                    command = self.transcribe_audio(audio_data)
                    if command:
                        self.process_command(command)

            return True

        return False

    def run(self):
        """Run wake word detection"""
        print("="*50)
        print("KLYRA - WAKE WORD MODE")
        print("="*50)
        print(f"🎤 Say: '{self.wake_word.upper()}'")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            return

        self.running = True
        print("👂 Listening quietly for wake word...\n")

        try:
            while self.running:
                self.listen_for_wake_word()
                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            self.cleanup()

    def check_server(self):
        """Check server"""
        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                return True
        except:
            pass
        print("❌ Server offline!")
        return False

    def cleanup(self):
        """Cleanup"""
        self.running = False
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Goodbye! 👋")


if __name__ == "__main__":
    client = WakeWordClient()
    client.run()
