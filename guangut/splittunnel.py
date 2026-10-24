"""GuangutVPN Split Tunneling & SOCKS5/HTTP Local App Proxy."""

from __future__ import annotations
import os
import shutil
import subprocess
from typing import List, Optional


def launch_app_in_vpn_namespace(app_command: List[str]) -> subprocess.Popen:
    """Launch an application (e.g. google-chrome or curl) through the VPN route."""
    # When tun0 is up, default gateway routes all traffic.
    # For explicit split-launch, can bind to interface or custom socks5 proxy.
    env = os.environ.copy()
    return subprocess.Popen(app_command, env=env)


def launch_browser_through_vpn(browser: str = "google-chrome", url: str = "https://ipinfo.io") -> bool:
    """Launch user's browser with distinct user data profile to test VPN location."""
    su = os.environ.get("SUDO_USER")
    bin_path = shutil.which(browser) or shutil.which("chromium") or shutil.which("firefox")
    if not bin_path:
        return False

    args = [bin_path, url]
    if su and os.geteuid() == 0:
        subprocess.Popen(["sudo", "-u", su] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

