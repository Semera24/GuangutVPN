#!/usr/bin/env bash
# GuangutVPN Background Daemon & Browser Launcher
# Runs the Web GUI in the background (non-blocking) and immediately opens the browser.

set -euo pipefail

APP_DIR="/home/yona/Projects/GuangutVPN"
URL="http://127.0.0.1:8765"
PID_FILE="/tmp/guangutvpn-gui.pid"

# Check if GUI server is already listening
if curl -sI "$URL" >/dev/null 2>&1; then
    # Server is already running! Just open browser
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 &
    fi
    exit 0
fi

# Not running yet: Start GUI server in background
nohup python3 "$APP_DIR/guangut-vpn" gui --no-browser > /tmp/guangutvpn-gui.log 2>&1 &
echo $! > "$PID_FILE"

# Wait up to 3 seconds for port 8765 to become active
for i in {1..15}; do
    if curl -sI "$URL" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

# Open the browser cleanly in the desktop user's session
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 &
elif command -v google-chrome >/dev/null 2>&1; then
    google-chrome "$URL" >/dev/null 2>&1 &
elif command -v firefox >/dev/null 2>&1; then
    firefox "$URL" >/dev/null 2>&1 &
fi

exit 0
