"""
Klyra Machine - AI Companion Mode
Monitors you and makes spontaneous comments + responds to wake word
"""

import base64
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

# Try to import webrtcvad, but continue without it if not available
try:
    import webrtcvad
    HAS_WEBRTCVAD = True
except ImportError:
    HAS_WEBRTCVAD = False
    print("NOTE: webrtcvad not available, using volume-based speech detection")

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
        self.chunk = 480  # 30ms at 16kHz for WebRTC VAD compatibility
        print("Step 6: Audio ready!")

        # Initialize pygame
        print("Step 7: Starting pygame mixer...")
        pygame.mixer.init()
        print("Step 8: Pygame ready!")

        # Initialize WebRTC VAD for better speech detection (if available)
        if HAS_WEBRTCVAD:
            print("Step 9: Starting voice activity detection...")
            self.vad = webrtcvad.Vad(2)  # Aggressiveness 0-3 (2 is moderate)
            print("Step 10: VAD ready!")
        else:
            self.vad = None
            print("Step 9-10: Using volume-based speech detection")

        # Companion state
        self.last_observation_time = time.time()
        self.observation_interval_min = 600   # 10 minutes between observations
        self.observation_interval_max = 900   # 15 minutes between observations
        self.no_motion_recheck = 60           # When no motion seen, re-check this often
        self.next_observation = time.time() + random.randint(
            self.observation_interval_min, self.observation_interval_max
        )

        self.last_frame = None
        self.running = False
        self.is_user_speaking = False  # Track if user is currently speaking
        self.is_speaking = False  # Track if Klyra is currently speaking (audio playback)

        # Motion gate via MOG2 background subtraction. Cheap, no API cost.
        # Sampled continuously from the main loop so we don't have to do
        # warm-up bursts at trigger time.
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=120, varThreshold=25, detectShadows=False
        )
        self.motion_check_interval = 5.0       # seconds between samples
        self.last_motion_check = 0.0
        self.bg_warmup_remaining = 5           # ignore the first N samples
        self.motion_history = []               # rolling list of recent scores
        self.motion_history_max = 12           # ~60s of history at 5s cadence
        self.motion_threshold = 0.005          # 0.5% of frame as foreground

        # Perceptual-hash dedup: don't re-comment on the same scene we just
        # commented on. Scene "fingerprint" is an 8x8 average-hash (64 bits).
        self.last_commented_hash = None
        self.dedup_max_hamming = 8             # <= 8 bit differences = same scene

        print("Step 11: All systems ready!\n")

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

    def sample_motion(self):
        """Tick the MOG2 background subtractor. Cheap; safe to call every
        iteration of the main loop — gated internally by motion_check_interval.
        Run continuously so the subtractor learns the background and the
        motion gate has fresh state when the spontaneous timer fires."""
        now = time.time()
        if now - self.last_motion_check < self.motion_check_interval:
            return
        self.last_motion_check = now
        if not self.camera.isOpened():
            return
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return

        fg_mask = self.bg_subtractor.apply(frame)

        # Burn the first few samples while the model warms up — they're all
        # ~100% "foreground" because the model has no background yet.
        if self.bg_warmup_remaining > 0:
            self.bg_warmup_remaining -= 1
            return

        score = float(np.count_nonzero(fg_mask > 200)) / float(fg_mask.size)
        self.motion_history.append(score)
        if len(self.motion_history) > self.motion_history_max:
            self.motion_history.pop(0)

    def has_recent_motion(self):
        """True if any sample in our recent window crossed the motion
        threshold. Uses peak (not mean) because a single still frame in the
        middle of an active period shouldn't suppress a comment."""
        if not self.motion_history:
            return False
        return max(self.motion_history) > self.motion_threshold

    def _average_hash(self, frame, hash_size=8):
        """64-bit average-hash perceptual fingerprint of a frame. Zero deps:
        downscale to 8x8 grayscale, threshold each pixel against the mean.
        Hamming distance between two hashes ~= scene similarity."""
        small = cv2.resize(frame, (hash_size, hash_size),
                           interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        bits = (gray > gray.mean()).flatten().astype(np.uint8)
        h = 0
        for b in bits:
            h = (h << 1) | int(b)
        return h

    @staticmethod
    def _hamming(a, b):
        return bin(a ^ b).count("1")

    def apply_noise_gate(self, audio_data, threshold=500):
        """Apply noise gate to remove background noise"""
        # Simple noise gate - zeros out audio below threshold
        audio_array = np.frombuffer(audio_data, dtype=np.int16).copy()
        volume = np.abs(audio_array).mean()
        if volume < threshold:
            audio_array = np.zeros_like(audio_array)
        return audio_array.tobytes()

    def detect_speech(self, audio_chunk):
        """Check if audio chunk has speech using WebRTC VAD or volume threshold"""
        # If WebRTC VAD is available, use it
        if self.vad and len(audio_chunk) == 960:
            try:
                # WebRTC VAD requires specific frame lengths (10, 20, or 30 ms)
                # At 16000 Hz, 30ms = 480 samples = 960 bytes
                is_speech = self.vad.is_speech(audio_chunk, self.rate)
                return is_speech
            except:
                pass  # Fall through to volume detection

        # Fallback to volume detection (or if VAD not available)
        audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
        volume = np.abs(audio_data).mean()
        return volume > 1500

    def check_if_user_speaking(self):
        """Quick check if user is currently speaking - non-blocking"""
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            # Check a few quick samples
            is_speaking = False
            for _ in range(3):
                data = stream.read(self.chunk, exception_on_overflow=False)
                if self.detect_speech(data):
                    is_speaking = True
                    break

            stream.stop_stream()
            stream.close()
            return is_speaking
        except:
            return False

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
        # Motion gate: don't burn API calls observing an empty room.
        # has_recent_motion() captures its own pair of frames, so this also
        # serves as a camera health check before we commit to an interaction.
        if not self.has_recent_motion():
            print(f"(no motion — rechecking in {self.no_motion_recheck}s)")
            self.next_observation = time.time() + self.no_motion_recheck
            return

        print("\n👁️  *Klyra observes you*")

        result = self.capture_image()
        if result is None:
            print("⚠️  Camera unavailable, skipping observation")
            self.next_observation = time.time() + self.no_motion_recheck
            return
        image_data, frame = result
        if not image_data:
            self.next_observation = time.time() + self.no_motion_recheck
            return

        # pHash dedup: don't re-comment on a scene we already commented on.
        # Cheap (8x8 grayscale + bit comparison), no API call.
        scene_hash = self._average_hash(frame)
        if self.last_commented_hash is not None:
            distance = self._hamming(scene_hash, self.last_commented_hash)
            if distance <= self.dedup_max_hamming:
                print(f"(scene unchanged from last comment, hamming={distance}; skipping)")
                # Push to a half-interval — the scene may genuinely change soon.
                half = (self.observation_interval_min + self.observation_interval_max) // 4
                self.next_observation = time.time() + half
                return

        # Update last_frame for any other consumer of detect_motion()
        self.detect_motion(frame)

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

                # Only remember the scene we successfully commented on, so a
                # failed network call doesn't poison the dedup state.
                self.last_commented_hash = scene_hash

        except Exception as e:
            print(f"Error: {e}")

        # Schedule next observation
        self.next_observation = time.time() + random.randint(
            self.observation_interval_min,
            self.observation_interval_max
        )

    def preprocess_audio(self, frames):
        """Apply noise reduction and audio enhancement"""
        # Combine all frames
        audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)

        # Apply simple high-pass filter to remove low-frequency noise
        # This helps reduce rumble and background hum
        from scipy import signal
        # High-pass filter at 80Hz to remove low-frequency noise
        sos = signal.butter(4, 80, 'hp', fs=self.rate, output='sos')
        filtered = signal.sosfilt(sos, audio_data)

        # Normalize audio to maximize volume
        max_val = np.abs(filtered).max()
        if max_val > 0:
            filtered = filtered * (32767 / max_val * 0.9)  # 90% of max to avoid clipping

        return filtered.astype(np.int16).tobytes()

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

            # Apply audio preprocessing
            processed_audio = self.preprocess_audio(frames)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.rate)
                wf.writeframes(processed_audio)

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

            # Apply audio preprocessing
            processed_audio = self.preprocess_audio(frames)

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wf.setframerate(self.rate)
                wf.writeframes(processed_audio)

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
            # Mark that we're playing audio (so we don't listen to ourselves)
            self.is_speaking = True

            pygame.mixer.music.unload()
            with open("temp_response.mp3", 'wb') as f:
                f.write(audio_data)
            pygame.mixer.music.load("temp_response.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()

            # Add extra delay to ensure audio is fully done
            time.sleep(0.5)

            # Mark that we're done speaking
            self.is_speaking = False
        except:
            self.is_speaking = False
            pass

    def listen_for_followup(self, timeout=5):
        """Listen for a follow-up response after Buddy speaks"""
        print("\n👂 Listening for follow-up... (speak within 5 seconds or stay silent)")

        # Wait and check if user starts speaking
        start_time = time.time()
        while time.time() - start_time < timeout:
            audio_data = self.record_with_speech_detection(duration=1)
            if audio_data:
                # User is speaking! Get the full command
                print("🎤 Heard you! Continue speaking...")

                # Record until silence
                full_audio = self.record_until_silence()
                if full_audio:
                    command = self.transcribe_audio(full_audio)
                    if command:
                        self.process_command(command)
                        return
            time.sleep(0.1)

        print("(No follow-up detected)\n")

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
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")
                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"Klyra: {response_text}\n")
                    except:
                        pass

                if len(response.content) > 0:
                    self.play_audio(response.content)

                    # After Buddy finishes talking, listen for a follow-up response
                    self.listen_for_followup()

        except Exception as e:
            print(f"Error: {e}")

    def listen_for_wake_word(self):
        """Listen for wake word with speech detection"""
        # Don't listen while Klyra is speaking
        if self.is_speaking:
            time.sleep(0.1)
            return False

        audio_data = self.record_with_speech_detection(duration=2)

        if not audio_data:
            print(".", end="", flush=True)
            return False

        print("\n🎤 (heard speech, checking...)")
        text = self.transcribe_audio(audio_data)

        if not text:
            return False

        print(f"   Heard: '{text}'")

        # Detect hallucination bug - if text is too repetitive or too long, ignore it
        if len(text) > 300 or text.count("hey buddy") > 3:
            print("   ⚠️  Ignoring (likely microphone glitch)")
            return False

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
                # Tick the background-subtraction motion sampler. Internally
                # rate-limited; cheap when nothing's due.
                self.sample_motion()

                # Check if it's time for a spontaneous observation
                if time.time() >= self.next_observation:
                    # Only make observation if user is NOT speaking
                    if not self.check_if_user_speaking():
                        self.make_spontaneous_comment()
                    else:
                        # User is speaking, reschedule for later
                        print("(User speaking, delaying observation)")
                        self.next_observation = time.time() + 30

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
    client = CompanionClient()
    client.run()
