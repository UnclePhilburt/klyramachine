# Klyra Machine Setup Guide

## Overview

The Klyra Machine has two parts:
1. **Server** - Runs on your powerful computer (handles AI)
2. **Client** - Runs on Raspberry Pi (captures camera/mic, plays audio)

## Part 1: Server Setup (Your Render Server)

### 1. Get API Keys

You'll need:
- **OpenAI API Key**: https://platform.openai.com/api-keys
- **ElevenLabs API Key**: https://elevenlabs.io/app/settings/api-keys

### 2. Install Python

Make sure you have Python 3.8 or newer installed.

### 3. Set Up Server

```bash
cd C:\Users\CodyW\Documents\klyramachine\server

# Install dependencies
pip install -r requirements.txt

# Create config file
copy config.example.json config.json
```

### 4. Edit config.json

Open `config.json` and add your API keys:

```json
{
  "openai_api_key": "sk-your-actual-key-here",
  "elevenlabs_api_key": "your-elevenlabs-key-here",
  "server_host": "0.0.0.0",
  "server_port": 8000,
  "elevenlabs_voice": "Adam",
  "gpt_model": "gpt-4o",
  "system_prompt": "You are Klyra..."
}
```

### 5. Run Server

```bash
python server.py
```

You should see:
```
Starting Klyra Machine Server...
Server will run on 0.0.0.0:8000
```

The server is now running! Keep this terminal open.

### 6. Find Your Server IP Address

On Windows, open Command Prompt and type:
```bash
ipconfig
```

Look for "IPv4 Address" - it will look like `192.168.1.100` or similar.

## Part 2: Raspberry Pi Client Setup

### 1. Prepare Raspberry Pi

You need:
- Raspberry Pi (any model with USB ports)
- Camera (USB webcam or Pi Camera Module)
- USB Microphone
- Speaker (USB or 3.5mm jack)
- Power supply
- SD card with Raspberry Pi OS installed

### 2. Install Dependencies on Pi

```bash
cd ~/
git clone <your-repo-url>  # or copy files manually
cd klyramachine/client

# Install Python dependencies
pip install -r requirements.txt

# For audio to work on Raspberry Pi, you may need:
sudo apt-get install python3-pyaudio portaudio19-dev
sudo apt-get install python3-pygame
```

### 3. Configure Client

```bash
cp config.example.json config.json
nano config.json
```

Edit the file:
```json
{
  "server_url": "http://192.168.1.100:8000",  # Use your server IP here!
  "client_id": "klyra_client_001",
  "camera_index": 0,
  "vision_check_interval": 10,
  "audio_record_duration": 5
}
```

### 4. Test Camera and Microphone

Test camera:
```bash
python3 -c "import cv2; cam = cv2.VideoCapture(0); ret, frame = cam.read(); print('Camera works!' if ret else 'Camera failed'); cam.release()"
```

Test mic (record 3 seconds):
```bash
arecord -d 3 test.wav
aplay test.wav
```

### 5. Run Client

```bash
python3 client.py
```

You should see:
```
Initializing Klyra Client...
Client initialized! Connected to server: http://192.168.1.100:8000
Server is online!
```

## Using Klyra Machine

### Interactive Text Mode

Just type your messages:
```
You: What do you see?
Klyra: I can see you sitting at a desk with a laptop...
```

### Commands

- Type anything to talk to Klyra
- Type `quit` to exit

## API Endpoints

Your server provides these endpoints:

- `GET /` - Health check
- `POST /api/analyze-image` - Analyze a single image
- `POST /api/conversation` - Chat without vision
- `POST /api/text-to-speech` - Convert text to speech
- `POST /api/process-interaction` - Full interaction (recommended)

## Troubleshooting

### "Cannot connect to server"
- Make sure server is running
- Check the IP address in client config.json
- Make sure both devices are on same network
- Try pinging: `ping 192.168.1.100`

### "Camera not available"
- Check camera is plugged in
- Try `camera_index: 1` or `2` in config
- Run: `ls /dev/video*` to see available cameras

### "Error recording audio"
- Check microphone is plugged in
- Install: `sudo apt-get install portaudio19-dev`
- Check volume: `alsamixer`

### "API Error"
- Check your API keys in server/config.json
- Make sure you have credits in OpenAI and ElevenLabs accounts
- Check server terminal for error messages

## Cost Estimates

Approximate API costs per interaction:
- Vision API: $0.01 - $0.03 per image
- GPT-4: $0.01 - $0.03 per conversation turn
- ElevenLabs: $0.01 - $0.02 per speech response

Total: ~$0.03 - $0.08 per complete interaction

## Next Steps

- Add wake word detection ("Hey Klyra")
- Implement continuous voice mode
- Add memory/context persistence
- Multiple client support
- Web dashboard for monitoring

## Support

Check the main README.md for more information!
