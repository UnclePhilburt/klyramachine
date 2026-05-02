#!/bin/bash
# Open the Klyra launcher in a Chrome --app= window. Assumes the
# klyra-webui.service is already serving on localhost:8080. Used as the
# XDG autostart entry on graphical sessions.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLIENT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Wait briefly for the server to come up
for i in {1..40}; do
    if curl -fsS -o /dev/null http://localhost:8080/api/config 2>/dev/null; then
        break
    fi
    sleep 0.25
done

CHROME=$(command -v google-chrome-stable \
    || command -v google-chrome \
    || command -v brave-browser-stable \
    || command -v brave-browser \
    || command -v chromium-browser \
    || command -v chromium \
    || true)

if [ -z "$CHROME" ]; then
    xdg-open http://localhost:8080
    exit 0
fi

if [ "${KIOSK:-}" = "1" ]; then
    WIN_FLAGS="--kiosk"
else
    WIN_FLAGS="--window-size=420,860"
fi

exec "$CHROME" \
    --app=http://localhost:8080 \
    --user-data-dir="$CLIENT_DIR/chrome_data" \
    --no-first-run \
    --no-default-browser-check \
    $WIN_FLAGS
