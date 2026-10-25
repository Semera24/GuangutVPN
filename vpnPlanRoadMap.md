# 🗺️ GuangutVPN — Engineering Roadmap & Completed Feature Matrix (`vpnPlanRoadMap.md`)

All architectural and commercial-grade feature phases of **GuangutVPN** have been engineered, reverse-engineered, and verified.

---

## Phase 1: Environment Setup & Open-Source Reference Analysis (✅ Completed)
- [x] **Task 1.1: System VPN Setup & Installer (`install.sh`)**
  - Automated installer for Debian 13 (`trixie`) configuring `openvpn`, `wireguard-tools`, `openresolv`, and linking `guangut` into `/usr/bin` and `/usr/local/bin`.
- [x] **Task 1.2: Reference Architecture Extraction**
  - Cloned and analyzed `sajadinmaker/vpnbox`, `Zoult/.ovpn`, and `9xN/auto-ovpn`.
  - Resolved Debian 13 legacy cipher incompatibility and plain-HTTP GeoIP timeout bottlenecks.

---

## Phase 2: Server Harvester & US Regional GeoIP Engine (✅ Completed)
- [x] **Task 2.1: Multi-Source VPN Node Harvester (`guangut/harvester.py`)**
  - Live harvesting across VPN Gate API, community `.ovpn` pools, and custom configs.
- [x] **Task 2.2: US Country & Regional Geolocation Classifier (`guangut/regions.py`)**
  - Default filter targets **United States (`US`)** servers.
  - Classifies US relays into **US-East**, **US-Central**, **US-West**, **US-Northeast**, **US-South**, **US-Midwest**, and all 50 US State codes with Haversine distance fallback.
  - Global country support (`JP`, `KR`, `GB`, `DE`, `FR`, `RO`, `TH`, `VN`, `AU`, etc.).
- [x] **Task 2.3: Parallel Socket Latency Prober**
  - Concurrent socket handshake checking (`probe_candidates_parallel`) measuring real latency before starting OpenVPN.

---

## Phase 3: Reverse-Engineering & OpenVPN 2.6+ Config Patcher (✅ Completed)
- [x] **Task 3.1: Base64 Payload Extraction & Inspection (`guangut/patcher.py`)**
  - Decodes `.ovpn` payloads, extracts protocol (`tcp`/`udp`), remote IP, port, and cipher types.
- [x] **Task 3.2: Automated Compatibility Patching**
  - Strips Windows directives (`win-sys`, `register-dns`, `route-method`).
  - Injects `data-ciphers`, `data-ciphers-fallback`, `tls-version-min 1.0`, `auth-user-pass /tmp/guangutvpn-auth.txt`, `redirect-gateway def1`, and `block-ipv6`.
  - Pre-exported ready-to-use profiles in `configs/`:
    - `configs/US_CA_SanFrancisco.ovpn` (US-West, 25ms RTT)
    - `configs/US_CO_ColoradoSprings.ovpn` (US-West, 25ms RTT)
    - `configs/US_TX_Dallas.ovpn` (US-Central, 30ms RTT)

---

## Phase 4: Tunnel Manager, Auto-Failover & Security Layer (✅ Completed)
- [x] **Task 4.1: Privilege-Separated Tunnel Controller (`guangut/tunnel.py`)**
  - Manages `tun0` daemon lifecycle with offset log monitoring (`Initialization Sequence Completed`).
- [x] **Task 4.2: Smart Auto-Failover Loop**
  - Rolls over across top-ranked candidate relays if an individual node times out or drops.
- [x] **Task 4.3: DNS Leak Guard & `nftables` Kill Switch (`guangut/security.py`)**
  - Automatic `systemd-resolved` DNS pinning and optional `nftables` Kill Switch dropping non-VPN outbound packets.

---

## Phase 5: CLI, TUI Dashboard & Live Verification (✅ Completed)
- [x] **Task 5.1: Command Line & Interactive Menu (`guangut/cli.py`)**
  - Implemented `connect`, `disconnect`, `status`, `list`, `refresh`, `export`, and `menu`.
- [x] **Task 5.2: Unit Test Suite & Verification (`test_guangut.py`)**
  - All unit tests pass with 100% success.
  - Live connection verified active via Dallas, TX (`72.180.13.9:1276`).

---

## Phase 6: Commercial-Grade Feature Expansion (✅ Completed)
- [x] **Task 6.1: Local Web GUI Control Center (`guangut/gui.py`)**
  - Dark-mode dashboard (`http://127.0.0.1:8765`) with font-safe labels, 1-click US regional filtering, live RTT probing, and real-time public exit IP monitoring.
- [x] **Task 6.2: Auto-Reconnect Watchdog Daemon (`guangut/watchdog.py`)**
  - Background supervisor verifying `tun0` interface health and ICMP reachability every 5 seconds, auto-reconnecting on tunnel drops.
- [x] **Task 6.3: High-Speed VPNBook US Scraper (`guangut/sources.py`)**
  - Dynamic scraping of fresh US1/US2 profiles and real-time password synchronization.
- [x] **Task 6.4: Native WireGuard (wg0) Controller (`guangut/wireguard.py`)**
  - Full kernel-level WireGuard management via `wg-quick` for sub-second handshakes and gigabit throughput.
- [x] **Task 6.5: GuangutShield Zero-Latency DNS Ad & Malware Blocker (`guangut/adblock.py`)**
  - NetShield/CleanWeb equivalent dropping ads, trackers, and telemetry at the DNS level with a 1-click GUI toggle.
- [x] **Task 6.6: Desktop Application Launcher & GUI Wrapper (`guangutvpn-gui-wrapper.sh`)**
  - Smooth background daemonization preventing terminal blinking on Xfce/Freedesktop menus.
- [x] **Task 6.7: GTK3 Desktop System Tray Status Pill (`guangut/tray.py`)**
  - Taskbar applet with dynamic green/red connection status and right-click quick connect menus.
- [x] **Task 6.8: Split-Tunneling Browser Mode (`guangut/splittunnel.py`)**
  - Direct browser invocation through the active VPN exit node.
