# Testing Klyra Machine on Windows

Before deploying to Raspberry Pi, test everything on your Windows PC!

## Prerequisites

- Python 3.8+ installed
- Webcam connected
- Microphone connected
- Speakers/headphones

## Quick Start

### Option 1: Use the Batch File (Easiest)

1. Double-click `test_windows.bat`
2. It will install dependencies and start the client
3. Follow the prompts

### Option 2: Manual Setup

```bash
# Navigate to client folder
cd C:\Users\CodyW\Documents\klyramachine\client

# Install dependencies
pip install -r requirements.txt

# Create config file
copy config.example.json config.json

# Edit config.json with your Render server URL
notepad config.json
```

Set your server URL:
```json
{
  "server_url": "https://your-app.onrender.com",
  "client_id": "klyra_windows_test",
  "camera_index": 0,
  "vision_check_interval": 10,
  "audio_record_duration": 5
}
```

Run the client:
```bash
python client.py
```

## Testing Checklist

### 1. Server Connection
When you start the client, you should see:
```
Initializing Klyra Client...
Client initialized! Connected to server: https://...
Server is online!
```

If not:
- Check your server URL in config.json
- Make sure server is running on Render
- Visit the server URL in your browser - you should see: `{"status":"online",...}`

### 2. Camera Test
When you send a message that requires vision:
```
You: What do you see?
Sending image to server...
```

Check:
- Webcam light turns on
- No "Camera not available" errors

If camera fails:
- Check webcam is plugged in
- Try `"camera_index": 1` in config.json
- Close other apps using the camera

### 3. Conversation Test
Type messages and check responses:
```
You: Hello!
Waiting for Klyra...
Klyra: Hi! I can see you sitting at your desk...
```

### 4. Audio Playback Test
After Klyra responds, you should:
- Hear audio through your speakers
- See "Finished speaking" message

If no audio:
- Check speaker volume
- Check Windows audio output device
- Look for error messages

## Common Issues

### "Cannot connect to server"
- Server not deployed or crashed
- Wrong URL in config.json
- Check Render dashboard for server status

### "Camera not available"
- Webcam in use by another app
- Wrong camera_index
- Try: `python -c "import cv2; print('Cameras:', [i for i in range(5) if cv2.VideoCapture(i).read()[0]])"`

### "Module not found" errors
- Run: `pip install -r requirements.txt` again
- Make sure you're in the `client` folder

### Audio playback errors
- Install: `pip install pygame --upgrade`
- Check Windows audio is working

## Example Test Session

```
You: Hello, can you see me?
Klyra: Yes! I can see you sitting at your desk with a laptop. How can I help you today?

You: What's on my desk?
Klyra: I can see a laptop, a coffee mug, and what looks like some papers or notebooks.

You: Thanks!
Klyra: You're welcome! Let me know if you need anything else.
```

## Next Steps

Once everything works on Windows:
1. Deploy the same client script to Raspberry Pi
2. Update the config on Pi with the same server URL
3. Connect camera, mic, and speaker to Pi
4. Run the same `python client.py` command

The client code works identically on both Windows and Raspberry Pi!

## Performance Notes

- First request may be slow (30-60s) if using Render free tier
- Each interaction costs ~$0.03-0.08 in API fees
- Vision analysis takes 2-3 seconds
- Speech generation takes 1-2 seconds
