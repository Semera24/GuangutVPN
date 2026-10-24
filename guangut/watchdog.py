"""GuangutVPN Watchdog Daemon — Tunnel Health Supervisor & Auto-Failover Service."""

from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
from typing import Optional

from guangut.harvester import filter_servers, load_cache, probe_candidates_parallel, refresh_server_list
from guangut.security import configure_tunnel_dns
from guangut.tunnel import (
    clear_meta,
    fetch_public_ip_geo,
    get_active_tun_iface,
    kill_stale_daemons,
    read_meta,
    running_pid,
    save_meta,
    start_openvpn_session,
    wait_for_handshake,
)

WATCH_PID_FILE = "/run/guangutvpn-watchdog.pid"
WATCH_STATE_FILE = "/var/tmp/guangutvpn-watchdog.json"


def is_watchdog_running() -> Optional[int]:
    try:
        with open(WATCH_PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        if os.path.exists(f"/proc/{pid}"):
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace")
            if "watch" in cmd or "guangut" in cmd:
                return pid
    except (OSError, ValueError):
        pass
    return None


def write_watch_state(state: dict) -> None:
    try:
        tmp = WATCH_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, WATCH_STATE_FILE)
    except OSError:
        pass


def read_watch_state() -> dict:
    try:
        with open(WATCH_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def ping_check(host: str = "1.1.1.1", timeout: int = 3) -> bool:
    res = subprocess.run(
        ["ping", "-c", "1", "-W", str(timeout), host],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0


def reconnect_tunnel(country: str = "US", us_region: Optional[str] = None, state: Optional[str] = None) -> bool:
    cache = load_cache() or {}
    servers = cache.get("servers", [])
    if not servers:
        servers = refresh_server_list(enrich=True)

    filtered, _ = filter_servers(servers, country=country, us_region=us_region, state=state)
    candidates = probe_candidates_parallel(filtered, max_probe=8)

    for srv in candidates[:4]:
        kill_stale_daemons()
        ok, res = start_openvpn_session(srv, connect_timeout=10)
        if not ok:
            continue
        ready, _ = wait_for_handshake(int(res), timeout_sec=14)
        if ready:
            configure_tunnel_dns("tun0")
            geo = fetch_public_ip_geo(timeout=4)
            save_meta(srv, exit_info=geo, killswitch=False)
            return True
        kill_stale_daemons()
    return False


def run_watchdog_loop(
    country: str = "US",
    us_region: Optional[str] = None,
    state: Optional[str] = None,
    check_interval: int = 5,
    max_retries: int = 10,
) -> None:
    # Save PID
    with open(WATCH_PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    state_info = {
        "active": True,
        "pid": os.getpid(),
        "country": country,
        "us_region": us_region,
        "state": state,
        "reconnect_count": 0,
        "last_health_check": time.time(),
        "status": "watching",
    }
    write_watch_state(state_info)

    def _sig_handler(signum, frame):
        state_info["active"] = False
        state_info["status"] = "stopped"
        write_watch_state(state_info)
        try:
            if os.path.exists(WATCH_PID_FILE):
                os.remove(WATCH_PID_FILE)
        except OSError:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    print(f"[WATCHDOG] Started watchdog daemon (PID: {os.getpid()})")
    print(f"[WATCHDOG] Monitoring target: {country} (Region: {us_region or 'all'}, State: {state or 'any'})")

    failed_checks = 0
    while True:
        time.sleep(check_interval)
        state_info["last_health_check"] = time.time()

        pid = running_pid()
        tun = get_active_tun_iface()

        healthy = bool(pid and tun and ping_check())

        if healthy:
            failed_checks = 0
            state_info["status"] = f"healthy (tun: {tun}, pid: {pid})"
            write_watch_state(state_info)
            continue

        failed_checks += 1
        print(f"[WATCHDOG] Health check failed ({failed_checks}/2). Tun: {tun}, PID: {pid}")

        if failed_checks >= 2:
            state_info["status"] = "reconnecting"
            write_watch_state(state_info)
            print("[WATCHDOG] Tunnel dropped! Initiating automatic recovery...")

            recovered = reconnect_tunnel(country=country, us_region=us_region, state=state)
            if recovered:
                failed_checks = 0
                state_info["reconnect_count"] += 1
                state_info["status"] = "recovered"
                write_watch_state(state_info)
                print(f"[WATCHDOG] Successfully recovered tunnel! Total recoveries: {state_info['reconnect_count']}")
            else:
                print("[WATCHDOG] Recovery cycle failed. Waiting before retry...")
                time.sleep(5)
