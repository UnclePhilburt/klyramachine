"""
Audio input module for capturing voice and converting to text
Uses OpenAI Whisper API for speech recognition
"""

import pyaudio
import wave
import io
from openai import OpenAI


class AudioInput:
    """Handles microphone input and speech-to-text"""

    def __init__(self, api_key):
        """Initialize audio input and OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self.audio = None
        self.audio_available = False

        try:
            self.audio = pyaudio.PyAudio()
            self.audio_available = True

            # Audio recording parameters
            self.format = pyaudio.paInt16
            self.channels = 1
            self.rate = 16000
            self.chunk = 1024
            self.record_seconds = 5  # Maximum recording time

            print("Audio input initialized")
        except Exception as e:
            print(f"Audio not available: {e}")
            print("Running in TEXT INPUT mode")
            self.audio_available = False

    def record_audio(self, duration=None):
        """
        Record audio from microphone

        Args:
            duration: Recording duration in seconds (default from config)

        Returns:
            Audio data as bytes
        """
        if not self.audio_available:
            print("Audio not available - use text input instead")
            return None

        if duration is None:
            duration = self.record_seconds

        print("Listening...")

        try:
            stream = self.audio.open(
                format=self.format,
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

            # Convert to WAV format
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))

            wav_buffer.seek(0)
            return wav_buffer

        except Exception as e:
            print(f"Error recording audio: {e}")
            return None

    def listen_for_speech(self, duration=5):
        """
        Record audio and convert to text using Whisper

        Args:
            duration: How long to listen (seconds)

        Returns:
            Transcribed text
        """
        audio_data = self.record_audio(duration)

        if audio_data is None:
            return None

        try:
            # Use OpenAI Whisper API
            audio_data.name = "speech.wav"  # Whisper API needs a filename
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_data
            )

            text = transcript.text.strip()
            if text:
                print(f"Heard: {text}")
                return text
            else:
                return None

        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None

    def listen_with_wake_word(self, wake_word="hey klyra"):
        """
        Continuously listen for a wake word, then capture full speech

        Returns:
            Transcribed speech (without wake word)
        """
        # For simplicity, we'll do basic continuous listening
        # In production, you'd want voice activity detection
        print(f"Listening for '{wake_word}'...")

        # Listen for short segments
        text = self.listen_for_speech(duration=3)

        if text and wake_word.lower() in text.lower():
            print("Wake word detected! Listening for your message...")
            # Remove wake word and capture full message
            text = text.lower().replace(wake_word.lower(), "").strip()

            if not text:
                # If nothing after wake word, listen again
                text = self.listen_for_speech(duration=5)

            return text

        return None

    def cleanup(self):
        """Clean up audio resources"""
        if self.audio:
            self.audio.terminate()
            print("Audio input cleaned up")


# Test the audio input module
if __name__ == "__main__":
    import json

    print("Testing audio input...")

    # Load config
    with open("config.json", 'r') as f:
        config = json.load(f)

    audio = AudioInput(config["openai_api_key"])
    print("Say something...")
    text = audio.listen_for_speech(duration=5)
    print(f"You said: {text}")
    audio.cleanup()
