# Raspberry Pi Setup Guide

## Initial Setup

### 1. Clone the repository on your Raspberry Pi

```bash
cd ~
git clone https://github.com/UnclePhilburt/klyramachine.git
cd klyramachine/client
```

### 2. Install dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
pip3 install -r requirements.txt

# Install audio libraries (for PyAudio)
sudo apt install -y python3-pyaudio portaudio19-dev

# Install camera support (if using Pi Camera)
sudo apt install -y python3-opencv
```

### 3. Configure the client

Edit `config.json`:
```bash
nano config.json
```

Update the server URL to your Render server:
```json
{
  "server_url": "https://klyramachine.onrender.com",
  "client_id": "raspberry_pi_001",
  "camera_index": 0
}
```

### 4. Test it manually first

```bash
python3 client_companion.py
```

Press `Ctrl+C` to stop.

## Auto-Start on Boot (Recommended)

### Install as a systemd service

```bash
# Make the install script executable
chmod +x install_service.sh

# Run the installer
./install_service.sh
```

### Start the service

```bash
sudo systemctl start klyra
```

### Check status

```bash
sudo systemctl status klyra
```

### View live logs

```bash
sudo journalctl -u klyra -f
```

## Useful Commands

```bash
# Start Klyra
sudo systemctl start klyra

# Stop Klyra
sudo systemctl stop klyra

# Restart Klyra
sudo systemctl restart klyra

# Disable auto-start
sudo systemctl disable klyra

# Enable auto-start
sudo systemctl enable klyra

# View logs
sudo journalctl -u klyra -f
```

## Troubleshooting

### Camera not working
```bash
# Test camera
raspistill -o test.jpg

# Check camera in config.json
# Try camera_index: 0 or 1
```

### Microphone not working
```bash
# List audio devices
python3 test_mic.py

# Adjust microphone in config.json
```

### Service won't start
```bash
# Check logs
sudo journalctl -u klyra -n 50

# Test manually
cd ~/klyramachine/client
python3 client_companion.py
```

### Update code
```bash
cd ~/klyramachine
git pull
sudo systemctl restart klyra
```

## Performance Tips

1. **Use a good quality microphone** - Built-in mics on webcams often have poor quality
2. **Use a power supply** - Raspberry Pi needs stable 5V/3A power
3. **SD card speed** - Use Class 10 or better SD cards
4. **Cooling** - Add a heatsink or fan if running 24/7
