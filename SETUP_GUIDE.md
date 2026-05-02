# Klyra Machine Setup Guide

## Overview

The Klyra Machine has two parts:
1. **Server** - Runs on Render (handles AI)
2. **Client** - Runs on Ubuntu (captures camera/mic, plays audio)

## Part 1: Server Setup (Render)

### 1. Get API Keys

You'll need:
- **OpenAI API Key**: https://platform.openai.com/api-keys
- **ElevenLabs API Key**: https://elevenlabs.io/app/settings/api-keys

### 2. Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full Render walkthrough. The
short version:

1. Fork this repo on GitHub.
2. Create a new Web Service on Render and connect the fork.
3. Set environment variables `OPENAI_API_KEY` and `ELEVENLABS_API_KEY`.
4. Render builds with `cd server && pip install -r requirements.txt` and
   starts with `cd server && python server.py`.

### 3. Run the server locally (optional, for development)

```bash
cd server
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json with your API keys
python server.py
```

You should see:
```
Starting Klyra Machine Server...
Server will run on 0.0.0.0:8000
```

## Part 2: Ubuntu Client Setup

### 1. Hardware

- Ubuntu host (Desktop or Server, x86 or ARM)
- USB webcam
- USB microphone
- Speakers (USB or 3.5mm)

### 2. One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/UnclePhilburt/klyramachine/main/easy_install.sh | bash
```

This handles apt deps, uv-managed Python 3.12, the venv, ALSA config (only
on bare-ALSA systems), the Vosk wake-word model, the Piper TTS voice, and
the systemd service with auto-update.

### 3. Manual install

```bash
git clone https://github.com/UnclePhilburt/klyramachine.git
cd klyramachine/client

# System deps
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev libasound2-dev \
    libsdl2-2.0-0 libsdl2-mixer-2.0-0 build-essential

# Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pygame webrtcvad
```

### 4. Configure

```bash
cp config.example.json config.json
nano config.json
```

```json
{
  "server_url": "https://klyramachine.onrender.com",
  "client_id": "klyra_ubuntu_001",
  "camera_index": 0,
  "wake_word": "hey buddy",
  "enable_camera": true
}
```

For local server development, use `http://localhost:8000` instead.

### 5. Test camera and microphone

```bash
# Camera
python3 -c "import cv2; c=cv2.VideoCapture(0); ok,_=c.read(); print('Camera works!' if ok else 'Camera failed'); c.release()"

# Mic (record 3 seconds)
arecord -d 3 test.wav
aplay test.wav
```

### 6. Run

```bash
python3 client_vosk.py        # offline wake word (default if model present)
python3 client_text.py        # text-only fallback
python3 client_companion.py   # spontaneous-observation mode
```

## Using Klyra Machine

Say **"Hey Buddy"** to wake Klyra, then talk. Or in text mode, just type.

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
- Check the URL in client `config.json`
- For local dev: `curl http://localhost:8000/` should return `{"status":"online",...}`

### "Camera not available"
- Check camera is plugged in
- Try `camera_index: 1` or `2` in config
- Run: `ls /dev/video*` to see available cameras

### "Error recording audio"
- Check microphone is plugged in
- Run `python3 client/debug_audio.py` to enumerate audio devices
- Check volume: `alsamixer`

### "API Error"
- Check your API keys in `server/config.json` (or Render env vars)
- Make sure you have credits in OpenAI and ElevenLabs accounts
- Check server logs

## Cost Estimates

Approximate API costs per interaction:
- Vision API: $0.01 - $0.03 per image
- GPT-4: $0.01 - $0.03 per conversation turn
- ElevenLabs: $0.01 - $0.02 per speech response

Total: ~$0.03 - $0.08 per complete interaction

## Support

Check the main README.md for more information!
