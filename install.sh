#!/usr/bin/env bash
set -uo pipefail

echo "=================================================================="
echo "  GuangutVPN — Debian 13 (Trixie) System Installer"
echo "=================================================================="

if [[ $EUID -ne 0 ]]; then
    echo "🔒 Elevating with sudo to install system packages & symlink..."
    exec sudo bash "$0" "$@"
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔗 [1/3] Linking 'guangut' and 'guangut-vpn' into /usr/local/bin and /usr/bin..."
chmod +x "$PROJECT_DIR/guangut-vpn" "$PROJECT_DIR/guangut/cli.py"
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/local/bin/guangut
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/local/bin/guangut-vpn
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/bin/guangut
ln -sf "$PROJECT_DIR/guangut-vpn" /usr/bin/guangut-vpn
echo "   ✓ Linked /usr/bin/guangut and /usr/local/bin/guangut"

if [[ -d /usr/share/applications ]]; then
    cp -f "$PROJECT_DIR/guangutvpn.desktop" /usr/share/applications/
    chmod +x /usr/share/applications/guangutvpn.desktop
    echo "   ✓ Installed Linux Desktop Application icon (/usr/share/applications/guangutvpn.desktop)"
fi

echo "📦 [2/3] Installing Linux VPN tunnel packages (openvpn, wireguard-tools, openresolv)..."
# Ignore broken third-party repo GPG errors (like packages.microsoft.com) during apt update
apt-get update -y || true
DEBIAN_FRONTEND=noninteractive apt-get install -y openvpn wireguard-tools openresolv

echo "✅ [3/3] Verifying installation..."
if command -v openvpn >/dev/null 2>&1 || [[ -x /usr/sbin/openvpn ]]; then
    echo "   ✓ OpenVPN is installed: $(/usr/sbin/openvpn --version | head -n 1)"
else
    echo "   ⚠ Warning: openvpn binary was not found after apt-get install."
fi

echo ""
echo "=================================================================="
echo "  🎉 GuangutVPN Installation Complete!"
echo "=================================================================="
echo "Run any of these commands now:"
echo "  sudo guangut gui                        # Open Web GUI Dashboard in Browser"
echo "  sudo guangut connect                    # Auto-connect to fastest US server"
echo "  sudo guangut connect --us-region west   # Connect to US-West (CA, CO)"
echo "  sudo guangut connect --us-region central# Connect to US-Central (TX)"
echo "  sudo guangut connect --state CA         # Connect to specific US State"
echo "  sudo guangut connect --country JP       # Connect to another country (JP, KR, GB, DE...)"
echo "  guangut status                          # Check tunnel status & verified public IP"
echo "  sudo guangut disconnect                 # Disconnect VPN"
