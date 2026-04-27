# Klyra Machine - AI Vision Companion

An interactive AI companion with client-server architecture. Like Alexa, but it can see you and hold natural conversations!

- **Server**: Deployed on Render, handles all AI processing (Vision, GPT, TTS)
- **Client**: Lightweight Raspberry Pi with camera/mic/speaker

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Raspberry Pi      │         │   Render Server      │
│   (Client)          │◄───────►│   (AI Processing)    │
├─────────────────────┤         ├──────────────────────┤
│ • Camera capture    │         │ • OpenAI Vision API  │
│ • Mic recording     │         │ • GPT-4 conversation │
│ • Audio playback    │         │ • ElevenLabs TTS     │
│ • Send to server    │         │ • Image analysis     │
└─────────────────────┘         └──────────────────────┘
```

## Quick Start

### 1. Deploy Server to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

1. Fork this repo
2. Create new Web Service on Render
3. Connect your GitHub repo
4. Set build command: `cd server && pip install -r requirements.txt`
5. Set start command: `cd server && python server.py`
6. Add environment variables:
   - `OPENAI_API_KEY`
   - `ELEVENLABS_API_KEY`

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### 2. Test on Windows (Before Raspberry Pi)

```bash
cd client
pip install -r requirements.txt
copy config.example.json config.json
# Server URL is already set to https://klyramachine.onrender.com
python client.py
```

### 3. Deploy to Raspberry Pi

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for Raspberry Pi setup.

## Components

### Server (`/server`)
- FastAPI web server
- Handles Vision API, GPT, and Text-to-Speech
- Processes requests from any client
- Can handle multiple clients simultaneously

### Client (`/client`)
- Runs on Raspberry Pi (or Windows for testing)
- Captures camera and microphone input
- Sends data to server via HTTP
- Plays audio responses

## Features
- Real-time camera vision analysis
- Contextual conversation with memory
- Natural speech responses
- Lightweight client for Raspberry Pi
- Cloud-based AI processing
- Works from anywhere with internet

## API Keys Required

- **OpenAI API**: https://platform.openai.com/api-keys
- **ElevenLabs API**: https://elevenlabs.io/app/settings/api-keys

## Development

```bash
# Run server locally
cd server
pip install -r requirements.txt
cp config.example.json config.json
# Add your API keys to config.json
python server.py

# Run client (separate terminal)
cd client
pip install -r requirements.txt
cp config.example.json config.json
# Edit config.json with server URL (http://localhost:8000)
python client.py
```

## Cost Estimates

Per interaction:
- OpenAI Vision: ~$0.01-0.03
- GPT-4 Chat: ~$0.01-0.03
- ElevenLabs TTS: ~$0.01-0.02

Total: ~$0.03-0.08 per interaction

## License

MIT
