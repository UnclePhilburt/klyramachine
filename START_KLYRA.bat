@echo off
REM Klyra Machine - Windows Launcher
REM Double-click to start Klyra

echo ==================================================
echo    KLYRA MACHINE - STARTING...
echo ==================================================
echo.

cd /d "%~dp0\client"

if not exist "client_companion.py" (
    echo ERROR: client_companion.py not found!
    echo Make sure you have the complete klyramachine folder.
    pause
    exit /b 1
)

python client_companion.py

pause
