#!/usr/bin/env python3
"""GuangutVPN — CLI & Interactive US-Regional / Global VPN Dashboard for Linux."""

from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
from typing import Optional

from guangut import __app_name__, __version__
from guangut.harvester import (
    cache_file,
    filter_servers,
    load_cache,
    probe_candidates_parallel,
    refresh_server_list,
)
from guangut.patcher import patch_ovpn_config
from guangut.regions import US_REGIONS, US_STATE_CODE_TO_NAME
from guangut.security import (
    configure_tunnel_dns,
    enable_killswitch,
    is_killswitch_active,
)
from guangut.tunnel import (
    check_vpn_binaries,
    disconnect_vpn,
    fetch_public_ip_geo,
    get_active_tun_iface,
    kill_stale_daemons,
    read_meta,
    running_pid,
    save_meta,
    start_openvpn_session,
    summarize_failure,
    wait_for_handshake,
)


# ---------------------------------------------------------------------------
# ANSI Styling Helpers
# ---------------------------------------------------------------------------
def _color_ok() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM") not in (None, "dumb") and not os.environ.get("NO_COLOR")


USE_COLOR = _color_ok()


def c(text: str, code: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if USE_COLOR else text


def bold(s: str) -> str: return c(s, "1")
def green(s: str) -> str: return c(s, "1;32")
def yellow(s: str) -> str: return c(s, "1;33")
def red(s: str) -> str: return c(s, "1;31")
def cyan(s: str) -> str: return c(s, "1;36")
def blue(s: str) -> str: return c(s, "1;34")
def dim(s: str) -> str: return c(s, "2")


def clip(text: str, length: int) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1] + "…"


def fmt_speed(bps: object) -> str:
    try:
        val = float(int(bps))
    except (TypeError, ValueError):
        return "?"
    for unit in ("bps", "Kbps", "Mbps", "Gbps"):
        if val < 1000.0 or unit == "Gbps":
            return f"{val:.0f} {unit}" if unit == "bps" else f"{val:.1f} {unit}"
        val /= 1000.0
    return "?"


BANNER = r"""
   ____                                _   __     _______  _   _ 
  / ___|_   _  __ _ _ __   __ _ _   _| |_\ \   / /  _ \| \ | |
 | |  _| | | |/ _` | '_ \ / _` | | | | __|\ \ / /| |_) |  \| |
 | |_| | |_| | (_| | | | | (_| | |_| | |_  \ V / |  __/| |\  |
  \____|\__,_|\__,_|_| |_|\__, |\__,_|\__|  \_/  |_|   |_| \_|
                          |___/                               
"""


def print_banner() -> None:
    print(cyan(BANNER.strip("\n")))
    print(
        dim(f"  GuangutVPN v{__version__} — US-Regional (East/Central/West/State) & Global Linux Kernel VPN")
    )
    print(dim("  " + "─" * 74))


def ensure_server_cache(max_age_sec: int = 1800) -> dict:
    cache = load_cache()
    if not cache or (time.time() - cache.get("updated", 0) > max_age_sec):
        print(cyan("⟳ Fetching live VPN servers & resolving US State/Region GeoIP data..."))
        servers = refresh_server_list(enrich=True)
        cache = {"updated": time.time(), "servers": servers}
    return cache


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
def cmd_refresh(args: argparse.Namespace) -> int:
    t0 = time.time()
    print(cyan("⟳ Harvesting live VPN servers & resolving US State/Region GeoIP coordinates..."))
    servers = refresh_server_list(enrich=not args.no_geo)
    elapsed = time.time() - t0
    us_servers = [s for s in servers if s.get("cc") == "US"]
    us_states = sorted({s.get("state_code") for s in us_servers if s.get("state_code")})
    countries = sorted({s.get("cc") for s in servers if s.get("cc")})
    print(
        f"{green('✓ Refresh Complete')} in {elapsed:.1f}s — "
        f"{bold(str(len(servers)))} total servers across {bold(str(len(countries)))} countries."
    )
    print(
        f"  [US] {bold(str(len(us_servers)))} United States servers ready "
        f"(States: {', '.join(us_states) if us_states else 'Enriched'})"
    )
    print(f"  [CACHE] Saved to: {dim(cache_file())}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cache = ensure_server_cache()
    servers = cache.get("servers", [])

    if args.countries:
        by_cc: dict[str, dict] = {}
        for s in servers:
            cc = s.get("cc", "??")
            entry = by_cc.setdefault(cc, {"country": s.get("country", cc), "count": 0, "best_speed": 0, "states": set()})
            entry["count"] += 1
            if s.get("speed", 0) > entry["best_speed"]:
                entry["best_speed"] = s.get("speed", 0)
            if cc == "US" and s.get("state_code"):
                entry["states"].add(s["state_code"])

        rows = sorted(by_cc.items(), key=lambda kv: (0 if kv[0] == "US" else 1, -kv[1]["count"]))
        print(bold(f"\n{'CODE':<6} {'COUNTRY':<28} {'SERVERS':>8} {'MAX SPEED':>14}   {'REGIONS / STATES'}"))
        print("─" * 82)
        for cc, info in rows:
            flag = "[US] " if cc == "US" else "[GL] "
            reg_note = ", ".join(sorted(info["states"])) if cc == "US" and info["states"] else "Global Relay"
            print(
                f"{cc:<6} {flag}{clip(info['country'], 23):<23} {info['count']:>8} "
                f"{fmt_speed(info['best_speed']):>14}   {clip(reg_note, 28)}"
            )
        return 0

    target_country = "ALL" if args.all_countries else (args.country or "US")
    filtered, note = filter_servers(
        servers,
        country=target_country,
        us_region=args.us_region,
        state=args.state,
        city=args.city,
        proto=args.proto,
    )
    if note:
        print(yellow(f"ℹ {note}"))
    if not filtered:
        print(red("✗ No matching servers found. Try `guangut list --countries` or `guangut refresh`."))
        return 1

    if args.probe:
        print(cyan(f"⚡ Probing live socket latency for top {min(len(filtered), args.limit)} servers..."))
        filtered = probe_candidates_parallel(filtered, max_probe=min(len(filtered), args.limit))

    scope_label = f"US ({args.us_region or args.state or 'All States'})" if target_country.upper() == "US" else target_country.upper()
    print(bold(f"\nShowing top {min(len(filtered), args.limit)} of {len(filtered)} servers for [{scope_label}]:"))
    header = (
        f"{'#':>3}  {'CC':<3} {'US-REG':<8} {'STATE/CITY':<22} {'IP:PORT':<21} "
        f"{'PROTO':<5} {'LIVE RTT':>10} {'SPEED':>11}  {'ISP / OPERATOR'}"
    )
    print(bold(header))
    print("─" * 108)
    for idx, s in enumerate(filtered[: args.limit], 1):
        cc = s.get("cc", "??")
        us_reg = (s.get("us_region") or "—").upper() if cc == "US" else "—"
        st = s.get("state_code") or s.get("region") or ""
        city = s.get("city") or ""
        loc = f"{st} / {city}".strip(" /") or s.get("country", "—")
        ip_port = f"{s.get('ip', '?')}:{s.get('port', '?')}"
        proto = s.get("proto", "udp").upper()
        live_ms = s.get("live_ms")
        if live_ms is not None:
            rtt_str = green(f"{live_ms:.0f} ms")
        elif 0 < s.get("ping", 0) < 900:
            rtt_str = f"{s['ping']} ms"
        else:
            rtt_str = dim("unprobed")
        isp = s.get("isp") or s.get("operator") or s.get("host", "")
        print(
            f"{idx:>3}  {cc:<3} {us_reg:<8} {clip(loc, 21):<22} {ip_port:<21} "
            f"{proto:<5} {rtt_str:>10} {fmt_speed(s.get('speed')):>11}  {clip(isp, 24)}"
        )
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    has_ovpn, _ = check_vpn_binaries()
    if not has_ovpn:
        print(red("✗ OpenVPN binary is not installed yet!"))
        print(yellow("  Run this first to install the Linux tunnel packages:"))
        print(bold("  sudo apt update && sudo apt install -y openvpn wireguard-tools openresolv"))
        return 2

    if os.geteuid() != 0:
        # Re-invoke self under sudo so user gets prompted cleanly if needed
        print(cyan("🔒 Elevating privileges via sudo to configure Linux tun0 interface & routing..."))
        cmd = ["sudo", sys.executable, os.path.abspath(sys.argv[0])] + sys.argv[1:]
        return subprocess.run(cmd).returncode

    cache = ensure_server_cache()
    servers = cache.get("servers", [])

    target_country = args.country or args.country_pos or "US"
    candidates, note = filter_servers(
        servers,
        country=target_country,
        us_region=args.us_region,
        state=args.state,
        city=args.city,
        proto=args.proto,
    )
    if note:
        print(yellow(f"ℹ {note}"))
    if not candidates:
        print(red(f"✗ No candidate servers matched country={target_country} region={args.us_region} state={args.state}"))
        return 1

    if args.index:
        if 1 <= args.index <= len(candidates):
            candidates = [candidates[args.index - 1]]
        else:
            print(red(f"✗ --index {args.index} is out of range (1..{len(candidates)})"))
            return 1
    else:
        print(cyan(f"⚡ Probing live TCP/UDP sockets across {min(len(candidates), 20)} candidate relays..."))
        candidates = probe_candidates_parallel(candidates, max_probe=20)

    old_pid = running_pid()
    if old_pid:
        print(yellow(f"⟳ Stopping existing VPN session (pid {old_pid})..."))
    kill_stale_daemons()

    tries = candidates[: args.max_tries]
    for attempt, srv in enumerate(tries, 1):
        cc = srv.get("cc", "US")
        st = srv.get("state_code") or srv.get("region") or ""
        city = srv.get("city") or srv.get("host") or ""
        reg_tag = f"US-{srv.get('us_region', '').upper()}" if cc == "US" and srv.get("us_region") else cc
        rtt = f"{srv['live_ms']:.0f}ms" if srv.get("live_ms") is not None else f"{srv.get('ping', '?')}ms"

        print(
            f"\n{bold(f'[Attempt {attempt}/{len(tries)}]')} Connecting to "
            f"{cyan(f'{reg_tag} | {st} {city}'.strip())} — "
            f"{srv.get('ip')}:{srv.get('port')} ({srv.get('proto', 'udp').upper()}, RTT {rtt}, {fmt_speed(srv.get('speed'))})"
        )

        ok, res = start_openvpn_session(srv, connect_timeout=args.timeout)
        if not ok:
            print(red(f"  ✗ Failed to start OpenVPN daemon: {res}"))
            continue

        print(dim("  ⏳ Negotiating OpenVPN 2.6+ TLS & data-ciphers tunnel (tun0)..."))
        ready, log_tail = wait_for_handshake(int(res), timeout_sec=args.timeout + 10)
        if ready:
            dns_msg = configure_tunnel_dns("tun0")
            ks_msg = "Disabled (use --killswitch to enable)"
            if args.killswitch:
                ks_ok, ks_msg = enable_killswitch(srv.get("ip", ""))

            exit_geo = fetch_public_ip_geo()
            save_meta(srv, exit_info=exit_geo, killswitch=args.killswitch)
            tun_iface = get_active_tun_iface() or "tun0"

            print("\n" + green("═" * 74))
            print(green("  ✓ GUANGUT VPN CONNECTED — FULL LINUX KERNEL TUNNEL ACTIVE"))
            print(green("═" * 74))
            print(f"  • Tunnel Interface : {bold(tun_iface)} (PID: {running_pid()})")
            print(f"  • VPN Relay Host   : {srv.get('host')} ({srv.get('ip')}:{srv.get('port')} {srv.get('proto', '').upper()})")
            print(f"  • Target Region    : {reg_tag} — {st}, {city} ({srv.get('country')})")
            if exit_geo:
                print(
                    f"  • Verified Exit IP : {bold(green(exit_geo.get('ip', '?')))} — "
                    f"{exit_geo.get('city', '?')}, {exit_geo.get('region', '?')}, {exit_geo.get('country', '?')}"
                )
                print(f"  • Exit ISP / Org   : {exit_geo.get('isp', '?')}")
            print(f"  • DNS Leak Guard   : {dns_msg}")
            print(f"  • Kill Switch      : {ks_msg}")
            print(green("═" * 74))
            print(dim("  Run `guangut status` to check anytime, or `sudo guangut disconnect` to stop."))
            return 0

        # Handshake failed on this candidate; clean up and roll over to next server
        kill_stale_daemons()
        for err_line in summarize_failure(log_tail):
            print(red(f"  × {clip(err_line, 100)}"))

    print(yellow("\n⚠ All attempted relays timed out or dropped handshake. Try `guangut refresh` or increase `--max-tries`."))
    return 1


def cmd_disconnect(args: argparse.Namespace) -> int:
    if os.geteuid() != 0 and running_pid() is not None:
        cmd = ["sudo", sys.executable, os.path.abspath(sys.argv[0]), "disconnect"]
        return subprocess.run(cmd).returncode
    ok, msg = disconnect_vpn()
    print(green(f"✓ {msg}") if ok else yellow(f"ℹ {msg}"))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    pid = running_pid()
    tun = get_active_tun_iface()
    ks = is_killswitch_active()
    meta = read_meta() or {}
    geo = fetch_public_ip_geo()

    print_banner()
    if pid and tun:
        uptime_s = int(time.time() - meta.get("started", time.time()))
        mins, secs = divmod(uptime_s, 60)
        hrs, mins = divmod(mins, 60)
        up_str = f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"
        print(f"  Status           : {green('● CONNECTED (Encrypted Kernel Tunnel)')}")
        print(f"  Interface / PID  : {bold(tun)}  (OpenVPN PID {pid}, uptime {up_str})")
        print(
            f"  Connected Server : {meta.get('host', '?')} ({meta.get('ip', '?')}:{meta.get('port', '?')} "
            f"{str(meta.get('proto', 'udp')).upper()})"
        )
        loc_parts = [p for p in (meta.get("city"), meta.get("state_code") or meta.get("region"), meta.get("country")) if p]
        us_reg = f" [US-{meta['us_region'].upper()}]" if meta.get("us_region") else ""
        print(f"  Server Location  : {', '.join(loc_parts)}{us_reg}")
        print(f"  Kill Switch      : {green('ACTIVE (nftables)') if ks else dim('Inactive')}")
    else:
        print(f"  Status           : {red('○ DISCONNECTED (Direct Unprotected Connection)')}")
        if ks:
            print(f"  Kill Switch      : {yellow('ACTIVE (blocking non-VPN traffic!)')}")

    if geo:
        label = "Public Exit IP   " if (pid and tun) else "Real Public IP   "
        print(
            f"  {label}: {bold(geo.get('ip', '?'))} — "
            f"{geo.get('city', '?')}, {geo.get('region', '?')} ({geo.get('country', '?')})"
        )
        print(f"  ISP / Network    : {geo.get('isp', '?')}")
    print()
    return 0


def cmd_export_ovpn(args: argparse.Namespace) -> int:
    """Export a reverse-engineered, OpenVPN 2.6+-patched .ovpn file for inspection or NetworkManager import."""
    cache = ensure_server_cache()
    servers = cache.get("servers", [])
    candidates, _ = filter_servers(
        servers,
        country=args.country or "US",
        us_region=args.us_region,
        state=args.state,
        city=args.city,
        proto=args.proto,
    )
    if not candidates:
        print(red("✗ No matching server found to export."))
        return 1
    srv = candidates[0]
    patched = patch_ovpn_config(srv)
    out_path = args.output or f"/home/yona/Projects/GuangutVPN/configs/{srv.get('cc', 'US')}_{srv.get('state_code') or 'relay'}_{srv.get('host', 'vpn')}.ovpn"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(patched)
    print(green(f"✓ Exported OpenVPN 2.6+ patched configuration to: {bold(out_path)}"))
    print(dim(f"  Server: {srv.get('ip')}:{srv.get('port')} ({srv.get('proto', '').upper()}) — {srv.get('city')}, {srv.get('region')}, {srv.get('country')}"))
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    """Interactive menu for selecting US All, Part of US (East/Central/West/State), or Global Countries."""
    while True:
        print("\x1b[H\x1b[2J", end="", flush=True)
        cmd_status(args)
        print(bold("  Select an action:"))
        print(f"    {cyan('1)')} [US-ALL]     Connect Fastest US Server (All-US Auto-Probe)")
        print(f"    {cyan('2)')} [US-EAST]    Connect US-East    (NY, VA, NJ, FL, GA, MA, PA, DC)")
        print(f"    {cyan('3)')} [US-CENTRAL] Connect US-Central (TX, IL, OH, MI, MN, MO)")
        print(f"    {cyan('4)')} [US-WEST]    Connect US-West    (CA, CO, WA, OR, AZ, NV, UT)")
        print(f"    {cyan('5)')} [US-STATE]   Connect by Specific US State (e.g. CA, CO, TX)")
        print(f"    {cyan('6)')} [GLOBAL]     Connect Other Country (JP, GB, DE, CA, KR, NL, SG...)")
        print(f"    {cyan('7)')} [LIST]       List Live US Servers & Latency")
        print(f"    {cyan('8)')} [REFRESH]    Refresh Live Server Feed & GeoIP Cache")
        print(f"    {cyan('9)')} [STOP]       Disconnect VPN")
        print(f"    {cyan('q)')} Exit Menu")
        try:
            choice = input(bold("\n  guangut> ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in ("q", "quit", "exit"):
            return 0
        elif choice == "1":
            ns = argparse.Namespace(country="US", country_pos=None, us_region="all", state=None, city=None, proto=None, index=None, max_tries=5, timeout=12, killswitch=False)
            cmd_connect(ns)
            input(dim("\nPress Enter to return to menu..."))
        elif choice in ("2", "3", "4"):
            reg_map = {"2": "east", "3": "central", "4": "west"}
            ns = argparse.Namespace(country="US", country_pos=None, us_region=reg_map[choice], state=None, city=None, proto=None, index=None, max_tries=5, timeout=12, killswitch=False)
            cmd_connect(ns)
            input(dim("\nPress Enter to return to menu..."))
        elif choice == "5":
            st = input("  Enter 2-letter US State code or name (e.g. CA, NY, TX, VA, Oregon): ").strip()
            if st:
                ns = argparse.Namespace(country="US", country_pos=None, us_region=None, state=st, city=None, proto=None, index=None, max_tries=5, timeout=12, killswitch=False)
                cmd_connect(ns)
                input(dim("\nPress Enter to return to menu..."))
        elif choice == "6":
            ns_list = argparse.Namespace(countries=True, all_countries=False, country="US", us_region=None, state=None, city=None, proto=None, limit=30, probe=False)
            cmd_list(ns_list)
            cc = input("\n  Enter 2-letter Country Code (e.g. JP, KR, GB, DE, CA): ").strip()
            if cc:
                ns = argparse.Namespace(country=cc, country_pos=None, us_region=None, state=None, city=None, proto=None, index=None, max_tries=5, timeout=12, killswitch=False)
                cmd_connect(ns)
                input(dim("\nPress Enter to return to menu..."))
        elif choice == "7":
            ns_list = argparse.Namespace(countries=False, all_countries=False, country="US", us_region=None, state=None, city=None, proto=None, limit=25, probe=True)
            cmd_list(ns_list)
            input(dim("\nPress Enter to return to menu..."))
        elif choice == "8":
            cmd_refresh(argparse.Namespace(no_geo=False))
            input(dim("\nPress Enter to return to menu..."))
        elif choice == "9":
            cmd_disconnect(argparse.Namespace())
            input(dim("\nPress Enter to return to menu..."))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="guangut",
        description="GuangutVPN — Native Linux Kernel VPN Client with US Regional/State Targeting & OpenVPN 2.6+ Auto-Patcher",
    )
    p.add_argument("--version", action="version", version=f"GuangutVPN {__version__}")
    sub = p.add_subparsers(dest="cmd")

    # refresh
    p_ref = sub.add_parser("refresh", help="Fetch live VPN relays and enrich US States/Regions & global GeoIP")
    p_ref.add_argument("--no-geo", action="store_true", help="Skip GeoIP batch enrichment")
    p_ref.set_defaults(fn=cmd_refresh)

    # list
    p_lst = sub.add_parser("list", help="List available US servers (by region/state) or global countries")
    p_lst.add_argument("--country", "-c", default="US", help="Country code (default: US, or JP, GB, DE, ALL)")
    p_lst.add_argument("--us-region", "-r", choices=["all", "east", "central", "west", "northeast", "south", "midwest"], help="Filter part of US by region")
    p_lst.add_argument("--state", "-s", help="Filter US servers by state code or name (e.g. CA, NY, TX, VA)")
    p_lst.add_argument("--city", help="Filter by city name")
    p_lst.add_argument("--proto", choices=["udp", "tcp"], help="Filter by transport protocol")
    p_lst.add_argument("--countries", action="store_true", help="List summary of all available countries")
    p_lst.add_argument("--all-countries", action="store_true", help="List servers across all countries")
    p_lst.add_argument("--probe", action="store_true", help="Run live TCP/UDP socket latency probe on listed servers")
    p_lst.add_argument("--limit", "-n", type=int, default=25, help="Max rows to display")
    p_lst.set_defaults(fn=cmd_list)

    # connect
    p_con = sub.add_parser("connect", help="Connect to fastest US server, specific US region/state, or another country")
    p_con.add_argument("country_pos", nargs="?", help="Optional country code (default: US)")
    p_con.add_argument("--country", "-c", help="Target country code (default: US; or JP, KR, GB, DE, CA...)")
    p_con.add_argument("--us-region", "-r", choices=["all", "east", "central", "west", "northeast", "south", "midwest"], help="Target part of the US (east, central, west, northeast, south, midwest)")
    p_con.add_argument("--state", "-s", help="Target specific US state (e.g. CA, NY, TX, VA, WA, FL, IL)")
    p_con.add_argument("--city", help="Target specific city")
    p_con.add_argument("--proto", choices=["udp", "tcp"], help="Prefer UDP or TCP transport")
    p_con.add_argument("--index", "-i", type=int, help="Connect to specific server # from `guangut list`")
    p_con.add_argument("--max-tries", type=int, default=5, help="Max automatic failover attempts (default: 5)")
    p_con.add_argument("--timeout", type=int, default=10, help="Socket handshake timeout per attempt in seconds")
    p_con.add_argument("--killswitch", "-k", action="store_true", help="Enable nftables kernel Kill Switch")
    p_con.set_defaults(fn=cmd_connect)

    # disconnect
    p_dis = sub.add_parser("disconnect", help="Disconnect active VPN tunnel and restore DNS & firewall")
    p_dis.set_defaults(fn=cmd_disconnect)

    # status
    p_st = sub.add_parser("status", help="Show current VPN tunnel status, interface, and verified public exit IP")
    p_st.set_defaults(fn=cmd_status)

    # export
    p_exp = sub.add_parser("export", help="Export a patched OpenVPN 2.6+ .ovpn profile to disk")
    p_exp.add_argument("--country", "-c", default="US", help="Country code (default: US)")
    p_exp.add_argument("--us-region", "-r", help="US region (east, central, west)")
    p_exp.add_argument("--state", "-s", help="US state (e.g. CA, NY, TX)")
    p_exp.add_argument("--city", help="City substring")
    p_exp.add_argument("--proto", choices=["udp", "tcp"], help="Protocol")
    p_exp.add_argument("--output", "-o", help="Output .ovpn file path")
    p_exp.set_defaults(fn=cmd_export_ovpn)

    # menu
    p_menu = sub.add_parser("menu", help="Launch interactive terminal dashboard")
    p_menu.set_defaults(fn=cmd_interactive)

    # gui
    p_gui = sub.add_parser("gui", help="Launch local Web GUI Control Center in browser (http://127.0.0.1:8765)")
    p_gui.add_argument("--port", "-p", type=int, default=8765, help="Local port (default: 8765)")
    p_gui.add_argument("--no-browser", action="store_true", help="Do not auto-open browser")
    p_gui.set_defaults(fn=lambda a: __import__("guangut.gui", fromlist=["run_web_gui"]).run_web_gui(port=a.port, open_browser=not a.no_browser))

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        if sys.stdin.isatty() and sys.stdout.isatty():
            sys.exit(cmd_interactive(args))
        else:
            parser.print_help()
            sys.exit(0)
    try:
        sys.exit(args.fn(args) or 0)
    except KeyboardInterrupt:
        print(yellow("\nInterrupted by user."))
        sys.exit(130)


if __name__ == "__main__":
    main()

