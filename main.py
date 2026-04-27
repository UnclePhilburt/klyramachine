#!/usr/bin/env python3
"""
Klyra Machine - AI Vision Companion
Main program that integrates camera, microphone, OpenAI APIs, and speech output
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path

# We'll import these as we build out each module
# from camera import CameraCapture
# from vision import VisionProcessor
# from audio import AudioInput, AudioOutput
# from conversation import ConversationManager


class KlyraMachine:
    """Main class orchestrating the AI companion"""

    def __init__(self, config_path="config.json"):
        """Initialize the Klyra Machine with configuration"""
        print("Starting Klyra Machine...")

        # Load configuration
        self.config = self.load_config(config_path)

        # Initialize components (we'll add these as we go)
        self.camera = None
        self.vision = None
        self.audio_input = None
        self.audio_output = None
        self.conversation = None

        # State
        self.running = False
        self.last_vision_check = 0
        self.current_scene_description = ""

    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            print("Please copy config.example.json to config.json and add your API keys")
            exit(1)

    def start(self):
        """Start the Klyra Machine"""
        print("Klyra Machine is now active!")
        print("I can see you, hear you, and talk with you.")
        print("Press Ctrl+C to stop.")

        self.running = True

        try:
            # Main loop
            while self.running:
                # Check vision periodically
                self.check_vision()

                # Listen for voice input
                self.listen_and_respond()

                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutting down Klyra Machine...")
            self.stop()

    def check_vision(self):
        """Periodically capture and analyze what the camera sees"""
        current_time = time.time()
        interval = self.config.get("vision_interval_seconds", 5)

        if current_time - self.last_vision_check >= interval:
            print("Looking around...")
            # TODO: Capture image and analyze with Vision API
            self.last_vision_check = current_time

    def listen_and_respond(self):
        """Listen for voice input and generate a response"""
        # TODO: Implement voice listening and response
        pass

    def stop(self):
        """Clean shutdown of all components"""
        self.running = False
        print("Goodbye!")


def main():
    """Main entry point"""
    machine = KlyraMachine()
    machine.start()


if __name__ == "__main__":
    main()
