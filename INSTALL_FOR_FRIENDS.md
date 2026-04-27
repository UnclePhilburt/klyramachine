# Easy Install for Klyra Machine

Hey! Setting up Klyra is super easy. Just follow these steps:

## What You Need
- Raspberry Pi (any model with camera/mic support)
- Webcam or Pi Camera
- USB Microphone
- Internet connection

## Installation (One Command!)

Open a terminal on your Raspberry Pi and run:

```bash
curl -sSL https://raw.githubusercontent.com/UnclePhilburt/klyramachine/main/easy_install.sh | bash
```

That's it! The installer will:
1. ✅ Install all dependencies
2. ✅ Download Klyra
3. ✅ Set up auto-start
4. ✅ Configure everything

## After Installation

Start Klyra:
```bash
sudo systemctl start klyra
```

Say **"Hey Buddy"** followed by your question!

## Examples

- "Hey Buddy, what's the weather?"
- "Hey Buddy, tell me a joke"
- "Hey Buddy, what do you see?"

## Troubleshooting

### Check if it's running:
```bash
sudo systemctl status klyra
```

### View logs:
```bash
sudo journalctl -u klyra -f
```

### Restart:
```bash
sudo systemctl restart klyra
```

### Test camera:
```bash
raspistill -o test.jpg
```

### Test microphone:
```bash
arecord -l
```

## Updates

Klyra automatically updates every hour! No manual updates needed.

## Questions?

Contact the person who sent you this!

---

That's it! Enjoy your AI buddy! 🤖
