#!/usr/bin/env bash
set -uo pipefail

echo "=================================================================="
echo "  GuangutVPN — Debian/Xfce System Installer & Launcher Setup"
echo "=================================================================="

PROJECT_DIR="/home/yona/Projects/GuangutVPN"

# Ensure we are root for system installation
if [[ $EUID -ne 0 ]]; then
    echo "🔒 Elevating with sudo to complete system installation (/usr/bin, /usr/share/applications)..."
    exec sudo bash "$0" "$@"
fi

# Ensure project permissions & executables
chmod +x "$PROJECT_DIR/guangut-vpn" "$PROJECT_DIR/guangut/cli.py" "$PROJECT_DIR/guangutvpn-gui-wrapper.sh"

echo "🔗 [1/4] Linking 'guangut' and 'guangut-vpn' into /usr/local/bin and /usr/bin..."
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/local/bin/guangut
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/local/bin/guangut-vpn
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/bin/guangut
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/bin/guangut-vpn
echo "   ✓ Linked /usr/bin/guangut and /usr/local/bin/guangut"

echo "🎨 [2/4] Installing application icons..."
mkdir -p /usr/share/pixmaps
mkdir -p /usr/share/icons/hicolor/scalable/apps
cp -f "$PROJECT_DIR/guangutvpn.svg" /usr/share/pixmaps/guangutvpn.svg
cp -f "$PROJECT_DIR/guangutvpn.svg" /usr/share/icons/hicolor/scalable/apps/guangutvpn.svg
echo "   ✓ Installed icon to /usr/share/pixmaps/guangutvpn.svg"

echo "🖥️ [3/4] Installing system application launcher for Xfce / Freedesktop..."
mkdir -p /usr/share/applications
cp -f "$PROJECT_DIR/guangutvpn.desktop" /usr/share/applications/guangutvpn.desktop
chmod 644 /usr/share/applications/guangutvpn.desktop

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
echo "   ✓ Installed system launcher: /usr/share/applications/guangutvpn.desktop"

echo "📦 [4/4] Ensuring tunnel packages are installed..."
apt-get update -y || true
DEBIAN_FRONTEND=noninteractive apt-get install -y openvpn wireguard-tools openresolv >/dev/null 2>&1 || true

echo ""
echo "=================================================================="
echo "  🎉 GuangutVPN Installation & Desktop Launcher Ready!"
echo "=================================================================="
echo "You can now launch 'GuangutVPN' directly from:"
echo "  1. Xfce Application Menu -> Internet / Network -> GuangutVPN"
echo "  2. Application Finder / Search -> type 'GuangutVPN'"
echo "  3. Terminal command -> 'sudo guangut gui' or 'guangut'"
