"""
Test which microphone is being used
"""

import pyaudio

audio = pyaudio.PyAudio()

print("Available audio devices:")
print("="*50)

for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)
    if info['maxInputChannels'] > 0:  # Only show input devices
        print(f"\nDevice {i}: {info['name']}")
        print(f"  Max Input Channels: {info['maxInputChannels']}")
        print(f"  Default Sample Rate: {info['defaultSampleRate']}")

print("\n" + "="*50)
print(f"\nDefault input device: {audio.get_default_input_device_info()['name']}")
print("\nThis is the microphone Klyra is using!")

audio.terminate()
