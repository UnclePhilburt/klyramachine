"""
Klyra Machine - Vosk Local Wake Word Detection
100% offline wake word detection - no API calls!
"""

print("="*60)
print("KLYRA CLIENT STARTUP - VOSK OFFLINE WAKE WORD")
print("="*60)
print(f"Startup time: {__import__('datetime').datetime.now()}")
print("")

print("[IMPORT] Loading Python modules...")
import sys
print(f"[IMPORT]   Python: {sys.version}")
print(f"[IMPORT]   Executable: {sys.executable}")

import os
print(f"[IMPORT]   ✓ OS")

import cv2
print(f"[IMPORT]   ✓ OpenCV {cv2.__version__}")

import pyaudio
print(f"[IMPORT]   ✓ PyAudio")

import wave
print(f"[IMPORT]   ✓ Wave")

import io
print(f"[IMPORT]   ✓ IO")

import requests
print(f"[IMPORT]   ✓ Requests {requests.__version__}")

import json
print(f"[IMPORT]   ✓ JSON")

import time
print(f"[IMPORT]   ✓ Time")

import pygame
print(f"[IMPORT]   ✓ Pygame {pygame.version.ver}")

import numpy as np
print(f"[IMPORT]   ✓ NumPy {np.__version__}")

print(f"[IMPORT]   Loading Vosk (offline speech recognition)...")
from vosk import Model, KaldiRecognizer
print(f"[IMPORT]   ✓ Vosk")

print("[IMPORT] All imports loaded successfully!")
print("")


class VoskWakeWordClient:
    def __init__(self, config_path="config.json"):
        print("Starting Klyra with Vosk Local Wake Word Detection...")
        print("Step 1: Loading config...")

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.server_url = self.config["server_url"]
        self.client_id = self.config["client_id"]
        self.wake_word = self.config.get("wake_word", "hey buddy").lower()
        print(f"Step 2: Config loaded - {self.server_url}")
        print(f"   Wake word: {self.wake_word}")

        # Initialize Vosk
        print("Step 3: Loading Vosk model...")
        model_path = self.config.get("vosk_model_path", "vosk-model-small-en-us-0.15")

        if not os.path.exists(model_path):
            print(f"ERROR: Vosk model not found at {model_path}")
            print("Please download a model from https://alphacephei.com/vosk/models")
            print("Recommended: vosk-model-small-en-us-0.15 (40MB)")
            print(f"Extract it to: {model_path}")
            sys.exit(1)

        try:
            self.vosk_model = Model(model_path)
            self.vosk_recognizer = KaldiRecognizer(self.vosk_model, 16000)
            self.vosk_recognizer.SetWords(True)
            print(f"Step 4: Vosk model loaded! (100% offline)")
        except Exception as e:
            print(f"ERROR loading Vosk model: {e}")
            sys.exit(1)

        # Initialize camera
        print("Step 5: Starting camera...")
        camera_enabled = self.config.get("enable_camera", True)
        if camera_enabled:
            self.camera = cv2.VideoCapture(self.config.get("camera_index", 0))
            time.sleep(0.5)
            print("Step 6: Camera ready!")
        else:
            self.camera = None
            print("Step 6: Camera disabled (faster responses)")

        # Initialize audio
        print("Step 7: Starting audio...")
        self.audio = pyaudio.PyAudio()

        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 4096  # Larger chunk for Vosk

        # Auto-pick input device: prefer PulseAudio/PipeWire "Default Source"
        # (honors `pactl set-default-source`), then probe each hardware mic
        # for an actual signal so we don't pick a silent onboard jack.
        self.input_device_index = self._pick_input_device()

        # Check for microphone
        has_input = self.input_device_index is not None
        if not has_input:
            print("")
            print("WARNING: NO MICROPHONE DETECTED!")
            print("WARNING: Switching to TEXT MODE automatically...")
            print("")
            self.audio.terminate()

            # Switch to text mode
            print("INFO: Launching text mode client...")
            import subprocess
            subprocess.run([sys.executable, "client_text.py"])
            sys.exit(0)

        # TEST the microphone with actual recording
        print("Step 8: Testing microphone...")
        try:
            test_stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            # Try to read a few chunks
            for i in range(3):
                data = test_stream.read(self.chunk, exception_on_overflow=False)

            test_stream.stop_stream()
            test_stream.close()

            print("Step 9: Microphone test PASSED!")
            print("Step 10: Audio ready!")

        except Exception as e:
            print(f"ERROR: Microphone test FAILED: {e}")
            print("")
            print("WARNING: ═══════════════════════════════════════════════")
            print("WARNING: MICROPHONE NOT WORKING!")
            print(f"WARNING: Error: {e}")
            print("WARNING: Switching to TEXT MODE...")
            print("WARNING: ═══════════════════════════════════════════════")
            print("")
            self.audio.terminate()

            # Switch to text mode
            print("INFO: Launching text mode client...")
            import subprocess
            subprocess.run([sys.executable, "client_text.py"])
            sys.exit(0)

        # Initialize pygame for audio playback
        print("Step 9: Starting pygame mixer...")
        try:
            # Initialize with Pi-compatible settings
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            print("Step 10: Pygame mixer initialized at 44100Hz")
        except:
            print("Step 10: 44100Hz failed, trying 22050Hz...")
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=2048)
            print("Step 10: Pygame mixer initialized at 22050Hz")
        print("Step 11: Pygame ready!")

        self.running = False
        print("Step 11: All systems ready!")
        print("")

        # Play startup ding to confirm audio output works
        print("Step 12: Testing audio output...")
        self.play_ding()
        print("Step 13: Audio output test complete!")
        print("")

    def record_until_silence(self, max_duration=15, silence_threshold=300, silence_duration=1.5):
        """Record audio until silence is detected"""
        try:
            # Small delay to let wake word finish
            time.sleep(0.3)

            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            # Clear any buffered audio
            for _ in range(3):
                try:
                    stream.read(self.chunk, exception_on_overflow=False)
                except:
                    pass

            frames = []
            silent_chunks = 0
            speech_chunks = 0
            chunks_for_silence = int(self.rate / self.chunk * silence_duration)
            max_chunks = int(self.rate / self.chunk * max_duration)

            print("   🎤 Recording... (speak your command)")

            for i in range(max_chunks):
                data = stream.read(self.chunk, exception_on_overflow=False)
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
                    silent_chunks = 0
                    speech_chunks += 1

            stream.stop_stream()
            stream.close()

            # Check if we got enough actual speech
            if len(frames) == 0 or speech_chunks < 2:
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
            print(f"Recording error: {e}")
            return None

    def transcribe_audio(self, audio_data):
        """Transcribe with Whisper (for commands only, not wake word)"""
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
        if not self.camera or not self.camera.isOpened():
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

    def play_ding(self):
        """Play ding sound when wake word is detected"""
        try:
            ding_path = "ding.ogg"
            if os.path.exists(ding_path):
                ding_sound = pygame.mixer.Sound(ding_path)
                ding_sound.play()
        except Exception as e:
            pass

    def process_command(self, text):
        """Send command to Klyra"""
        print(f"You: {text}")

        # Only capture image if camera is enabled
        image_data = None
        if self.camera:
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

    def _pick_input_device(self):
        """Auto-pick the best input device.

        Strategy:
        1. Prefer PulseAudio/PipeWire 'Default Source' / 'pulse' / 'pipewire' /
           'default' — that routes to whatever the user set with
           `pactl set-default-source`, so the same code works on every box.
        2. Otherwise, probe each remaining hardware input by recording briefly
           and pick the loudest. This avoids silent onboard jacks (e.g. the
           Intel ICH MIC ADC that exists but has nothing plugged in) when
           there's a real USB mic also present.
        Skip obvious non-mics: monitor (loopback of speakers), HDMI, IEC958.
        """
        device_count = self.audio.get_device_count()

        skip_keywords = ('monitor', 'iec958', 'hdmi', 'loopback', 'output', 'sysdefault')
        preferred = ('default source', 'pipewire', 'pulse')

        candidates = []
        for i in range(device_count):
            try:
                info = self.audio.get_device_info_by_index(i)
            except Exception:
                continue
            if info.get('maxInputChannels', 0) <= 0:
                continue
            name = info.get('name', '')
            lname = name.lower()
            if any(k in lname for k in skip_keywords):
                continue
            candidates.append((i, name, lname))

        if not candidates:
            return None

        for i, name, lname in candidates:
            if any(p in lname for p in preferred):
                print(f"   Auto-picked input #{i}: '{name}' (system default route)")
                return i

        best_idx = None
        best_vol = -1.0
        for i, name, _ in candidates:
            try:
                s = self.audio.open(
                    format=self.audio_format,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    input_device_index=i,
                    frames_per_buffer=self.chunk,
                )
            except Exception as e:
                print(f"   Skipping input #{i} '{name}': can't open ({e})")
                continue
            try:
                vols = []
                for _ in range(5):
                    data = s.read(self.chunk, exception_on_overflow=False)
                    arr = np.frombuffer(data, dtype=np.int16)
                    vols.append(float(np.abs(arr).mean()))
                avg = sum(vols) / len(vols)
                print(f"   Input #{i} '{name}': avg level {avg:.1f}")
                if avg > best_vol:
                    best_vol = avg
                    best_idx = i
            except Exception as e:
                print(f"   Input #{i} '{name}': read failed ({e})")
            finally:
                try:
                    s.stop_stream()
                    s.close()
                except Exception:
                    pass

        if best_idx is not None:
            print(f"   Auto-picked input #{best_idx} (highest signal level)")
        return best_idx

    def listen_for_wake_word(self):
        """Listen for wake word using Vosk (100% local)"""
        try:
            stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk
            )

            print("👂 Listening locally for wake word...")
            print(f"   Say: '{self.wake_word.upper()}'")
            print("   (100% offline - no cloud calls!)")
            print("   (Press Ctrl+C to exit)\n")

            while self.running:
                # Read audio frame
                data = stream.read(self.chunk, exception_on_overflow=False)

                # Process with Vosk (offline)
                if self.vosk_recognizer.AcceptWaveform(data):
                    result = json.loads(self.vosk_recognizer.Result())
                    text = result.get("text", "").lower()

                    if text:
                        print(f"[Vosk heard: '{text}']")

                        # Check for wake word
                        if self.wake_word in text:
                            print(f"\n✓ Wake word '{self.wake_word}' detected!")

                            # Play ding sound
                            self.play_ding()

                            # Stop listening and close stream
                            stream.stop_stream()
                            stream.close()

                            # Listen for command
                            audio_data = self.record_until_silence()
                            if audio_data:
                                command = self.transcribe_audio(audio_data)
                                if command:
                                    self.process_command(command)
                                else:
                                    print("   ⚠️  Couldn't understand the command\n")

                            # Restart listening
                            print("\n👂 Listening for wake word again...\n")
                            stream = self.audio.open(
                                format=self.audio_format,
                                channels=self.channels,
                                rate=self.rate,
                                input=True,
                                input_device_index=self.input_device_index,
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
        print("="*60)
        print("KLYRA - VOSK LOCAL WAKE WORD MODE")
        print("="*60)
        print(f"🎤 Wake word: '{self.wake_word.upper()}'")
        print("🔒 100% Offline - No cloud calls for wake word!")
        print("Press Ctrl+C to exit")
        print("="*60 + "\n")

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
        if self.camera and self.camera.isOpened():
            self.camera.release()
        self.audio.terminate()
        pygame.mixer.quit()
        print("Goodbye! 👋")


if __name__ == "__main__":
    try:
        print("="*60)
        print("STARTING KLYRA VOSK CLIENT")
        print("="*60)
        print(f"Working directory: {os.getcwd()}")
        print(f"Python executable: {sys.executable}")
        print("")

        client = VoskWakeWordClient()
        client.run()
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\n\nTroubleshooting:")
        print("1. Check if Vosk model exists: ls -la vosk-model-small-en-us-0.15/")
        print("2. Check logs: sudo journalctl -u klyra -n 50")
        print("3. Try running manually: python client_vosk.py")
        sys.exit(1)
