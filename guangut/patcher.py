"""Reverse-Engineered OpenVPN 2.6+ & WireGuard Configuration Patcher for Debian 13."""

from __future__ import annotations
import os
import re
import time
from typing import Optional, Tuple

PROTO_REGEX = re.compile(r"^\s*proto\s+(\S+)", re.M | re.I)
REMOTE_REGEX = re.compile(r"^\s*remote\s+(\S+)\s+(\d+)", re.M | re.I)
CIPHER_REGEX = re.compile(r"^\s*cipher\s+(\S+)", re.M | re.I)

# Directives in legacy VPN Gate / Windows OpenVPN profiles that cause OpenVPN 2.6+ on Linux to fail or warn
STRIP_DIRECTIVE_PREFIXES = (
    "win-sys",
    "route-method",
    "route-delay",
    "dhcp-renew",
    "dhcp-release",
    "show-net-up",
    "ip-win32",
    "register-dns",
    "tun-ipv6",
    "ncp-ciphers",
    "ncp-disable",
    " explicit-exit-notify",
)

DNS_HELPER = "/etc/openvpn/update-systemd-resolved"
AUTH_FILE = "/tmp/guangutvpn-auth.txt"


def ensure_default_auth_file(username: str = "vpn", password: str = "vpn") -> str:
    """Create /tmp/guangutvpn-auth.txt with standard VPN Gate credentials (vpn / vpn)."""
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            f.write(f"{username}\n{password}\n")
        os.chmod(AUTH_FILE, 0o600)
    except OSError:
        pass
    return AUTH_FILE


def extract_proto_and_remote(raw_ovpn: str) -> Tuple[str, str, int]:
    """Parse protocol ('udp' or 'tcp'), remote host/IP, and port from raw .ovpn text."""
    proto = "udp"
    host = ""
    port = 1194

    m_proto = PROTO_REGEX.search(raw_ovpn)
    if m_proto:
        raw_p = m_proto.group(1).lower()
        proto = "tcp" if "tcp" in raw_p else "udp"

    m_rem = REMOTE_REGEX.search(raw_ovpn)
    if m_rem:
        host = m_rem.group(1).strip()
        try:
            port = int(m_rem.group(2).strip())
        except ValueError:
            port = 1194

    return proto, host, port


def extract_legacy_cipher(raw_ovpn: str) -> str:
    """Detect the legacy cipher declared by the server profile (default AES-128-CBC)."""
    m = CIPHER_REGEX.search(raw_ovpn)
    if m:
        return m.group(1).strip().upper()
    return "AES-128-CBC"


def patch_ovpn_config(
    server: dict,
    keepalive: Tuple[int, int] = (10, 45),
    custom_dns: Tuple[str, str] = ("1.1.1.1", "8.8.8.8"),
    connect_timeout: int = 10,
) -> str:
    """Reverse-engineer and patch a legacy .ovpn profile so it works reliably on Debian 13 (OpenVPN 2.6+).

    Key Fixes:
    1. Strips Windows-only and deprecated OpenVPN 2.4/2.5 directives.
    2. Reads the legacy `--cipher` (e.g. AES-128-CBC or AES-256-CBC) and injects it into
       `--data-ciphers` and `--data-ciphers-fallback` so OpenVPN 2.6+ negotiates cleanly.
    3. Adds `--tls-version-min 1.0` and `--tls-cipher DEFAULT:@SECLEVEL=0` compatibility for
       academic/volunteer SoftEther relays with older OpenSSL certificates.
    4. Enforces full-tunnel routing (`redirect-gateway def1`), IPv6 leak blocking (`block-ipv6`),
       and fast-fail handshake timeouts so dead relays roll over quickly.
    """
    raw_cfg = server.get("cfg", "")
    legacy_cipher = extract_legacy_cipher(raw_cfg)

    cleaned_lines = []
    for line in raw_cfg.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith(STRIP_DIRECTIVE_PREFIXES):
            continue
        # Remove conflicting connect-retry, ping, or bare auth-user-pass lines so ours take precedence
        if low.startswith(("connect-retry ", "connect-retry-max ", "connect-timeout ", "ping ", "ping-exit ", "ping-restart ", "auth-user-pass", "#auth-user-pass")):
            continue
        cleaned_lines.append(line)

    ciphers_list = [
        "AES-256-GCM",
        "AES-128-GCM",
        "CHACHA20-POLY1305",
        "AES-256-CBC",
        "AES-128-CBC",
    ]
    if legacy_cipher and legacy_cipher not in ciphers_list:
        ciphers_list.append(legacy_cipher)
    data_ciphers_str = ":".join(ciphers_list)

    ping_int, ping_exit = keepalive
    proto = server.get("proto", "udp")

    if "vpnbook" in server.get("host", "").lower():
        from guangut.sources import VPNBOOK_CREDS_FILE, fetch_vpnbook_live_credentials
        fetch_vpnbook_live_credentials()
        auth_file_path = VPNBOOK_CREDS_FILE
    else:
        auth_file_path = ensure_default_auth_file()

    patch_block = [
        "",
        "# ====================================================================",
        f"# GuangutVPN OpenVPN 2.6+ Reverse-Engineered Patch (Debian 13 Trixie)",
        f"# Server: {server.get('host', '?')} | IP: {server.get('ip', '?')}:{server.get('port', '?')} ({proto.upper()})",
        f"# Location: {server.get('country', '?')} / {server.get('state_code') or server.get('region') or '?'} / {server.get('city') or '?'}",
        f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "# ====================================================================",
        "client",
        "nobind",
        "persist-key",
        "persist-tun",
        "script-security 2",
        f"auth-user-pass {auth_file_path}",
        "auth-nocache",
        f"data-ciphers {data_ciphers_str}",
        f"data-ciphers-fallback {legacy_cipher}",
        "tls-version-min 1.0",
        "tls-cipher DEFAULT:@SECLEVEL=0",
        f"connect-timeout {connect_timeout}",
        "connect-retry 2 4",
        "connect-retry-max 2",
        "resolv-retry 5",
        'pull-filter ignore "bypass-dhcp"',
        'pull-filter ignore "route-ipv6"',
        'pull-filter ignore "ifconfig-ipv6"',
        "redirect-gateway def1",
        "block-ipv6",
    ]

    for dns_ip in custom_dns:
        patch_block.append(f"dhcp-option DNS {dns_ip}")

    if ping_int > 0:
        patch_block.append(f"ping {ping_int}")
    if ping_exit > 0:
        patch_block.append(f"ping-exit {ping_exit}")

    if os.path.exists(DNS_HELPER):
        patch_block.extend([
            f"up {DNS_HELPER}",
            f"down {DNS_HELPER}",
            "down-pre",
        ])

    return "\n".join(cleaned_lines) + "\n" + "\n".join(patch_block) + "\n"

