"""GuangutVPN Native WireGuard (wg0) Controller — Sub-Second Handshakes & 1Gbps+ Speed."""

from __future__ import annotations
import os
import shutil
import subprocess
import time
from typing import Optional, Tuple

from guangut.security import configure_tunnel_dns, disable_killswitch, enable_killswitch

WG_CONF_DIR = "/etc/wireguard"
WG_IFACE = "wg0"
WG_ACTIVE_CONF = "/etc/wireguard/wg0.conf"


def is_wireguard_available() -> bool:
    return bool(shutil.which("wg-quick") or os.path.exists("/usr/bin/wg-quick"))


def is_wireguard_connected() -> bool:
    res = subprocess.run(["ip", "-o", "link", "show", WG_IFACE], capture_output=True, text=True)
    return res.returncode == 0 and "UP" in res.stdout


def connect_wireguard(config_content: str, server_endpoint_ip: str, dns_servers: tuple[str, str] = ("1.1.1.1", "8.8.8.8")) -> Tuple[bool, str]:
    """Bring up a WireGuard interface (wg0) using wg-quick with automated routing and DNS."""
    if not is_wireguard_available():
        return False, "wireguard-tools / wg-quick not installed"

    if is_wireguard_connected():
        disconnect_wireguard()

    try:
        # Save config securely
        tmp_conf = "/tmp/wg0.conf"
        with open(tmp_conf, "w", encoding="utf-8") as f:
            f.write(config_content)
        os.chmod(tmp_conf, 0o600)

        # Move to /etc/wireguard/wg0.conf
        subprocess.run(["sudo", "mkdir", "-p", WG_CONF_DIR], check=True)
        subprocess.run(["sudo", "cp", "-f", tmp_conf, WG_ACTIVE_CONF], check=True)
        subprocess.run(["sudo", "chmod", "600", WG_ACTIVE_CONF], check=True)

        # Bring up wg0
        proc = subprocess.run(["sudo", "wg-quick", "up", WG_IFACE], capture_output=True, text=True)
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            return False, f"wg-quick up failed: {err}"

        time.sleep(1.0)
        configure_tunnel_dns(WG_IFACE, dns_servers)
        return True, "WireGuard wg0 kernel tunnel established successfully!"
    except Exception as e:
        return False, str(e)


def disconnect_wireguard() -> Tuple[bool, str]:
    """Gracefully bring down WireGuard interface wg0."""
    if not is_wireguard_available():
        return False, "wireguard-tools not found"

    proc = subprocess.run(["sudo", "wg-quick", "down", WG_IFACE], capture_output=True, text=True)
    subprocess.run(["sudo", "rm", "-f", WG_ACTIVE_CONF], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if proc.returncode == 0:
        return True, "WireGuard wg0 disconnected."
    return False, "WireGuard interface was not active."

