"""Linux Tunnel Daemon Controller (OpenVPN 2.6+ & WireGuard) with Auto-Failover & Geo Verifier."""

from __future__ import annotations
import json
import os
import shutil
import subprocess
import time
from typing import Optional, Tuple

from guangut.harvester import http_get
from guangut.patcher import patch_ovpn_config
from guangut.security import (
    configure_tunnel_dns,
    disable_killswitch,
    enable_killswitch,
    is_killswitch_active,
    restore_system_dns,
)

PID_FILE = "/run/guangutvpn.pid"
LOG_FILE = "/var/log/guangutvpn.log"
CONF_FILE = "/tmp/guangutvpn-active.ovpn"
META_FILE = "/var/tmp/guangutvpn.meta.json"

OK_MARKER = "Initialization Sequence Completed"
FAIL_MARKERS = (
    "Options error",
    "AUTH_FAILED",
    "Cannot resolve host",
    "Connection refused",
    "Connection timed out",
    "Connection reset by peer",
    "No route to host",
    "Network is unreachable",
    "Error opening configuration file",
    "Failed to establish",
    "TUNSETIFF failed",
    "All connections have been",
    "Exiting due to fatal error",
    "TLS Error: TLS key negotiation failed",
    "TLS handshake failed",
)


def has_root_or_sudo() -> bool:
    if os.geteuid() == 0:
        return True
    try:
        return subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def sudo_exec(argv: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    if os.geteuid() == 0:
        return subprocess.run(argv, capture_output=capture, text=True)
    return subprocess.run(["sudo"] + argv, capture_output=capture, text=True)


def sudo_exec_nonblock(argv: list[str]) -> subprocess.CompletedProcess:
    if os.geteuid() == 0:
        return subprocess.run(argv, capture_output=True, text=True)
    return subprocess.run(["sudo", "-n"] + argv, capture_output=True, text=True)


def check_vpn_binaries() -> Tuple[bool, bool]:
    """Return (has_openvpn, has_wireguard) on the system."""
    ovpn = bool(shutil.which("openvpn") or os.path.exists("/usr/sbin/openvpn") or os.path.exists("/sbin/openvpn"))
    wg = bool(shutil.which("wg-quick") or os.path.exists("/usr/bin/wg-quick"))
    return ovpn, wg


def get_openvpn_bin() -> str:
    for candidate in (shutil.which("openvpn"), "/usr/sbin/openvpn", "/sbin/openvpn", "/usr/bin/openvpn"):
        if candidate and os.path.exists(candidate):
            return candidate
    return "openvpn"


def running_pid() -> Optional[int]:
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace")
        if CONF_FILE in cmdline or "openvpn" in cmdline:
            return pid
    except (OSError, ValueError):
        pass
    # Also check pgrep fallback
    res = subprocess.run(["pgrep", "-f", CONF_FILE], capture_output=True, text=True)
    pids = res.stdout.strip().split()
    if pids:
        try:
            return int(pids[0])
        except ValueError:
            pass
    return None


def get_active_tun_iface() -> Optional[str]:
    """Detect active tun0/wg0 interface and its assigned internal IPv4."""
    res = subprocess.run(["ip", "-o", "-4", "addr", "show"], capture_output=True, text=True)
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            iface = parts[1]
            if iface.startswith(("tun", "tap", "wg")):
                return f"{iface} ({parts[3]})"
    return None


def fetch_public_ip_geo(timeout: int = 6) -> Optional[dict]:
    """Fetch current public exit IP, country, US state/region, city, and ISP via fast HTTPS endpoints."""
    endpoints = [
        "https://ipwho.is/",
        "https://ipinfo.io/json",
    ]
    for url in endpoints:
        try:
            raw = http_get(url, timeout=timeout).decode("utf-8", "replace")
            data = json.loads(raw)
            if "ip" in data and data.get("success") is True:
                conn = data.get("connection") or {}
                return {
                    "ip": data.get("ip", ""),
                    "country": data.get("country", ""),
                    "cc": data.get("country_code", ""),
                    "state_code": data.get("region_code", ""),
                    "region": data.get("region", ""),
                    "city": data.get("city", ""),
                    "isp": conn.get("isp") or conn.get("org") or "",
                }
            if "ip" in data:
                return {
                    "ip": data.get("ip", ""),
                    "country": data.get("country", ""),
                    "cc": data.get("country", ""),
                    "state_code": data.get("region", ""),
                    "region": data.get("region", ""),
                    "city": data.get("city", ""),
                    "isp": data.get("org", ""),
                }
        except Exception:
            continue
    return None


def save_meta(server: dict, exit_info: Optional[dict] = None, killswitch: bool = False) -> None:
    meta = {
        "host": server.get("host"),
        "ip": server.get("ip"),
        "cc": server.get("cc"),
        "country": server.get("country"),
        "state_code": server.get("state_code", ""),
        "us_region": server.get("us_region", ""),
        "region": server.get("region", ""),
        "city": server.get("city", ""),
        "isp": server.get("isp", ""),
        "proto": server.get("proto", "udp"),
        "port": server.get("port", 1194),
        "engine": server.get("engine", "openvpn"),
        "killswitch": killswitch,
        "exit_info": exit_info or {},
        "started": time.time(),
    }
    try:
        tmp = META_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, META_FILE)
    except OSError:
        pass


def read_meta() -> Optional[dict]:
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def clear_meta() -> None:
    try:
        if os.path.exists(META_FILE):
            os.remove(META_FILE)
    except OSError:
        sudo_exec_nonblock(["rm", "-f", META_FILE])


def kill_stale_daemons() -> None:
    """Ensure any previous OpenVPN daemon tied to CONF_FILE is cleanly terminated."""
    res = subprocess.run(["pgrep", "-f", CONF_FILE], capture_output=True, text=True)
    pids = res.stdout.strip().split()
    for p in pids:
        sudo_exec_nonblock(["kill", p])
    for _ in range(20):
        res = subprocess.run(["pgrep", "-f", CONF_FILE], capture_output=True, text=True)
        if not res.stdout.strip():
            break
        time.sleep(0.25)
    for p in res.stdout.strip().split():
        sudo_exec_nonblock(["kill", "-9", p])
    sudo_exec_nonblock(["rm", "-f", PID_FILE, CONF_FILE])


def start_openvpn_session(server: dict, connect_timeout: int = 10) -> Tuple[bool, int | str]:
    """Write patched .ovpn config and launch OpenVPN daemon."""
    patched = patch_ovpn_config(server, connect_timeout=connect_timeout)
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        f.write(patched)
    try:
        os.chmod(CONF_FILE, 0o600)
    except OSError:
        pass

    try:
        start_offset = os.path.getsize(LOG_FILE)
    except OSError:
        start_offset = 0

    ovpn_bin = get_openvpn_bin()
    argv = [
        ovpn_bin,
        "--config", CONF_FILE,
        "--daemon", "guangutvpn",
        "--writepid", PID_FILE,
        "--log-append", LOG_FILE,
        "--verb", "3",
    ]
    proc = sudo_exec(argv, capture=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "Failed to launch openvpn").strip()
        return False, err
    return True, start_offset


def wait_for_handshake(start_offset: int, timeout_sec: int = 18) -> Tuple[bool, str]:
    """Monitor OpenVPN log from `start_offset` until `Initialization Sequence Completed` or failure."""
    t0 = time.time()

    def read_tail() -> str:
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(max(0, start_offset))
                return f.read(16000)
        except PermissionError:
            res = sudo_exec_nonblock(["tail", "-c", f"+{max(1, start_offset + 1)}", LOG_FILE])
            return (res.stdout or "")[:16000]
        except OSError:
            return ""

    while time.time() - t0 < timeout_sec:
        pid = running_pid()
        tail = read_tail()
        if OK_MARKER in tail:
            time.sleep(1.2)  # Allow tun0 routes to settle
            return True, tail
        for marker in FAIL_MARKERS:
            if marker in tail:
                return False, tail
        if pid is None and (time.time() - t0) > 1.5:
            return False, read_tail()
        time.sleep(0.6)

    return False, read_tail()


def summarize_failure(log_tail: str, max_lines: int = 3) -> list[str]:
    keywords = ("error", "failed", "refused", "timeout", "cannot", "auth", "fatal", "tls")
    matches = [
        line.strip()
        for line in log_tail.splitlines()
        if any(k in line.lower() for k in keywords)
    ]
    return matches[-max_lines:] if matches else [l.strip() for l in log_tail.splitlines()[-max_lines:] if l.strip()]


def disconnect_vpn() -> Tuple[bool, str]:
    """Tear down active VPN tunnel, restore DNS, and remove Kill Switch."""
    pid = running_pid()
    meta = read_meta()
    kill_stale_daemons()
    disable_killswitch()
    restore_system_dns()
    clear_meta()
    if pid or meta:
        return True, f"Disconnected VPN tunnel (stopped pid {pid or 'daemon'}, restored DNS & firewall)."
    return False, "No active VPN connection found (cleaned any stale state)."
