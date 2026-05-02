#!/bin/bash
# Start the Klyra web UI server and open it in Chrome.
# Use --kiosk to run fullscreen (Esc to exit kiosk).

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLIENT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
PY="$CLIENT_DIR/venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "venv python not found at $PY"
    exit 1
fi

# Start the server in the background
echo "Starting Klyra web server on http://localhost:8080 ..."
"$PY" "$SCRIPT_DIR/server.py" &
SERVER_PID=$!

# Wait briefly for the server to come up
for i in {1..20}; do
    if curl -fsS -o /dev/null http://localhost:8080/api/config 2>/dev/null; then
        break
    fi
    sleep 0.25
done

# Pick a Chrome/Chromium binary
CHROME=$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true)
if [ -z "$CHROME" ]; then
    echo "Chrome not found — open http://localhost:8080 in any browser."
else
    # Phone-shaped window for testing (420x860 ≈ modern Android phone).
    # Pass KIOSK=1 to fullscreen instead.
    if [ "${KIOSK:-}" = "1" ]; then
        WIN_FLAGS="--kiosk"
    else
        WIN_FLAGS="--window-size=420,860"
    fi
    "$CHROME" \
        --app=http://localhost:8080 \
        --user-data-dir="$CLIENT_DIR/chrome_data" \
        --no-first-run \
        --no-default-browser-check \
        $WIN_FLAGS &
fi

# When this script exits, kill the server too
trap "kill $SERVER_PID 2>/dev/null || true" EXIT
wait $SERVER_PID
