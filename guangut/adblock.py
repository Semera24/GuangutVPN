"""GuangutShield — Zero-Latency DNS Ad, Tracker & Malware Blocker (Like Proton NetShield / Nord Threat Protection)."""

from __future__ import annotations
import os
import re
import shutil
import subprocess
import urllib.request
from typing import Set

BLOCKLIST_CACHE = "/var/tmp/guangut_adblock_hosts"
NFT_AD_SET = "guangut_blocked_dns"

# Curated list of popular high-impact ad/malware domain sources (StevenBlack minimal starter)
DEFAULT_AD_DOMAINS = [
    # Google Ads & Analytics
    "googleads.g.doubleclick.net",
    "pagead2.googlesyndication.com",
    "adservice.google.com",
    "analytics.google.com",
    "clickserve.dartsearch.net",
    # Telemetry & trackers
    "telemetry.microsoft.com",
    "v10.events.data.microsoft.com",
    "graph.facebook.com",
    "pixel.facebook.com",
    "an.facebook.com",
    # Ad networks & popups
    "ads.pubmatic.com",
    "c.amazon-adsystem.com",
    "aax.amazon-adsystem.com",
    "static.ads-twitter.com",
    "ads-api.twitter.com",
    "ads.tiktok.com",
    "analytics.tiktok.com",
    "ad.doubleclick.net",
    "securepubads.g.doubleclick.net",
    "adservice.google.com",
    "ib.adnxs.com",
    "ad.yieldlab.net",
    "track.adform.net",
    "ad.adriver.ru",
]


def generate_adblock_hosts(output_path: str = "/tmp/guangut_adblock_hosts") -> str:
    """Generate local /etc/hosts redirect block rules mapping known ad/malware domains to 0.0.0.0."""
    lines = [
        "# GuangutShield — DNS Ad & Tracker Protection (Generated)",
        "# Blocks advertisements, pop-ups, and trackers at 0 ms latency",
        "",
    ]
    for domain in sorted(DEFAULT_AD_DOMAINS):
        lines.append(f"0.0.0.0 {domain}")
        lines.append(f":: {domain}")

    content = "\n".join(lines) + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def apply_adblock_protection() -> tuple[bool, str]:
    """Apply ad-blocking DNS hosts rules without disturbing real hostname resolution."""
    hosts_tmp = generate_adblock_hosts()
    # Check if hosts already contains GuangutShield
    try:
        with open("/etc/hosts", "r", encoding="utf-8") as f:
            current = f.read()
        if "GuangutShield" in current:
            return True, "GuangutShield Ad & Tracker Blocker is already active"

        # Append block entries cleanly with sudo
        cmd = ["sudo", "bash", "-c", f"cat {hosts_tmp} >> /etc/hosts"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True, f"GuangutShield Active: Blocked {len(DEFAULT_AD_DOMAINS)} tracker/ad networks"
    except Exception as e:
        return False, str(e)
    return False, "Failed to update hosts"


def remove_adblock_protection() -> bool:
    """Cleanly strip GuangutShield entries from /etc/hosts."""
    try:
        cmd = ["sudo", "sed", "-i", "/GuangutShield/,+55d", "/etc/hosts"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

