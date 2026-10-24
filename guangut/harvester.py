"""Multi-Source VPN Harvester, Fast HTTPS US State/Region GeoIP Enricher & Live Socket Prober."""

from __future__ import annotations
import base64
import concurrent.futures
import csv
import glob
import io
import json
import os
import pwd
import socket
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from guangut import __app_name__, __version__
from guangut.patcher import extract_proto_and_remote
from guangut.regions import (
    US_REGIONS,
    US_STATE_CODE_TO_NAME,
    classify_us_region,
    haversine_km,
    match_us_region,
    normalize_us_state,
)

UA = f"{__app_name__}/{__version__} (Linux Debian 13; US-Regional VPN Client)"

VPNGATE_MIRRORS = [
    "http://www.vpngate.net/api/iphone/",
    "https://www.vpngate.net/api/iphone/",
]

REFERENCE_COUNTRY_MAP = {
    "USA": ("US", "United States"),
    "Canada": ("CA", "Canada"),
    "UK": ("GB", "United Kingdom"),
    "Germany": ("DE", "Germany"),
    "France": ("FR", "France"),
    "Netherlands": ("NL", "Netherlands"),
    "Japan": ("JP", "Japan"),
    "South Korea": ("KR", "South Korea"),
    "Sweden": ("SE", "Sweden"),
    "Romania": ("RO", "Romania"),
    "Poland": ("PL", "Poland"),
    "Italy": ("IT", "Italy"),
    "Thailand": ("TH", "Thailand"),
    "Vietnam": ("VN", "Vietnam"),
    "India": ("IN", "India"),
    "Indonesia": ("ID", "Indonesia"),
    "Emirates": ("AE", "United Arab Emirates"),
    "Turkey": ("TR", "Turkey"),
    "Ukraine": ("UA", "Ukraine"),
    "Russia": ("RU", "Russia"),
}


def real_home() -> str:
    """Return the home directory of the actual user even when invoked under sudo."""
    su = os.environ.get("SUDO_USER")
    if su and os.geteuid() == 0:
        try:
            return pwd.getpwnam(su).pw_dir
        except KeyError:
            pass
    return os.path.expanduser("~")


def cache_dir() -> str:
    return os.path.join(real_home(), ".cache", "guangutvpn")


def cache_file() -> str:
    return os.path.join(cache_dir(), "servers.json")


def geoip_cache_file() -> str:
    return os.path.join(cache_dir(), "geoip_cache.json")


def custom_configs_dir() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "configs", "custom")


def reference_ovpn_dir() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "reference", "zoult-ovpn")


def reference_auto_ovpn_dir() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "reference", "auto-ovpn", "configs")


def fix_ownership(path: str) -> None:
    """Ensure files created under sudo belong to the real invoking user."""
    su = os.environ.get("SUDO_USER")
    if su and os.geteuid() == 0:
        try:
            u = pwd.getpwnam(su)
            if os.path.exists(path):
                os.chown(path, u.pw_uid, u.pw_gid)
        except (KeyError, OSError):
            pass


def load_cache() -> Optional[dict]:
    path = cache_file()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "servers" in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def save_cache(data: dict) -> None:
    cdir = cache_dir()
    os.makedirs(cdir, exist_ok=True)
    fix_ownership(cdir)
    path = cache_file()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    fix_ownership(path)


def load_geoip_cache() -> Dict[str, dict]:
    path = geoip_cache_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_geoip_cache(data: Dict[str, dict]) -> None:
    cdir = cache_dir()
    os.makedirs(cdir, exist_ok=True)
    fix_ownership(cdir)
    path = geoip_cache_file()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    fix_ownership(path)


def http_get(url: str, timeout: int = 20, data: Optional[bytes] = None, headers: Optional[dict] = None) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": UA, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def quiet_int(val: object, default: int = 0) -> int:
    try:
        return int(float(str(val).strip()))
    except (TypeError, ValueError):
        return default


def fetch_vpngate_raw() -> str:
    urls = []
    if os.environ.get("VPNGATE_API"):
        urls.append(os.environ["VPNGATE_API"])
    urls.extend(VPNGATE_MIRRORS)
    last_err = None
    for url in urls:
        try:
            text = http_get(url, timeout=25).decode("utf-8", "replace")
            if "#HostName" in text:
                return text
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"Could not fetch live VPN server feed ({last_err})")


def parse_vpngate_csv(text: str) -> List[dict]:
    header = None
    body = []
    for line in text.splitlines():
        if line.startswith("*"):
            continue
        if header is None:
            if line.startswith("#HostName"):
                header = line.lstrip("#").split(",")
            continue
        if line.startswith("#") or not line.strip():
            continue
        body.append(line.rstrip("\r"))

    if not header:
        raise RuntimeError("Unrecognized VPN Gate CSV header format.")

    hmap = {name.strip().lower(): i for i, name in enumerate(header)}
    required = [
        "hostname", "ip", "score", "ping", "speed",
        "countrylong", "countryshort", "numvpnsessions", "uptime",
        "logtype", "operator", "openvpn_configdata_base64",
    ]
    idx = {k: hmap.get(k) for k in required}
    if any(v is None for v in idx.values()):
        raise RuntimeError("Missing expected columns in VPN Gate feed.")

    servers: List[dict] = []
    for row in csv.reader(io.StringIO("\n".join(body))):
        try:
            if len(row) < len(header) - 2:
                continue
            b64 = row[idx["openvpn_configdata_base64"]].strip()
            if len(b64) < 200:
                continue
            cfg = base64.b64decode(b64).decode("utf-8", "replace")
            proto, remote_host, port = extract_proto_and_remote(cfg)
            ip_addr = row[idx["ip"]].strip() or remote_host
            cc = row[idx["countryshort"]].strip().upper()
            servers.append({
                "host": row[idx["hostname"]].strip(),
                "ip": ip_addr,
                "score": quiet_int(row[idx["score"]]),
                "ping": quiet_int(row[idx["ping"]]),
                "speed": quiet_int(row[idx["speed"]]),
                "country": row[idx["countrylong"]].strip(),
                "cc": cc,
                "sessions": quiet_int(row[idx["numvpnsessions"]]),
                "uptime": quiet_int(row[idx["uptime"]]),
                "log": row[idx["logtype"]].strip(),
                "operator": row[idx["operator"]].strip(),
                "proto": proto,
                "port": int(port) if port else 1194,
                "cfg": cfg,
                "engine": "openvpn",
                "city": "",
                "region": "",
                "state_code": "",
                "us_region": "",
                "isp": "",
                "lat": None,
                "lon": None,
                "live_ms": None,
            })
        except Exception:
            continue
    return servers


def load_reference_ovpn_pool() -> List[dict]:
    """Load passwordless OpenVPN profiles from reference/zoult-ovpn (IPS_* and FOV_*) across US & global folders."""
    base_dir = reference_ovpn_dir()
    if not os.path.isdir(base_dir):
        return []
    servers: List[dict] = []
    seen_endpoints = set()
    for folder, (cc, country_name) in REFERENCE_COUNTRY_MAP.items():
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        for ovpn_path in sorted(glob.glob(os.path.join(folder_path, "*.ovpn"))):
            fname = os.path.basename(ovpn_path)
            # Skip profiles that require interactive auth-user-pass (like VBK_ or freeopenvpn generic)
            try:
                with open(ovpn_path, "r", encoding="utf-8", errors="replace") as f:
                    cfg = f.read()
                if "auth-user-pass" in cfg:
                    continue
                proto, host, port = extract_proto_and_remote(cfg)
                if not host:
                    continue
                ep_key = f"{host}:{port}:{proto}"
                if ep_key in seen_endpoints:
                    continue
                seen_endpoints.add(ep_key)
                servers.append({
                    "host": os.path.splitext(fname)[0],
                    "ip": host,
                    "score": 500000,
                    "ping": 25,
                    "speed": 150_000_000,
                    "country": country_name,
                    "cc": cc,
                    "sessions": 1,
                    "uptime": 100000,
                    "log": "community",
                    "operator": "IPSpeed / OpenVPN Community",
                    "proto": proto,
                    "port": int(port),
                    "cfg": cfg,
                    "engine": "openvpn",
                    "city": "",
                    "region": "",
                    "state_code": "",
                    "us_region": "",
                    "isp": "",
                    "lat": None,
                    "lon": None,
                    "live_ms": None,
                })
            except OSError:
                continue
    # Also load pre-saved server_X_CC.ovpn configs from reference/auto-ovpn/configs
    auto_dir = reference_auto_ovpn_dir()
    if os.path.isdir(auto_dir):
        for ovpn_path in sorted(glob.glob(os.path.join(auto_dir, "server_*_*.ovpn"))):
            fname = os.path.basename(ovpn_path)
            parts = os.path.splitext(fname)[0].split("_")
            if len(parts) < 3:
                continue
            cc = parts[-1].upper()
            try:
                with open(ovpn_path, "r", encoding="utf-8", errors="replace") as f:
                    cfg = f.read()
                proto, host, port = extract_proto_and_remote(cfg)
                if not host:
                    continue
                ep_key = f"{host}:{port}:{proto}"
                if ep_key in seen_endpoints:
                    continue
                seen_endpoints.add(ep_key)
                servers.append({
                    "host": os.path.splitext(fname)[0],
                    "ip": host,
                    "score": 450000,
                    "ping": 30,
                    "speed": 120_000_000,
                    "country": "United States" if cc == "US" else cc,
                    "cc": cc,
                    "sessions": 1,
                    "uptime": 100000,
                    "log": "auto-ovpn",
                    "operator": "Auto-OVPN Relay",
                    "proto": proto,
                    "port": int(port),
                    "cfg": cfg,
                    "engine": "openvpn",
                    "city": "",
                    "region": "",
                    "state_code": "",
                    "us_region": "",
                    "isp": "",
                    "lat": None,
                    "lon": None,
                    "live_ms": None,
                })
            except OSError:
                continue
    return servers


def load_custom_profiles() -> List[dict]:
    """Load any user-supplied .ovpn or WireGuard .conf files from configs/custom/."""
    cdir = custom_configs_dir()
    if not os.path.isdir(cdir):
        return []
    custom_servers: List[dict] = []
    for path in sorted(glob.glob(os.path.join(cdir, "*"))):
        if not (path.endswith(".ovpn") or path.endswith(".conf")):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            fname = os.path.basename(path)
            name_no_ext = os.path.splitext(fname)[0]
            parts = name_no_ext.split("_")
            cc = parts[0].upper() if len(parts[0]) == 2 else "US"
            state_code = parts[1].upper() if (cc == "US" and len(parts) > 1 and len(parts[1]) == 2) else ""
            if path.endswith(".ovpn"):
                proto, host, port = extract_proto_and_remote(content)
                custom_servers.append({
                    "host": f"custom:{name_no_ext}",
                    "ip": host or "custom",
                    "score": 9999999,
                    "ping": 10,
                    "speed": 100_000_000,
                    "country": "United States" if cc == "US" else cc,
                    "cc": cc,
                    "sessions": 1,
                    "uptime": 0,
                    "log": "custom",
                    "operator": "Custom Profile",
                    "proto": proto,
                    "port": port,
                    "cfg": content,
                    "engine": "openvpn",
                    "city": name_no_ext,
                    "region": US_STATE_CODE_TO_NAME.get(state_code, state_code),
                    "state_code": state_code,
                    "us_region": classify_us_region(state_code) if cc == "US" else "",
                    "isp": "Custom VPN",
                    "lat": None,
                    "lon": None,
                    "live_ms": None,
                })
            elif path.endswith(".conf"):
                custom_servers.append({
                    "host": f"wg:{name_no_ext}",
                    "ip": "wireguard",
                    "score": 9999999,
                    "ping": 5,
                    "speed": 250_000_000,
                    "country": "United States" if cc == "US" else cc,
                    "cc": cc,
                    "sessions": 1,
                    "uptime": 0,
                    "log": "custom-wg",
                    "operator": "Custom WireGuard",
                    "proto": "wg",
                    "port": 51820,
                    "cfg": content,
                    "cfg_path": path,
                    "engine": "wireguard",
                    "city": name_no_ext,
                    "region": US_STATE_CODE_TO_NAME.get(state_code, state_code),
                    "state_code": state_code,
                    "us_region": classify_us_region(state_code) if cc == "US" else "",
                    "isp": "WireGuard Tunnel",
                    "lat": None,
                    "lon": None,
                    "live_ms": None,
                })
        except OSError:
            continue
    return custom_servers


def _lookup_single_ip_https(ip: str) -> Optional[dict]:
    """Query HTTPS GeoIP providers (ipwho.is with ipinfo.io fallback) for exact State, City, ISP, Lat/Lon."""
    try:
        raw = http_get(f"https://ipwho.is/{ip}", timeout=5).decode("utf-8", "replace")
        d = json.loads(raw)
        if d.get("success"):
            conn = d.get("connection") or {}
            return {
                "city": d.get("city") or "",
                "region": d.get("region") or "",
                "state_code": d.get("region_code") or normalize_us_state(d.get("region") or ""),
                "cc": (d.get("country_code") or "").upper(),
                "country": d.get("country") or "",
                "isp": conn.get("isp") or conn.get("org") or "",
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
            }
    except Exception:
        pass

    try:
        raw = http_get(f"https://ipinfo.io/{ip}/json", timeout=5).decode("utf-8", "replace")
        d = json.loads(raw)
        if "ip" in d:
            loc = (d.get("loc") or "").split(",")
            lat = float(loc[0]) if len(loc) == 2 else None
            lon = float(loc[1]) if len(loc) == 2 else None
            reg = d.get("region") or ""
            return {
                "city": d.get("city") or "",
                "region": reg,
                "state_code": normalize_us_state(reg),
                "cc": (d.get("country") or "").upper(),
                "country": "United States" if d.get("country") == "US" else (d.get("country") or ""),
                "isp": d.get("org") or "",
                "lat": lat,
                "lon": lon,
            }
    except Exception:
        pass
    return None


def enrich_geoip(servers: List[dict], max_lookup: int = 45) -> int:
    """Fast concurrent HTTPS GeoIP enrichment for all US servers + top global servers."""
    geo_cache = load_geoip_cache()
    us_servers = [s for s in servers if s.get("cc") == "US"]
    other_servers = sorted(
        [s for s in servers if s.get("cc") != "US"],
        key=lambda r: -r.get("score", 0),
    )
    targets = (us_servers + other_servers)[:max_lookup]

    # Collect unique IPs not yet in persistent GeoIP cache
    to_fetch = sorted({
        s["ip"] for s in targets
        if s.get("ip") and "." in s["ip"] and s["ip"] not in geo_cache
    })

    if to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, len(to_fetch))) as pool:
            fmap = {pool.submit(_lookup_single_ip_https, ip): ip for ip in to_fetch}
            for fut in concurrent.futures.as_completed(fmap):
                ip = fmap[fut]
                try:
                    res = fut.result()
                    if res:
                        geo_cache[ip] = res
                except Exception:
                    pass
        save_geoip_cache(geo_cache)

    resolved_count = 0
    for srv in servers:
        g = geo_cache.get(srv.get("ip", ""))
        if not g:
            continue
        srv["city"] = g.get("city") or srv.get("city", "")
        srv["region"] = g.get("region") or srv.get("region", "")
        srv["isp"] = g.get("isp") or srv.get("isp", "")
        srv["lat"] = g.get("lat")
        srv["lon"] = g.get("lon")
        if srv.get("cc") == "US":
            raw_st = g.get("state_code", "")
            # If CDN/anycast IP resolved to non-US country in GeoIP, mark as US Anycast
            if g.get("cc") and g.get("cc") != "US":
                srv["state_code"] = "ANYCAST"
                srv["region"] = "US-Anycast"
                srv["city"] = "Cloudflare Edge"
                srv["us_region"] = "east"
            else:
                st_code = raw_st if (raw_st and raw_st.isalpha() and len(raw_st) == 2) else normalize_us_state(srv["region"])
                srv["state_code"] = st_code
                srv["us_region"] = classify_us_region(st_code, srv["lon"])
        if srv["city"] or srv["region"]:
            resolved_count += 1

    return resolved_count


def probe_server_latency(server: dict, timeout: float = 1.8) -> Optional[float]:
    """Perform a fast live TCP/socket reachability & latency check in milliseconds."""
    ip = server.get("ip", "")
    port = int(server.get("port") or 1194)
    proto = server.get("proto", "udp")
    if not ip or ip in ("custom", "wireguard"):
        return 5.0

    probe_ports = [port] if proto == "tcp" else [port, 443]
    for p in probe_ports:
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, p), timeout=timeout):
                ms = (time.perf_counter() - t0) * 1000.0
                return round(ms, 1)
        except ConnectionRefusedError:
            ms = (time.perf_counter() - t0) * 1000.0
            if proto == "udp":
                return round(ms, 1)
            return None
        except OSError:
            continue
    return None


def probe_candidates_parallel(candidates: List[dict], max_probe: int = 25, timeout: float = 1.6) -> List[dict]:
    """Concurrently probe candidate servers and return them sorted with live reachable ones first."""
    subset = candidates[:max_probe]
    rest = candidates[max_probe:]

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(1, len(subset)))) as pool:
        future_map = {pool.submit(probe_server_latency, srv, timeout): srv for srv in subset}
        for fut in concurrent.futures.as_completed(future_map):
            srv = future_map[fut]
            try:
                srv["live_ms"] = fut.result()
            except Exception:
                srv["live_ms"] = None

    def sort_key(s: dict) -> Tuple:
        live = s.get("live_ms")
        is_alive = 0 if live is not None else 1
        live_val = live if live is not None else 9999.0
        udp_pref = 0 if s.get("proto") == "udp" else 1
        return (is_alive, live_val, udp_pref, -s.get("speed", 0), -s.get("score", 0))

    sorted_subset = sorted(subset, key=sort_key)
    return sorted_subset + rest


def rank_server(s: dict) -> Tuple:
    """Static ranking before live socket probing."""
    live = s.get("live_ms")
    live_ok = 0 if (live is not None and live < 1500) else 1
    ping_ok = 0 if (0 < s.get("ping", 0) < 900) else 1
    udp = 0 if s.get("proto") == "udp" else 1
    return (
        live_ok,
        live if live is not None else 9999.0,
        ping_ok,
        udp,
        -s.get("speed", 0),
        s.get("ping", 9999) if s.get("ping", 0) > 0 else 9999,
        -s.get("score", 0),
    )


def refresh_server_list(enrich: bool = True) -> List[dict]:
    """Fetch VPN Gate servers + community US/global pool + custom profiles, enrich GeoIP, and save cache."""
    vpngate_servers: List[dict] = []
    try:
        raw_csv = fetch_vpngate_raw()
        vpngate_servers = parse_vpngate_csv(raw_csv)
    except Exception:
        pass

    ref_servers = load_reference_ovpn_pool()
    custom = load_custom_profiles()

    # Deduplicate by (ip, port, proto)
    combined: List[dict] = []
    seen = set()
    for srv in custom + vpngate_servers + ref_servers:
        key = (srv.get("ip"), srv.get("port"), srv.get("proto"))
        if key not in seen:
            seen.add(key)
            combined.append(srv)

    if enrich and combined:
        enrich_geoip(combined)

    save_cache({"updated": time.time(), "servers": combined})
    return combined


def filter_servers(
    servers: List[dict],
    country: Optional[str] = "US",
    us_region: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    proto: Optional[str] = None,
) -> Tuple[List[dict], str]:
    """Filter servers by Country (default US), US Region (east/central/west/all), US State, City, and Protocol."""
    out = list(servers)
    notes = []

    if state or us_region:
        country = "US"

    if country and country.upper() not in ("ALL", "ANY", "*"):
        q = country.strip()
        c_match = [r for r in out if r.get("cc", "").upper() == q.upper()]
        if not c_match:
            c_match = [r for r in out if q.lower() in r.get("country", "").lower()]
        if not c_match:
            return [], f"No servers found for country '{country}'."
        out = c_match

    if us_region:
        reg_clean = us_region.strip().lower().replace("us-", "").replace("us_", "")
        if reg_clean not in ("all", "any", "us", "*"):
            r_match = [r for r in out if match_us_region(r, reg_clean)]
            if r_match:
                out = r_match
            else:
                reg_info = US_REGIONS.get(reg_clean)
                if reg_info and "centroid" in reg_info:
                    clat, clon = reg_info["centroid"]
                    geo_us = [r for r in out if r.get("lat") is not None and r.get("lon") is not None]
                    if geo_us:
                        geo_us.sort(key=lambda r: haversine_km(r["lat"], r["lon"], clat, clon))
                        out = geo_us
                        notes.append(
                            f"No exact server in US-{reg_clean.upper()} right now; ranked closest US servers by distance."
                        )

    if state:
        st_code = normalize_us_state(state) or state.strip().upper()
        st_match = [
            r for r in out
            if r.get("state_code", "").upper() == st_code
            or state.strip().lower() in r.get("region", "").lower()
        ]
        if st_match:
            out = st_match
        else:
            avail_states = sorted({r.get("state_code") or r.get("region") for r in out if r.get("state_code") or r.get("region")})
            notes.append(
                f"No live US server in state '{state}' right now (available US states: {', '.join(avail_states) or 'run refresh'}). Falling back to best US servers."
            )

    if city:
        c_q = city.strip().lower()
        city_match = [
            r for r in out
            if c_q in f"{r.get('city', '')} {r.get('region', '')} {r.get('isp', '')} {r.get('host', '')}".lower()
        ]
        if city_match:
            out = city_match
        else:
            avail_cities = sorted({r.get("city") for r in out if r.get("city")})
            notes.append(
                f"No exact match for city '{city}' (available: {', '.join(avail_cities[:12]) or 'none'}). Showing top matches in region/country."
            )

    if proto and proto.lower() in ("udp", "tcp", "wg"):
        p_match = [r for r in out if r.get("proto", "").lower() == proto.lower()]
        if p_match:
            out = p_match

    out.sort(key=rank_server)
    return out, " | ".join(notes)

