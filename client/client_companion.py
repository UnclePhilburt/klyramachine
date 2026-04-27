"""
Klyra Machine - AI Companion Mode
Monitors you and makes spontaneous comments + responds to wake word
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
import random
from datetime import datetime

print("DEBUG: All imports loaded successfully")


class CompanionClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra Companion Mode...")
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

        # Companion state
        self.last_observation_time = time.time()
        self.observation_interval_min = 30  # Minimum 30 seconds between observations
        self.observation_interval_max = 120  # Maximum 2 minutes
        self.next_observation = time.time() + random.randint(30, 60)

        self.last_frame = None
        self.running = False

        print("Step 9: All systems ready!\n")

    def detect_motion(self, current_frame):
        """Detect if there's motion between frames"""
        if self.last_frame is None:
            self.last_frame = current_frame
            return False

        # Convert to grayscale
        gray1 = cv2.cvtColor(self.last_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)

        # Calculate difference
        diff = cv2.absdiff(gray1, gray2)
        motion_level = np.mean(diff)

        self.last_frame = current_frame

        # Threshold for motion detection
        return motion_level > 5

    def detect_speech(self, audio_chunk):
        """Check if audio chunk has speech"""
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        return volume > 500

    def capture_image(self):
        """Capture from camera"""
        if not self.camera.isOpened():
            return None
        ret, frame = self.camera.read()
        if not ret:
            return None
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes(), frame

    def make_spontaneous_comment(self):
        """Take a photo and make a spontaneous comment"""
        print("\n👁️  *Klyra observes you*")

        image_data, frame = self.capture_image()
        if not image_data:
            return

        # Detect motion
        has_motion = self.detect_motion(frame)

        # Create context for the observation
        current_hour = datetime.now().hour

        if current_hour < 12:
            time_context = "morning"
        elif current_hour < 17:
            time_context = "afternoon"
        else:
            time_context = "evening"

        # Send to server with special prompt for observations
        observation_prompts = [
            f"You're a sarcastic AI buddy observing the user in the {time_context}. Comment on ANYTHING you see - the mess in the background, their pets, what's on their screen, their setup, literally anything. Be funny, slightly mean, and roast them if you see something worth roasting. Don't be nice - be a sassy friend who calls them out. Keep it short and punchy.",
            f"Look at what's happening in this {time_context} scene. Notice the background, any pets, messes, their setup, TV, posters, whatever. Make a sarcastic observation or joke about it. Be a bit of a dick about it - don't hold back. One or two sentences max.",
            f"You're watching the user in the {time_context}. Spot something funny, messy, weird, or worth commenting on in the scene (background, pets, their stuff, etc). Make a snarky comment about it. Channel your inner roast comedian. Be brief and savage.",
            f"Observe EVERYTHING in this scene - not just the person. See any pets? Roast them. See a mess? Call it out. See something on TV? Comment on it. Be a sarcastic AI companion who's not afraid to be funny and mean. Short and punchy.",
        ]

        data = {
            "client_id": self.client_id,
            "user_message": random.choice(observation_prompts)
        }

        files = {"image": ("image.jpg", image_data, "image/jpeg")}

        try:
            print("💭 Thinking of something to say...")
            response = requests.post(
                f"{self.server_url}/api/process-interaction",
                data=data,
                files=files,
                timeout=30
            )

            if response.status_code == 200:
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")
                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"💬 Klyra: {response_text}\n")
                    except:
                        pass

                if len(response.content) > 0:
                    self.play_audio(response.content)

        except Exception as e:
            print(f"Error: {e}")

        # Schedule next observation
        self.next_observation = time.time() + random.randint(
            self.observation_interval_min,
            self.observation_interval_max
        )

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

                if self.detect_speech(data):
                    has_speech = True

            stream.stop_stream()
            stream.close()

            if not has_speech:
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

    def record_until_silence(self, max_duration=15, silence_threshold=300, silence_duration=1.5):
        """Record audio until silence is detected"""
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            frames = []
            silent_chunks = 0
            chunks_for_silence = int(self.rate / self.chunk * silence_duration)
            max_chunks = int(self.rate / self.chunk * max_duration)

            print("   🎤 Recording... (speak your command)")

            for i in range(max_chunks):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.abs(audio_data).mean()

                if volume < silence_threshold:
                    silent_chunks += 1
                    if silent_chunks >= chunks_for_silence:
                        print("   ⏸️  Silence detected, processing...")
                        break
                else:
                    silent_chunks = 0

            stream.stop_stream()
            stream.close()

            if len(frames) == 0:
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
                    return result.get("text", "").lower()
            return None
        except:
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
        except:
            pass

    def process_command(self, text):
        """Send command to Klyra"""
        print(f"You: {text}")

        image_data, _ = self.capture_image()

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
        audio_data = self.record_with_speech_detection(duration=2)

        if not audio_data:
            print(".", end="", flush=True)
            return False

        print("\n🎤 (heard speech, checking...)")
        text = self.transcribe_audio(audio_data)

        if not text:
            return False

        print(f"   Heard: '{text}'")

        text_clean = text.replace(",", "").replace(".", "").replace("!", "").replace("?", "")

        wake_word_variants = ["hey buddy", "hey body", "hey budy", "hey buddie"]
        wake_word_detected = any(variant in text_clean for variant in wake_word_variants)

        if wake_word_detected:
            print(f"✓ Wake word detected!")

            command = text_clean
            for variant in wake_word_variants:
                command = command.replace(variant, "").strip()

            if command and len(command) > 3:
                self.process_command(command)
            else:
                audio_data = self.record_until_silence()
                if audio_data:
                    command = self.transcribe_audio(audio_data)
                    if command:
                        self.process_command(command)

            return True

        return False

    def run(self):
        """Run companion mode"""
        print("="*50)
        print("KLYRA - AI COMPANION MODE")
        print("="*50)
        print("🤖 Klyra will observe you and make comments")
        print("🎤 Say 'HEY BUDDY' to talk to Klyra")
        print("Press Ctrl+C to exit")
        print("="*50 + "\n")

        if not self.check_server():
            return

        self.running = True
        print("👁️  Klyra is watching and listening...\n")

        try:
            while self.running:
                # Check if it's time for a spontaneous observation
                if time.time() >= self.next_observation:
                    self.make_spontaneous_comment()

                # Listen for wake word
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
    import base64  # Import here for the client
    client = CompanionClient()
    client.run()
