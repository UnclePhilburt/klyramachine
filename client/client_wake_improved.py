"""
Klyra Machine - Improved Wake Word Detection (No Account Required)
Uses optimized speech detection + Whisper transcription
Works immediately without waiting for approval!
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


class ImprovedWakeWordClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra - Improved Wake Word Detection...")
        print("Step 1: Loading config...")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]
        self.wake_word = self.config.get("wake_word", "hey klyra").lower()
        print(f"Step 2: Config loaded - {self.server_url}")
        print(f"   Wake word: '{self.wake_word}'")

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

        # Optimized settings for wake word detection
        self.speech_threshold = 400  # Lower = more sensitive
        self.silence_threshold = 250  # Volume below this = silence
        self.min_speech_chunks = 3   # Minimum chunks to consider as speech

        print("Step 9: All systems ready!\n")

    def detect_speech(self, audio_chunk):
        """Enhanced speech detection"""
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        return volume > self.speech_threshold

    def record_short_audio(self, duration=2.5):
        """Record short audio clip for wake word detection"""
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            frames = []
            speech_detected = False
            speech_chunks = 0

            for i in range(0, int(self.rate / self.chunk * duration)):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                # Count speech chunks
                if self.detect_speech(data):
                    speech_chunks += 1

            stream.stop_stream()
            stream.close()

            # Only transcribe if enough speech detected
            if speech_chunks < self.min_speech_chunks:
                return None

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

    def record_until_silence(self, max_duration=15, silence_duration=1.5):
        """Record audio until silence is detected"""
        try:
            # Small delay to let wake word finish and clear buffer
            time.sleep(0.3)

            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            # Clear any buffered audio from wake word detection
            for _ in range(5):
                try:
                    stream.read(self.chunk, exception_on_overflow=False)
                except:
                    pass

            frames = []
            silent_chunks = 0
            speech_chunks = 0  # Track how much actual speech we got
            chunks_for_silence = int(self.rate / self.chunk * silence_duration)
            max_chunks = int(self.rate / self.chunk * max_duration)

            print("   🎤 Recording... (speak your command)")

            for i in range(max_chunks):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                # Check volume
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()

                if volume < self.silence_threshold:
                    silent_chunks += 1
                    if silent_chunks >= chunks_for_silence:
                        print("   ⏸️  Silence detected, processing...")
                        break
                else:
                    silent_chunks = 0
                    speech_chunks += 1  # Count speech chunks

            stream.stop_stream()
            stream.close()

            # Check if we got enough actual speech (not just silence)
            if len(frames) == 0 or speech_chunks < 3:
                print("   ⚠️  No speech detected, skipping...\n")
                return None

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
                    return result.get("text", "").lower().strip()
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

    def play_ding(self):
        """Play ding sound when wake word is detected"""
        try:
            import os
            ding_path = "ding.mp3"
            if os.path.exists(ding_path):
                # Use a sound effect channel instead of music to avoid conflicts
                ding_sound = pygame.mixer.Sound(ding_path)
                ding_sound.play()
                # Don't wait for it to finish, continue immediately
            else:
                print(f"   ⚠️  ding.mp3 not found in {os.getcwd()}")
        except Exception as e:
            print(f"   ⚠️  Error playing ding: {e}")

    def process_command(self, text):
        """Send command to Klyra"""
        print(f"You: {text}")

        # Only capture image if camera is enabled (for faster responses)
        image_data = None
        if self.config.get("enable_camera", False):
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

    def check_for_wake_word(self, text):
        """Check if wake word is in the text"""
        if not text:
            return False, None

        # Clean up text
        text_clean = text.replace(",", "").replace(".", "").replace("!", "").replace("?", "")

        # Common variations of wake words
        wake_variations = {
            "hey klyra": ["hey klyra", "hey clara", "hey clera", "a klyra", "hey lyra"],
            "hey buddy": ["hey buddy", "hey body", "hey budy", "hey buddie", "a buddy"],
            "ok klyra": ["ok klyra", "okay klyra", "ok clara"],
            "hey computer": ["hey computer", "a computer"],
        }

        # Get variations for current wake word
        variations = wake_variations.get(self.wake_word, [self.wake_word])

        # Check for wake word
        for variant in variations:
            if variant in text_clean:
                # Extract command (remove wake word)
                command = text_clean
                for v in variations:
                    command = command.replace(v, "").strip()
                return True, command

        return False, None

    def listen_for_wake_word(self):
        """Listen for wake word continuously"""
        # Record short clip
        audio_data = self.record_short_audio(duration=2.5)

        if not audio_data:
            # No speech detected
            print(".", end="", flush=True)
            return False

        # Speech detected, transcribe it
        print("\n🎤 Speech detected, checking...")
        text = self.transcribe_audio(audio_data)

        if not text:
            print("   ⚠️  Couldn't transcribe\n")
            return False

        # Check for repetitive text (audio feedback loop)
        words = text.split()
        if len(words) > 10:
            # Check if same phrase is repeating
            first_two = ' '.join(words[:2]) if len(words) >= 2 else words[0]
            repeat_count = text.count(first_two)
            if repeat_count > 5:
                print(f"   ⚠️  Audio feedback detected (speaker → microphone loop)")
                print(f"   💡 Lower your speaker volume or move mic away from speaker\n")
                return False

        # Show what was heard
        print(f"   Heard: '{text}'")

        # Check for wake word
        wake_detected, command = self.check_for_wake_word(text)

        if wake_detected:
            print(f"✓ Wake word detected!\n")

            # Play ding sound
            self.play_ding()

            if command and len(command) > 3:
                # Command was included with wake word
                self.process_command(command)
            else:
                # Listen for full command
                audio_data = self.record_until_silence()
                if audio_data:
                    command = self.transcribe_audio(audio_data)
                    if command:
                        self.process_command(command)
                    else:
                        print("   ⚠️  Couldn't understand command\n")

            return True
        else:
            print(f"   No wake word detected\n")

        return False

    def run(self):
        """Run wake word detection"""
        print("="*60)
        print("KLYRA - IMPROVED WAKE WORD DETECTION")
        print("="*60)
        print(f"🎤 Say: '{self.wake_word.upper()}'")
        print("   (Works immediately - no account needed!)")
        print("Press Ctrl+C to exit")
        print("="*60 + "\n")

        if not self.check_server():
            return

        self.running = True
        print("👂 Listening for wake word...\n")

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
            print("Checking server connection...")
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                print("✓ Server connected!\n")
                return True
        except Exception as e:
            print(f"❌ Server offline: {e}\n")
            return False
        print("❌ Server offline!\n")
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
    client = ImprovedWakeWordClient()
    client.run()
