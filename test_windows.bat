@echo off
echo ========================================
echo Klyra Machine - Windows Test Client
echo ========================================
echo.

cd client

REM Check if config.json exists
if not exist config.json (
    echo Creating config.json from example...
    copy config.example.json config.json
    echo.
    echo IMPORTANT: Edit config.json and set your server URL!
    echo Example: "server_url": "https://klyramachine-server.onrender.com"
    echo.
    pause
    notepad config.json
)

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Klyra client...
echo.
python client.py

pause
