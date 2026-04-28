"""
Klyra Machine - Porcupine Wake Word Detection
Uses Picovoice's Porcupine for accurate wake word detection
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
import pvporcupine
import struct

print("DEBUG: All imports loaded successfully")


class PorcupineWakeWordClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra with Porcupine Wake Word Detection...")
        print("Step 1: Loading config...")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]

        # Get Porcupine settings
        self.porcupine_access_key = self.config.get("porcupine_access_key")
        if not self.porcupine_access_key:
            print("ERROR: Please add 'porcupine_access_key' to config.json")
            print("Get your free access key at: https://console.picovoice.ai/")
            sys.exit(1)

        # Wake word - can use built-in keywords or custom
        self.wake_word = self.config.get("wake_word", "porcupine")
        print(f"Step 2: Config loaded - {self.server_url}")
        print(f"   Wake word: {self.wake_word}")

        # Initialize Porcupine
        print("Step 3: Starting Porcupine...")
        try:
            # Built-in keywords: alexa, americano, blueberry, bumblebee, computer,
            # grapefruit, grasshopper, hey google, hey siri, jarvis, ok google,
            # picovoice, porcupine, terminator
            self.porcupine = pvporcupine.create(
                access_key=self.porcupine_access_key,
                keywords=[self.wake_word]
            )
            print(f"Step 4: Porcupine ready! (Sample rate: {self.porcupine.sample_rate}Hz)")
        except Exception as e:
            print(f"ERROR initializing Porcupine: {e}")
            print("Make sure your access key is valid.")
            print("Get your free access key at: https://console.picovoice.ai/")
            sys.exit(1)

        # Initialize camera
        print("Step 5: Starting camera...")
        self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
        time.sleep(0.5)
        print("Step 6: Camera ready!")

        # Initialize audio
        print("Step 7: Starting audio...")
        self.audio = pyaudio.PyAudio()
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = self.porcupine.sample_rate  # Use Porcupine's required sample rate
        self.chunk = self.porcupine.frame_length  # Use Porcupine's frame length
        print("Step 8: Audio ready!")

        # Initialize pygame for audio playback
        print("Step 9: Starting pygame mixer...")
        pygame.mixer.init()
        print("Step 10: Pygame ready!")

        self.running = False
        print("Step 11: All systems ready!\n")

    def record_until_silence(self, max_duration=15, silence_threshold=300, silence_duration=1.5):
        """Record audio until silence is detected"""
        try:
            # Use 16kHz for recording (better for Whisper)
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            frames = []
            silent_chunks = 0
            chunks_for_silence = int(16000 / 1024 * silence_duration)
            max_chunks = int(16000 / 1024 * max_duration)

            print("   🎤 Recording... (speak your command)")

            for i in range(max_chunks):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

                # Check volume
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()

                if volume < silence_threshold:
                    silent_chunks += 1
                    if silent_chunks >= chunks_for_silence:
                        print("   ⏸️  Silence detected, processing...")
                        break
                else:
                    silent_chunks = 0  # Reset if sound detected

            stream.stop_stream()
            stream.close()

            if len(frames) == 0:
                return None

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(16000)
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
                    return result.get("text", "").strip()
            return None
        except Exception as e:
            print(f"Transcription error: {e}")
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
        except Exception as e:
            print(f"Audio playback error: {e}")

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
        """Listen for wake word using Porcupine"""
        try:
            # Open audio stream for Porcupine
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            print("👂 Listening for wake word...")
            print(f"   Say: '{self.wake_word.upper()}'")
            print("   (Press Ctrl+C to exit)\n")

            while self.running:
                # Read audio frame
                pcm = stream.read(self.chunk, exception_on_overflow=False)
                pcm_unpacked = struct.unpack_from("h" * self.chunk, pcm)

                # Process with Porcupine
                keyword_index = self.porcupine.process(pcm_unpacked)

                if keyword_index >= 0:
                    print(f"\n✓ Wake word '{self.wake_word}' detected!")

                    # Wake word detected, now listen for command
                    stream.stop_stream()
                    stream.close()

                    audio_data = self.record_until_silence()
                    if audio_data:
                        command = self.transcribe_audio(audio_data)
                        if command:
                            self.process_command(command)
                        else:
                            print("   ⚠️  Couldn't understand the command\n")

                    # Restart listening
                    print("👂 Listening for wake word again...\n")
                    stream = self.audio.open(
                        format=self.audio_format,
                        channels=self.channels,
                        rate=self.rate,
                        input=True,
                        frames_per_buffer=self.chunk
                    )

            stream.stop_stream()
            stream.close()

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
        except Exception as e:
            print(f"Error in wake word detection: {e}")
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()

    def run(self):
        """Run wake word detection"""
        print("="*50)
        print("KLYRA - PORCUPINE WAKE WORD MODE")
        print("="*50)
        print(f"🎤 Wake word: '{self.wake_word.upper()}'")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            return

        self.running = True

        try:
            self.listen_for_wake_word()
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
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
            print(f"❌ Server offline: {e}")
            return False
        print("❌ Server offline!")
        return False

    def cleanup(self):
        """Cleanup"""
        self.running = False
        if hasattr(self, 'porcupine'):
            self.porcupine.delete()
        if self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Goodbye! 👋")


if __name__ == "__main__":
    client = PorcupineWakeWordClient()
    client.run()
