#!/usr/bin/env bash
# GuangutVPN Desktop GUI Wrapper for Xfce / Freedesktop
# Runs with standard elevation prompt if root is needed, launches the local Web GUI, and opens browser.

set -euo pipefail

APP_DIR="/home/yona/Projects/GuangutVPN"
URL="http://127.0.0.1:8765"

# If already running as root or user, ensure we launch guangut gui cleanly
if [[ $EUID -eq 0 ]]; then
    exec python3 "$APP_DIR/guangut-vpn" gui
fi

# Not root: Launch via terminal with standard sudo prompt (preserving user environment) or pkexec
if command -v pkexec >/dev/null 2>&1; then
    exec pkexec --user root env DISPLAY="$DISPLAY" XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" python3 "$APP_DIR/guangut-vpn" gui
elif command -v xfce4-terminal >/dev/null 2>&1; then
    exec xfce4-terminal --title="GuangutVPN Control Center" -e "sudo python3 $APP_DIR/guangut-vpn gui"
else
    # Fallback: run user-space GUI server (user can control tunnel or it prompts on connect)
    exec python3 "$APP_DIR/guangut-vpn" gui
fi
