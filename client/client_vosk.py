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

# faster-whisper is optional. If config picks local STT but the package
# is missing or the CPU can't run CTranslate2, we fall back to the cloud
# transcriber.
#
# Force CTranslate2 to a CPU ISA the host actually supports. Some VMs
# expose a stripped-down feature set (no AVX2/FMA), and the prebuilt
# CTranslate2 wheel will SIGILL on import (uncatchable in Python). We
# probe in a subprocess first so a crash there doesn't take Klyra down.
# GENERIC is slower but works on any x86_64.
os.environ.setdefault("CT2_FORCE_CPU_ISA", "GENERIC")

HAVE_FASTER_WHISPER = False
try:
    import subprocess as _subproc
    _probe = _subproc.run(
        [sys.executable, "-c",
         "import os; os.environ.setdefault('CT2_FORCE_CPU_ISA','GENERIC'); "
         "from faster_whisper import WhisperModel"],
        capture_output=True, timeout=30,
    )
    if _probe.returncode == 0:
        from faster_whisper import WhisperModel
        print(f"[IMPORT]   ✓ faster-whisper (local Whisper)")
        HAVE_FASTER_WHISPER = True
    else:
        err = (_probe.stderr or b"").decode(errors="ignore").strip().splitlines()
        last = err[-1] if err else f"exit {_probe.returncode}"
        print(f"[IMPORT]   ⚠  faster-whisper unusable on this CPU ({last}); cloud STT only")
except Exception as _e:
    print(f"[IMPORT]   ⚠  faster-whisper probe failed ({_e}); cloud STT only")

# piper-tts is optional. Same pattern as faster-whisper: probe in a
# subprocess so a native-library SIGILL can't kill Klyra at startup.
HAVE_PIPER = False
try:
    import subprocess as _subproc
    _probe = _subproc.run(
        [sys.executable, "-c", "from piper.voice import PiperVoice"],
        capture_output=True, timeout=30,
    )
    if _probe.returncode == 0:
        from piper.voice import PiperVoice
        print(f"[IMPORT]   ✓ piper-tts (local TTS)")
        HAVE_PIPER = True
    else:
        err = (_probe.stderr or b"").decode(errors="ignore").strip().splitlines()
        last = err[-1] if err else f"exit {_probe.returncode}"
        print(f"[IMPORT]   ⚠  piper-tts unusable on this CPU ({last}); cloud TTS only")
except Exception as _e:
    print(f"[IMPORT]   ⚠  piper-tts probe failed ({_e}); cloud TTS only")

HAS_WEBRTCVAD = False
try:
    import webrtcvad
    HAS_WEBRTCVAD = True
    print(f"[IMPORT]   ✓ webrtcvad (voice activity detection)")
except ImportError:
    print(f"[IMPORT]   ⚠  webrtcvad unavailable; falling back to volume threshold")

# kokoro-onnx is optional. Same probe-then-import pattern as faster-whisper
# and piper-tts so a native-library issue can't kill Klyra at startup.
HAS_KOKORO = False
try:
    import subprocess as _subproc
    _probe = _subproc.run(
        [sys.executable, "-c", "from kokoro_onnx import Kokoro"],
        capture_output=True, timeout=30,
    )
    if _probe.returncode == 0:
        from kokoro_onnx import Kokoro
        print(f"[IMPORT]   ✓ kokoro-onnx (local TTS)")
        HAS_KOKORO = True
    else:
        err = (_probe.stderr or b"").decode(errors="ignore").strip().splitlines()
        last = err[-1] if err else f"exit {_probe.returncode}"
        print(f"[IMPORT]   ⚠  kokoro-onnx unusable ({last})")
except Exception as _e:
    print(f"[IMPORT]   ⚠  kokoro-onnx probe failed ({_e})")

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

        # Optional local Whisper for command transcription. Lazy: skip if
        # disabled or package missing — transcribe_audio falls back to cloud.
        # Using int8 quantization keeps RAM low enough for low-end hosts.
        self.whisper = None
        stt_engine = self.config.get("stt_engine", "local")
        whisper_size = self.config.get("whisper_model", "tiny.en")
        if stt_engine == "local" and HAVE_FASTER_WHISPER:
            print(f"Step 4b: Loading faster-whisper '{whisper_size}'...")
            try:
                self.whisper = WhisperModel(whisper_size, device="cpu", compute_type="int8")
                print(f"Step 4c: Whisper loaded (local STT enabled)")
            except Exception as e:
                print(f"   ⚠  Whisper load failed: {e}; falling back to cloud STT")
                self.whisper = None
        elif stt_engine == "local":
            print(f"   ⚠  stt_engine=local but faster-whisper unavailable; using cloud")

        # Local TTS dispatch. tts_engine controls which provider:
        #   "kokoro"          -> Kokoro (best quality, slightly slower)
        #   "local" / "piper" -> Piper  (fastest, robotic)
        #   "cloud"           -> ElevenLabs via server
        # Whichever is selected loads here; if it fails, synthesize_local
        # returns None and process_command falls through to cloud TTS.
        self.piper_voice = None
        self.kokoro = None
        self.kokoro_voice = self.config.get("kokoro_voice", "bm_lewis")
        tts_engine = self.config.get("tts_engine", "local")

        if tts_engine == "kokoro" and HAS_KOKORO:
            kk_model = self.config.get("kokoro_model_path", "kokoro/kokoro-v1.0.onnx")
            kk_voices = self.config.get("kokoro_voices_path", "kokoro/voices-v1.0.bin")
            if os.path.exists(kk_model) and os.path.exists(kk_voices):
                print(f"Step 4d: Loading Kokoro ({self.kokoro_voice})...")
                try:
                    self.kokoro = Kokoro(kk_model, kk_voices)
                    print(f"Step 4e: Kokoro loaded (local TTS enabled)")
                except Exception as e:
                    print(f"   ⚠  Kokoro load failed: {e}; falling back to cloud TTS")
                    self.kokoro = None
            else:
                print(f"   ⚠  Kokoro model files not found at {kk_model}/{kk_voices}; using cloud TTS")
        elif tts_engine == "kokoro":
            print(f"   ⚠  tts_engine=kokoro but kokoro-onnx unavailable; using cloud")
        elif tts_engine in ("local", "piper") and HAVE_PIPER:
            voice_path = self.config.get("piper_voice", "voices/en_US-lessac-medium.onnx")
            if os.path.exists(voice_path):
                print(f"Step 4d: Loading Piper voice '{voice_path}'...")
                try:
                    self.piper_voice = PiperVoice.load(voice_path)
                    print(f"Step 4e: Piper loaded (local TTS enabled)")
                except Exception as e:
                    print(f"   ⚠  Piper load failed: {e}; falling back to cloud TTS")
                    self.piper_voice = None
            else:
                print(f"   ⚠  Piper voice not found at {voice_path}; using cloud TTS")
                print(f"      Run ./download_piper_voice.sh to install it")
        elif tts_engine in ("local", "piper"):
            print(f"   ⚠  tts_engine={tts_engine} but piper-tts unavailable; using cloud")

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

        # WebRTC VAD: better silence detection than raw volume threshold,
        # especially with sensitive mics in noisy rooms. Aggressiveness 0-3;
        # 3 is most strict. Configurable via config.json.
        vad_agg = int(self.config.get("vad_aggressiveness", 3))
        vad_agg = max(0, min(3, vad_agg))
        self.vad = webrtcvad.Vad(vad_agg) if HAS_WEBRTCVAD else None

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

    def _chunk_has_speech(self, chunk_bytes):
        """Split a chunk into 30ms VAD frames; speech iff a majority vote.
        Single false-positive frames don't hold the recorder open.
        Returns None on VAD failure so caller can fall back to volume."""
        if not self.vad:
            return None
        # WebRTC VAD requires 10/20/30ms frames. 30ms at 16kHz = 480 samples = 960 bytes.
        # 4096-sample chunk → ~8 complete frames per chunk.
        frame_bytes = 960
        try:
            speech = 0
            total = 0
            for i in range(0, len(chunk_bytes) - frame_bytes + 1, frame_bytes):
                total += 1
                if self.vad.is_speech(chunk_bytes[i:i + frame_bytes], self.rate):
                    speech += 1
            if total == 0:
                return None
            # Require half the frames to vote speech. Tunable; raise to be
            # less sensitive, lower to catch quieter speech.
            print(f"   [vad {speech}/{total}]", end="", flush=True)
            return speech * 2 >= total
        except Exception:
            return None

    def record_until_silence(self, max_duration=15, silence_threshold=None,
                             silence_duration=0.8, pre_speech_timeout=None):
        """Record until silence is detected after the user has started speaking.
        Tolerates up to pre_speech_timeout seconds of silence at the start
        (lets the user take a beat to think before responding).

        silence_threshold and pre_speech_timeout default to config values
        when unset, so the settings UI can tune them without code changes."""
        if silence_threshold is None:
            silence_threshold = int(self.config.get("silence_threshold", 1500))
        if pre_speech_timeout is None:
            pre_speech_timeout = float(self.config.get("pre_speech_timeout", 4.0))
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

            frames = []
            silent_chunks = 0
            speech_chunks = 0
            pre_speech_silent_chunks = 0
            chunks_for_silence = int(self.rate / self.chunk * silence_duration)
            pre_speech_max_chunks = int(self.rate / self.chunk * pre_speech_timeout)
            max_chunks = int(self.rate / self.chunk * max_duration)

            print("   🎤 Recording... (speak your command)")

            for i in range(max_chunks):
                data = stream.read(self.chunk, exception_on_overflow=False)
                frames.append(data)

                # Volume floor: if the chunk is genuinely quiet, override
                # whatever VAD says. WebRTC VAD on hot mics sometimes calls
                # ambient noise speech; the volume number doesn't lie.
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = float(np.abs(audio_data).mean())
                print(f" vol={int(volume)}", end="", flush=True)

                if volume < silence_threshold:
                    is_speech = False
                else:
                    is_speech = self._chunk_has_speech(data)
                    if is_speech is None:
                        is_speech = True  # VAD failed, treat loud chunk as speech

                if speech_chunks == 0:
                    # Haven't heard speech yet — wait patiently up to pre_speech_timeout.
                    if is_speech:
                        speech_chunks = 1
                    else:
                        pre_speech_silent_chunks += 1
                        if pre_speech_silent_chunks >= pre_speech_max_chunks:
                            print("\n   ⚠️  No speech heard, giving up\n")
                            break
                else:
                    # Speech has started — now use end-of-utterance detection.
                    if not is_speech:
                        silent_chunks += 1
                        if silent_chunks >= chunks_for_silence:
                            print("\n========== SILENCE DETECTED — PROCESSING ==========\n")
                            self.play_ding()  # audible "got it, thinking" cue
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
        """Transcribe a WAV blob. Local faster-whisper if loaded, else cloud."""
        if self.whisper is not None:
            try:
                t0 = time.time()
                with wave.open(io.BytesIO(audio_data), 'rb') as wf:
                    sample_rate = wf.getframerate()
                    pcm = wf.readframes(wf.getnframes())
                samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
                if sample_rate != 16000:
                    # faster-whisper internally resamples, but only from 16k.
                    # We always record at 16k upstream, so this is just a guard.
                    print(f"   ⚠  Unexpected sample rate {sample_rate}, results may degrade")
                segments, _info = self.whisper.transcribe(samples, language="en", beam_size=1)
                text = " ".join(seg.text for seg in segments).strip()
                print(f"   [local whisper] {time.time()-t0:.2f}s")
                return text or None
            except Exception as e:
                print(f"Local transcription error: {e}; falling back to cloud")

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

    def play_audio(self, audio_data, fmt="mp3"):
        """Play audio bytes. fmt is 'mp3' (cloud) or 'wav' (local Piper)."""
        try:
            ext = "wav" if fmt == "wav" else "mp3"
            path = f"temp_response.{ext}"
            pygame.mixer.music.unload()
            with open(path, 'wb') as f:
                f.write(audio_data)
            pygame.mixer.music.load(path)
            volume = float(self.config.get("volume", 1.0))
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"Audio playback error: {e}")

    def synthesize_local(self, text):
        """Dispatch to whichever local TTS engine is loaded. Returns WAV bytes
        or None (caller falls back to cloud)."""
        if not text:
            return None
        if self.kokoro:
            return self._synthesize_kokoro(text)
        if self.piper_voice:
            return self._synthesize_piper(text)
        return None

    def _synthesize_piper(self, text):
        """Piper synthesis -> WAV bytes."""
        try:
            import wave, io
            t0 = time.time()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                self.piper_voice.synthesize_wav(text, wav_file)
            print(f"   [piper] {time.time()-t0:.2f}s")
            return buf.getvalue()
        except Exception as e:
            print(f"   ⚠  Piper synthesis failed: {e}; falling back to cloud audio")
            return None

    def _synthesize_kokoro(self, text):
        """Kokoro synthesis -> WAV bytes."""
        try:
            import wave, io
            t0 = time.time()
            speed = float(self.config.get("voice_speed", 1.0))
            samples, sr = self.kokoro.create(
                text, voice=self.kokoro_voice, speed=speed, lang="en-us"
            )
            pcm = (samples * 32767).clip(-32768, 32767).astype(np.int16)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sr)
                wav_file.writeframes(pcm.tobytes())
            print(f"   [kokoro {self.kokoro_voice}] {time.time()-t0:.2f}s")
            return buf.getvalue()
        except Exception as e:
            print(f"   ⚠  Kokoro synthesis failed: {e}; falling back to cloud audio")
            return None

    def _history_path(self):
        """Per-client history file. Created on first save."""
        fname = self.config.get("history_file", "history/{client_id}.json")
        fname = fname.format(client_id=self.client_id)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)

    def _load_history(self):
        """Load conversation history. Just user/assistant turns — system
        prompt is prepended fresh each call so prompt edits take effect
        without rewriting old files."""
        path = self._history_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"   ⚠  Failed to load history ({e}); starting fresh")
            return []

    def _save_history(self, history):
        """Persist history. Caps at last 50 turns (matches server)."""
        history = history[-50:]
        path = self._history_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠  Failed to save history: {e}")

    @staticmethod
    def _strip_stage_directions(text):
        """Remove '(sighs)', '(looking around)', '*smirks*' etc. — Mistral
        sometimes adds these despite the system prompt, and TTS reads them
        literally. Conservative: only strip if the parenthetical is short
        and looks like an action (lowercase, no question/punctuation inside)."""
        import re
        # (...) groups up to 40 chars, no internal parens, no sentence-ending
        text = re.sub(r"\(([^()?!.]{1,40})\)", "", text)
        # *...* asterisk-style stage directions
        text = re.sub(r"\*([^*\n]{1,40})\*", "", text)
        # Collapse double spaces left behind
        return re.sub(r"\s+", " ", text).strip()

    def _call_ollama(self, user_message, scene_context=None):
        """Call local Ollama with system prompt + persisted history.
        Returns response text, or None on failure (caller falls back)."""
        host = self.config.get("ollama_host", "http://localhost:11434")
        model = self.config.get("ollama_model", "mistral-small:22b")
        system_prompt = self.config.get("system_prompt", "")

        # Inject the user's name if configured. Cheap personalization that
        # also gives Klyra a stable identity to refer to in callbacks.
        user_name = self.config.get("user_name", "").strip()
        if user_name:
            system_prompt = f"{system_prompt}\n\nThe user's name is {user_name}."

        # Inline scene context like the server does — keeps history clean
        # (no system messages mid-conversation) and lets the model connect
        # what it sees to what it's hearing.
        user_content = user_message
        if scene_context:
            user_content = f"{user_message}\n[What you can see: {scene_context}]"

        history = self._load_history()
        history.append({"role": "user", "content": user_content})
        messages = [{"role": "system", "content": system_prompt}] + history

        try:
            t0 = time.time()
            r = requests.post(
                f"{host}/api/chat",
                json={"model": model, "messages": messages, "stream": False,
                      "options": {"temperature": 0.8, "num_predict": 200}},
                timeout=60,
            )
            r.raise_for_status()
            reply = r.json()["message"]["content"].strip()
            print(f"   [ollama {model}] {time.time()-t0:.2f}s")
        except Exception as e:
            print(f"   ⚠  Ollama call failed: {e}")
            return None

        reply = self._strip_stage_directions(reply)
        history.append({"role": "assistant", "content": reply})
        self._save_history(history)
        return reply

    def _get_scene_context(self):
        """Capture an image and get a scene description. Dispatches to local
        Ollama or cloud server based on config['vision_engine']:
            "local" -> Ollama at localhost (free, fast, no privacy concerns)
            "cloud" -> server /api/analyze-image (OpenAI Vision via Render)
            "off"   -> skip vision entirely
        Returns scene description text, or None on failure."""
        if not self.camera:
            return None
        # Backward compat: if vision_engine isn't set, fall back to the old
        # vision_enabled boolean (True->cloud, False->off).
        engine = self.config.get("vision_engine")
        if engine is None:
            engine = "cloud" if self.config.get("vision_enabled", True) else "off"
        if engine == "off":
            return None

        image_data = self.capture_image()
        if not image_data:
            return None

        if engine == "local":
            desc = self._vision_via_ollama(image_data)
        else:
            desc = self._vision_via_server(image_data)

        if desc:
            preview = desc if len(desc) <= 80 else desc[:77] + "..."
            print(f"   📷 Saw: {preview}")
        return desc

    def _vision_via_ollama(self, image_data):
        """Describe an image via local Ollama vision model.
        Uses /api/generate (legacy multimodal path) — moondream and some
        other vision models don't fully support the /api/chat endpoint with
        images, so generate is more reliable across model choices."""
        import base64
        host = self.config.get("ollama_host", "http://localhost:11434")
        model = self.config.get("ollama_vision_model", "moondream")
        img_b64 = base64.b64encode(image_data).decode("utf-8")
        prompt = (
            "Briefly describe what you see (1-2 sentences). Focus on the "
            "person, what they're doing, and notable objects. Only describe "
            "what is clearly visible; don't guess details you're unsure of."
        )
        try:
            t0 = time.time()
            r = requests.post(
                f"{host}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False,
                    "options": {"num_predict": 100, "temperature": 0.3},
                },
                timeout=60,
            )
            r.raise_for_status()
            desc = r.json().get("response", "").strip()
            print(f"   [vision-local {model}] {time.time()-t0:.2f}s")
            return desc or None
        except Exception as e:
            print(f"   ⚠  Local vision failed: {e}")
            return None

    def _vision_via_server(self, image_data):
        """Describe an image via the server's OpenAI Vision endpoint."""
        try:
            t0 = time.time()
            r = requests.post(
                f"{self.server_url}/api/analyze-image",
                files={"image": ("image.jpg", image_data, "image/jpeg")},
                timeout=30,
            )
            if r.status_code == 200:
                j = r.json()
                if j.get("success"):
                    desc = j.get("description", "").strip()
                    print(f"   [vision-cloud] {time.time()-t0:.2f}s")
                    return desc or None
        except Exception as e:
            print(f"   ⚠  Cloud vision failed: {e}")
        return None

    def _synthesize_via_server(self, text):
        """Fallback TTS via server when Piper isn't loaded."""
        try:
            r = requests.post(
                f"{self.server_url}/api/text-to-speech",
                data={"text": text}, timeout=30,
            )
            if r.status_code == 200 and r.content:
                return r.content
        except Exception as e:
            print(f"   ⚠  Server TTS failed: {e}")
        return None

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
        """Send command to Klyra via configured chat engine."""
        print(f"You: {text}")

        chat_engine = self.config.get("chat_engine", "openai")

        if chat_engine == "ollama":
            # Optional vision: capture frame -> server /api/analyze-image (OpenAI
            # Vision) -> pass description as scene_context to Ollama. Adds a
            # cloud round-trip (~2-4s) and ~$0.01-0.03 per call. Toggle off via
            # config "vision_enabled": false for fast/offline-only mode.
            scene = None
            if self.config.get("vision_enabled", True):
                scene = self._get_scene_context()

            print("💭 Thinking (local)...")
            reply = self._call_ollama(text, scene_context=scene)
            if not reply:
                print("   ⚠  Ollama unavailable — no response")
                return
            print(f"Klyra: {reply}\n")

            audio = self.synthesize_local(reply)
            if audio:
                self.play_audio(audio, fmt="wav")
            else:
                mp3 = self._synthesize_via_server(reply)
                if mp3:
                    self.play_audio(mp3, fmt="mp3")
            return

        # chat_engine == "openai" (existing path, unchanged)
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
                response_text = ""
                response_text_b64 = response.headers.get("X-Response-Text-B64", "")
                if response_text_b64:
                    try:
                        response_text = base64.b64decode(response_text_b64).decode('utf-8')
                        print(f"Klyra: {response_text}\n")
                    except:
                        pass

                # Prefer local synthesis (Kokoro or Piper) if loaded; fall
                # back to the MP3 the server returned. Existing setups
                # without local TTS keep working unchanged.
                local_wav = self.synthesize_local(response_text)
                if local_wav:
                    self.play_audio(local_wav, fmt="wav")
                elif len(response.content) > 0:
                    self.play_audio(response.content, fmt="mp3")

        except Exception as e:
            print(f"Error: {e}")

    def _pick_input_device(self):
        """Auto-pick the best input device.

        Strategy:
        0. If config sets `input_device_name`, pick the first input whose
           name contains that substring (case-insensitive). Escape hatch
           for boxes where auto-pick guesses wrong.
        1. Prefer PulseAudio/PipeWire 'Default Source' / 'pulse' / 'pipewire' /
           'default' — that routes to whatever the user set with
           `pactl set-default-source`, so the same code works on every box.
           Order: `pulse` before `pipewire`, because PortAudio's `pipewire`
           host on some PipeWire builds opens cleanly but never delivers
           audio (read() blocks forever); the `pulse` shim under PipeWire
           routes data correctly.
        2. Otherwise, probe each remaining hardware input by recording briefly
           and pick the loudest. This avoids silent onboard jacks (e.g. the
           Intel ICH MIC ADC that exists but has nothing plugged in) when
           there's a real USB mic also present.
        Skip obvious non-mics: monitor (loopback of speakers), HDMI, IEC958.
        """
        device_count = self.audio.get_device_count()

        skip_keywords = ('monitor', 'iec958', 'hdmi', 'loopback', 'output', 'sysdefault')
        preferred = ('default source', 'pulse', 'pipewire')

        # Optional explicit override from config. Honors the same
        # skip_keywords as auto-pick so a generic substring like
        # "default" doesn't accidentally match "sysdefault".
        override = (self.config.get('input_device_name') or '').lower().strip()
        if override:
            for i in range(device_count):
                try:
                    info = self.audio.get_device_info_by_index(i)
                except Exception:
                    continue
                if info.get('maxInputChannels', 0) <= 0:
                    continue
                lname = info.get('name', '').lower()
                if any(k in lname for k in skip_keywords):
                    continue
                if override in lname:
                    print(f"   Using configured input #{i}: '{info['name']}' (input_device_name match)")
                    return i
            print(f"   ⚠  input_device_name '{override}' not found; falling back to auto-pick")

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

        # Iterate preferred substrings in priority order, not device order.
        # Otherwise the first preferred-matching device by index wins, e.g.
        # `#8 pipewire` beats `#12 Default Source` even though the latter
        # is the more reliable route (PortAudio's pipewire host has been
        # observed to open cleanly but never deliver frames).
        for p in preferred:
            for i, name, lname in candidates:
                if p in lname:
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

                            # Conversation mode: process the initial command,
                            # then auto-listen for follow-ups (no wake word
                            # needed). When conversation_mode is False,
                            # process one turn and drop straight back to
                            # wake-word listening.
                            conv_mode = bool(self.config.get("conversation_mode", True))
                            audio_data = self.record_until_silence()
                            while audio_data:
                                command = self.transcribe_audio(audio_data)
                                if not command:
                                    print("   ⚠️  Couldn't understand the command\n")
                                    break
                                self.process_command(command)
                                if not conv_mode:
                                    break
                                print("\n👂 Listening for follow-up "
                                      "(no wake word needed)...\n")
                                self.play_ding()  # cue: "I'm listening"
                                audio_data = self.record_until_silence()

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
