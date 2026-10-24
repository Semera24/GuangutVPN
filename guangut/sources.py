"""Multi-Source Free VPN Harvester — VPNBook Live Scraper, FreeOpenVPN, and Cloudflare WARP Profiles."""

from __future__ import annotations
import base64
import io
import os
import re
import urllib.request
import zipfile
from typing import List

from guangut.patcher import extract_proto_and_remote

VPNBOOK_URL = "https://www.vpnbook.com/freevpn"
VPNBOOK_CREDS_FILE = "/tmp/guangutvpn-vpnbook-auth.txt"


def _http_get_sources(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GuangutVPN/1.0.0 (Linux)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_vpnbook_live_credentials() -> tuple[str, str]:
    """Scrape current dynamic password from vpnbook.com/freevpn."""
    try:
        html = _http_get_sources(VPNBOOK_URL, timeout=8).decode("utf-8", "replace")
        m_user = re.search(r"Username:\s*<strong>\s*(\w+)\s*</strong>", html, re.I)
        m_pass = re.search(r"Password:\s*<strong>\s*([\w\d]+)\s*</strong>", html, re.I)
        user = m_user.group(1) if m_user else "vpnbook"
        passwd = m_pass.group(1) if m_pass else "vpnbook"
        with open(VPNBOOK_CREDS_FILE, "w", encoding="utf-8") as f:
            f.write(f"{user}\n{passwd}\n")
        return user, passwd
    except Exception:
        return "vpnbook", "vpnbook"


def download_vpnbook_us_profiles() -> List[dict]:
    """Download fresh OpenVPN profile bundles for US servers from VPNBook."""
    target_urls = [
        "https://www.vpnbook.com/free-openvpn-account/VPNBook.com-OpenVPN-US1.zip",
        "https://www.vpnbook.com/free-openvpn-account/VPNBook.com-OpenVPN-US2.zip",
    ]
    out_servers: List[dict] = []
    user, passwd = fetch_vpnbook_live_credentials()

    for url in target_urls:
        try:
            raw_zip = _http_get_sources(url, timeout=10)
            with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
                for fname in z.namelist():
                    if fname.endswith(".ovpn"):
                        content = z.read(fname).decode("utf-8", "replace")
                        proto, host, port = extract_proto_and_remote(content)
                        if not host:
                            continue
                        name = os.path.splitext(fname)[0]
                        out_servers.append({
                            "host": f"vpnbook:{name}",
                            "ip": host,
                            "score": 600000,
                            "ping": 20,
                            "speed": 100_000_000,
                            "country": "United States",
                            "cc": "US",
                            "sessions": 1,
                            "uptime": 99999,
                            "log": "vpnbook",
                            "operator": "VPNBook US High-Speed",
                            "proto": proto,
                            "port": port,
                            "cfg": content,
                            "engine": "openvpn",
                            "city": "Ashburn / Washington DC",
                            "region": "Virginia",
                            "state_code": "VA",
                            "us_region": "east",
                            "isp": "VPNBook Cloud",
                            "lat": 39.0438,
                            "lon": -77.4874,
                            "live_ms": None,
                        })
        except Exception:
            continue

    return out_servers
