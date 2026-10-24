#!/usr/bin/env python3
"""GuangutVPN — Local Interactive Web GUI Dashboard (Zero-Dependency HTTP Server)."""

from __future__ import annotations
import http.server
import json
import os
import socketserver
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from typing import Any

from guangut import __version__
from guangut.harvester import (
    filter_servers,
    load_cache,
    probe_candidates_parallel,
    refresh_server_list,
)
from guangut.security import configure_tunnel_dns, enable_killswitch, is_killswitch_active
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

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>GuangutVPN — Linux US & Global VPN Control Center</title>
<style>
  :root {
    --bg: #0b0f19;
    --card: #131b2e;
    --card-border: #1e293b;
    --accent: #38bdf8;
    --accent-green: #22c55e;
    --accent-red: #ef4444;
    --accent-amber: #f59e0b;
    --text: #f1f5f9;
    --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--card-border);
    margin-bottom: 24px;
  }
  .brand h1 { font-size: 1.6rem; letter-spacing: -0.5px; color: var(--accent); }
  .brand p { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
  .badge {
    padding: 6px 14px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .badge.connected { background: rgba(34,197,94,0.15); color: var(--accent-green); border: 1px solid rgba(34,197,94,0.4); }
  .badge.disconnected { background: rgba(239,68,68,0.15); color: var(--accent-red); border: 1px solid rgba(239,68,68,0.4); }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
  }
  @media (max-width: 820px) { .grid { grid-template-columns: 1fr; } }
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 20px;
  }
  .card h2 { font-size: 1.05rem; margin-bottom: 14px; color: var(--accent); }
  .stat-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 0.9rem;
  }
  .stat-row span.label { color: var(--muted); }
  .stat-row span.value { font-weight: 600; font-family: monospace; }
  .btn-group {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 12px;
  }
  button {
    background: #1e293b;
    color: var(--text);
    border: 1px solid #334155;
    padding: 9px 14px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.85rem;
    transition: all 0.15s;
  }
  button:hover { background: #334155; border-color: var(--accent); }
  button.primary { background: #0284c7; border-color: #38bdf8; }
  button.primary:hover { background: #0369a1; }
  button.success { background: #15803d; border-color: #22c55e; }
  button.success:hover { background: #166534; }
  button.danger { background: rgba(239,68,68,0.2); border-color: var(--accent-red); color: #fca5a5; }
  button.danger:hover { background: rgba(239,68,68,0.35); }
  select, input {
    background: #0f172a;
    color: var(--text);
    border: 1px solid #334155;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    font-size: 0.85rem;
  }
  th, td {
    text-align: left;
    padding: 10px 8px;
    border-bottom: 1px solid var(--card-border);
  }
  th { color: var(--muted); font-weight: 600; }
  .rtt-good { color: var(--accent-green); font-weight: 600; }
  .tag {
    display: inline-block;
    padding: 2px 7px;
    border-radius: 4px;
    background: rgba(56,189,248,0.15);
    color: var(--accent);
    font-size: 0.75rem;
    font-weight: 700;
  }
  #log-box {
    margin-top: 14px;
    padding: 12px;
    border-radius: 8px;
    background: #090d16;
    border: 1px solid var(--card-border);
    font-family: monospace;
    font-size: 0.82rem;
    color: var(--accent);
    min-height: 48px;
    white-space: pre-wrap;
  }
</style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>[VPN] GuangutVPN Control Center</h1>
      <p>Native Linux Kernel Tunnel (OpenVPN 2.6+ Auto-Patcher) &bull; US Regional &amp; Global Relays</p>
    </div>
    <div id="status-badge" class="badge disconnected">&bull; Checking...</div>
  </header>

  <div class="grid">
    <div class="card">
      <h2>Live Tunnel &amp; Public Exit IP Status</h2>
      <div class="stat-row"><span class="label">Tunnel Interface</span><span class="value" id="st-iface">&mdash;</span></div>
      <div class="stat-row"><span class="label">Public Exit IP</span><span class="value" id="st-ip">&mdash;</span></div>
      <div class="stat-row"><span class="label">Verified Location</span><span class="value" id="st-loc">&mdash;</span></div>
      <div class="stat-row"><span class="label">Exit ISP / Org</span><span class="value" id="st-isp">&mdash;</span></div>
      <div class="stat-row"><span class="label">Connected Relay</span><span class="value" id="st-relay">&mdash;</span></div>
      <div class="btn-group" style="margin-top:16px;">
        <button class="success" onclick="autoConnectBest()">&gt;&gt; Auto-Connect Fastest Filtered Server</button>
        <button onclick="loadStatus()">Refresh Status</button>
        <button class="danger" onclick="disconnectVpn()">[X] Disconnect Tunnel</button>
      </div>
    </div>

    <div class="card">
      <h2>Quick US Regional &amp; Global Filter</h2>
      <p style="font-size:0.83rem;color:var(--muted);margin-bottom:10px;">
        Filter or auto-connect to All-US, Part-of-US (West / Central / East / State), or Global Countries:
      </p>
      <div class="btn-group">
        <button class="primary" onclick="filterServers('US', 'all', '')">[US] All US States</button>
        <button onclick="filterServers('US', 'west', '')">[US-WEST] CA / CO</button>
        <button onclick="filterServers('US', 'central', '')">[US-CENTRAL] TX</button>
        <button onclick="filterServers('US', 'east', '')">[US-EAST] East Coast</button>
      </div>
      <div class="btn-group" style="margin-top:12px;">
        <select id="country-select" onchange="onCountryChange()">
          <option value="US">[US] United States (Default)</option>
          <option value="JP">[JP] Japan</option>
          <option value="KR">[KR] South Korea</option>
          <option value="GB">[GB] United Kingdom</option>
          <option value="DE">[DE] Germany</option>
          <option value="FR">[FR] France</option>
          <option value="TH">[TH] Thailand</option>
          <option value="VN">[VN] Vietnam</option>
          <option value="RO">[RO] Romania</option>
          <option value="ALL">[ALL] All Countries</option>
        </select>
        <input type="text" id="state-input" placeholder="US State (e.g. CA, TX, CO)" style="width:180px;" />
        <button onclick="applyCustomFilter()">Filter List</button>
        <button onclick="probeServers()">Probe Live RTT</button>
      </div>
      <div id="log-box">Ready. Click "Auto-Connect Fastest Filtered Server" or click "Connect" on any row below.</div>
    </div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <h2 id="table-title">Available VPN Relays</h2>
      <button onclick="refreshFeed()">Re-Harvest Live Server Feed</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Country</th>
          <th>US Region</th>
          <th>State / City</th>
          <th>Endpoint (IP:Port)</th>
          <th>Proto</th>
          <th>Live RTT</th>
          <th>Throughput</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="servers-tbody">
        <tr><td colspan="9">Loading servers...</td></tr>
      </tbody>
    </table>
  </div>

<script>
let currentFilter = { country: 'US', us_region: 'all', state: '', probe: '1' };

function setLog(msg) {
  document.getElementById('log-box').textContent = msg;
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const badge = document.getElementById('status-badge');
    if (d.connected) {
      badge.className = 'badge connected';
      badge.textContent = '[ONLINE] CONNECTED (' + (d.tun || 'tun0') + ')';
    } else {
      badge.className = 'badge disconnected';
      badge.textContent = '[OFFLINE] DISCONNECTED';
    }
    document.getElementById('st-iface').textContent = d.tun || (d.has_openvpn ? 'None (Idle)' : 'WARNING: openvpn missing');
    if (d.geo) {
      document.getElementById('st-ip').textContent = d.geo.ip || '—';
      document.getElementById('st-loc').textContent = [d.geo.city, d.geo.region, d.geo.country].filter(Boolean).join(', ');
      document.getElementById('st-isp').textContent = d.geo.isp || '—';
    }
    if (d.meta && d.meta.ip) {
      document.getElementById('st-relay').textContent = d.meta.host + ' (' + d.meta.ip + ':' + d.meta.port + ')';
    } else {
      document.getElementById('st-relay').textContent = '—';
    }
  } catch (e) {
    console.error(e);
  }
}

async function loadServers() {
  const qs = new URLSearchParams(currentFilter).toString();
  setLog('Loading servers (' + qs + ')...');
  try {
    const r = await fetch('/api/servers?' + qs);
    const d = await r.json();
    const tbody = document.getElementById('servers-tbody');
    tbody.innerHTML = '';
    document.getElementById('table-title').textContent =
      `Available VPN Relays (${d.servers.length} shown) ${d.note ? '— ' + d.note : ''}`;
    d.servers.forEach((s, idx) => {
      const tr = document.createElement('tr');
      const rtt = s.live_ms !== null && s.live_ms !== undefined
        ? `<span class="rtt-good">${s.live_ms} ms</span>`
        : (s.ping ? s.ping + ' ms' : '—');
      const loc = [s.state_code || s.region, s.city].filter(Boolean).join(' / ') || s.country;
      const speedMbps = s.speed ? (s.speed / 1000000).toFixed(1) + ' Mbps' : '—';
      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td><span class="tag">${s.cc}</span></td>
        <td>${s.cc === 'US' ? (s.us_region || 'ALL').toUpperCase() : '—'}</td>
        <td>${loc}</td>
        <td><code>${s.ip}:${s.port}</code></td>
        <td>${(s.proto || 'udp').toUpperCase()}</td>
        <td>${rtt}</td>
        <td>${speedMbps}</td>
        <td><button class="primary" onclick="connectIp('${s.ip}', ${s.port}, '${s.proto}')">Connect</button></td>
      `;
      tbody.appendChild(tr);
    });
    setLog(`Loaded ${d.servers.length} servers.${d.note ? ' ' + d.note : ''}`);
  } catch (e) {
    setLog('Error loading servers: ' + e);
  }
}

function filterServers(country, us_region, state) {
  currentFilter = { country, us_region, state, probe: '1' };
  document.getElementById('country-select').value = country;
  document.getElementById('state-input').value = state;
  loadServers();
}

function onCountryChange() {
  const c = document.getElementById('country-select').value;
  currentFilter.country = c;
  currentFilter.us_region = c === 'US' ? 'all' : '';
  currentFilter.state = '';
  loadServers();
}

function applyCustomFilter() {
  currentFilter.country = document.getElementById('country-select').value;
  currentFilter.state = document.getElementById('state-input').value.trim();
  currentFilter.us_region = '';
  loadServers();
}

function probeServers() {
  currentFilter.probe = '1';
  loadServers();
}

async function refreshFeed() {
  setLog('Harvesting live VPN servers & HTTPS GeoIP...');
  const r = await fetch('/api/refresh', { method: 'POST' });
  const d = await r.json();
  setLog(d.message || 'Refreshed!');
  loadServers();
}

async function connectIp(ip, port, proto) {
  setLog(`[Connecting] Negotiating OpenVPN 2.6+ tunnel to ${ip}:${port} (${proto.toUpperCase()}) with auto-failover...`);
  const r = await fetch('/api/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ip,
      port,
      proto,
      country: currentFilter.country,
      us_region: currentFilter.us_region,
      state: currentFilter.state
    })
  });
  const d = await r.json();
  setLog(d.message);
  loadStatus();
}

async function autoConnectBest() {
  setLog(`[Auto-Connect] Probing & connecting to fastest server for ${currentFilter.country} (${currentFilter.us_region || currentFilter.state || 'all'})...`);
  const r = await fetch('/api/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      country: currentFilter.country,
      us_region: currentFilter.us_region,
      state: currentFilter.state
    })
  });
  const d = await r.json();
  setLog(d.message);
  loadStatus();
}

async function disconnectVpn() {
  setLog('Disconnecting VPN tunnel...');
  const r = await fetch('/api/disconnect', { method: 'POST' });
  const d = await r.json();
  setLog(d.message);
  loadStatus();
}

loadStatus();
loadServers();
setInterval(loadStatus, 10000);
</script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            raw = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if parsed.path == "/api/status":
            pid = running_pid()
            tun = get_active_tun_iface()
            has_ovpn, has_wg = check_vpn_binaries()
            geo = fetch_public_ip_geo(timeout=4)
            meta = read_meta() or {}
            self._send_json({
                "connected": bool(pid and tun),
                "pid": pid,
                "tun": tun,
                "has_openvpn": has_ovpn,
                "has_wireguard": has_wg,
                "killswitch": is_killswitch_active(),
                "geo": geo,
                "meta": meta,
            })
            return

        if parsed.path == "/api/servers":
            qs = urllib.parse.parse_qs(parsed.query)
            country = (qs.get("country") or ["US"])[0]
            us_region = (qs.get("us_region") or [""])[0] or None
            state = (qs.get("state") or [""])[0] or None
            do_probe = (qs.get("probe") or ["0"])[0] == "1"

            cache = load_cache()
            if not cache:
                servers = refresh_server_list(enrich=True)
            else:
                servers = cache.get("servers", [])

            filtered, note = filter_servers(
                servers,
                country=country,
                us_region=us_region,
                state=state,
            )
            top = filtered[:30]
            if do_probe and top:
                top = probe_candidates_parallel(top, max_probe=min(15, len(top)))
            clean_list = [{k: v for k, v in s.items() if k != "cfg"} for s in top]
            self._send_json({"servers": clean_list, "note": note})
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/refresh":
            servers = refresh_server_list(enrich=True)
            us_cnt = sum(1 for s in servers if s.get("cc") == "US")
            self._send_json({
                "ok": True,
                "message": f"[OK] Refreshed {len(servers)} total servers ({us_cnt} US servers).",
            })
            return

        if parsed.path == "/api/disconnect":
            ok, msg = disconnect_vpn()
            self._send_json({"ok": ok, "message": msg})
            return

        if parsed.path == "/api/connect":
            has_ovpn, _ = check_vpn_binaries()
            if not has_ovpn:
                self._send_json({
                    "ok": False,
                    "message": "[ERROR] OpenVPN binary not installed yet! Run `sudo ./install.sh` first.",
                })
                return

            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            target_ip = body.get("ip")
            target_port = int(body.get("port") or 0)
            country = body.get("country") or "US"
            us_region = body.get("us_region") or None
            state = body.get("state") or None

            cache = load_cache() or {}
            servers = cache.get("servers", [])
            filtered, _ = filter_servers(servers, country=country, us_region=us_region, state=state)
            filtered = probe_candidates_parallel(filtered, max_probe=10)

            candidates = []
            if target_ip:
                exact = [
                    s for s in servers
                    if s.get("ip") == target_ip and (not target_port or int(s.get("port", 0)) == target_port)
                ]
                others = [s for s in filtered if s not in exact]
                candidates = exact + others
            else:
                candidates = filtered

            if not candidates:
                self._send_json({"ok": False, "message": "[ERROR] No candidate servers found."})
                return

            log_attempts = []
            for idx, srv in enumerate(candidates[:5], 1):
                kill_stale_daemons()
                ok, res = start_openvpn_session(srv, connect_timeout=10)
                if not ok:
                    log_attempts.append(f"Attempt {idx} ({srv.get('ip')}): failed to start daemon ({res})")
                    continue

                ready, tail = wait_for_handshake(int(res), timeout_sec=14)
                if ready:
                    configure_tunnel_dns("tun0")
                    exit_geo = fetch_public_ip_geo(timeout=4)
                    save_meta(srv, exit_info=exit_geo, killswitch=False)
                    loc_str = f"{srv.get('state_code') or srv.get('region') or ''} {srv.get('city') or srv.get('country')}".strip()
                    exit_ip_str = exit_geo.get("ip") if exit_geo else srv.get("ip")
                    self._send_json({
                        "ok": True,
                        "message": f"[CONNECTED] Tunnel up via {srv.get('ip')}:{srv.get('port')} ({loc_str})! Verified Exit IP: {exit_ip_str}",
                    })
                    return
                else:
                    kill_stale_daemons()
                    errs = "; ".join(summarize_failure(tail, max_lines=1))
                    log_attempts.append(f"Attempt {idx} ({srv.get('ip')}:{srv.get('port')}): {errs or 'Timeout'}")

            self._send_json({
                "ok": False,
                "message": "[FAILED] All failover attempts failed:\n" + "\n".join(log_attempts),
            })
            return

        self.send_error(404)


def run_web_gui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://{host}:{port}"
    print(f"[GUI] GuangutVPN Local Web GUI running at: \x1b[1;36m{url}\x1b[0m")
    print("      Click or open the link above in Chrome/Firefox if it doesn't open automatically.")
    print("      Press Ctrl+C to stop the Web GUI server.")

    def _open_as_real_user() -> None:
        su = os.environ.get("SUDO_USER")
        if su and os.geteuid() == 0:
            subprocess.Popen(
                ["sudo", "-u", su, "xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            webbrowser.open(url)

    if open_browser:
        threading.Timer(0.6, _open_as_real_user).start()
    with socketserver.TCPServer((host, port), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping Web GUI server...")
    return 0
