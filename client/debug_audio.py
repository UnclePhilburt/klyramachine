#!/usr/bin/env python3
"""
Audio debugging script for Klyra
Shows ALL audio device information
"""

import pyaudio
import sys

print("="*60)
print("KLYRA AUDIO DEBUGGER")
print("="*60)
print("")

try:
    p = pyaudio.PyAudio()

    print(f"PyAudio Version: {pyaudio.__version__}")
    print(f"PortAudio Version: {pyaudio.get_portaudio_version()}")
    print(f"PortAudio Version Text: {pyaudio.get_portaudio_version_text()}")
    print("")

    device_count = p.get_device_count()
    print(f"Total Audio Devices Found: {device_count}")
    print("")

    print("="*60)
    print("DEVICE DETAILS")
    print("="*60)

    input_devices = []
    output_devices = []

    for i in range(device_count):
        try:
            info = p.get_device_info_by_index(i)

            print(f"\nDevice #{i}:")
            print(f"  Name: {info['name']}")
            print(f"  Host API: {info['hostApi']}")
            print(f"  Max Input Channels: {info['maxInputChannels']}")
            print(f"  Max Output Channels: {info['maxOutputChannels']}")
            print(f"  Default Sample Rate: {info['defaultSampleRate']}")
            print(f"  Default Low Input Latency: {info['defaultLowInputLatency']}")
            print(f"  Default Low Output Latency: {info['defaultLowOutputLatency']}")

            if info['maxInputChannels'] > 0:
                input_devices.append(i)
                print(f"  *** INPUT DEVICE ***")

                # Test if we can open this device
                print(f"  Testing device {i} for recording...")
                try:
                    test_stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=16000,
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=1024
                    )

                    # Try to read
                    data = test_stream.read(1024, exception_on_overflow=False)
                    test_stream.stop_stream()
                    test_stream.close()

                    print(f"  ✓ Device {i} recording test PASSED")

                except Exception as e:
                    print(f"  ✗ Device {i} recording test FAILED: {e}")

            if info['maxOutputChannels'] > 0:
                output_devices.append(i)
                print(f"  *** OUTPUT DEVICE ***")

        except Exception as e:
            print(f"  Error querying device {i}: {e}")

    print("")
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Input devices: {input_devices}")
    print(f"Output devices: {output_devices}")
    print("")

    # Get default devices
    try:
        default_input = p.get_default_input_device_info()
        print(f"Default input device: #{default_input['index']} - {default_input['name']}")
    except:
        print("No default input device set!")

    try:
        default_output = p.get_default_output_device_info()
        print(f"Default output device: #{default_output['index']} - {default_output['name']}")
    except:
        print("No default output device set!")

    print("")
    print("="*60)

    if not input_devices:
        print("ERROR: NO INPUT DEVICES FOUND!")
        print("")
        print("This means:")
        print("  - No microphone is connected")
        print("  - OR microphone is not recognized by the system")
        print("  - OR audio drivers are not working")
        print("")
        print("Try:")
        print("  1. Run: arecord -l")
        print("  2. Check USB connections")
        print("  3. Check audio settings in raspi-config")

    p.terminate()

except Exception as e:
    print(f"FATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
