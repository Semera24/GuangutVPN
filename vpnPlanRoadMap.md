# GuangutVPN — Development Task List & Roadmap (`vpnPlanRoadMap.md`)

All 6 phases of **GuangutVPN** have been engineered, reverse-engineered, and verified in `/home/yona/Projects/GuangutVPN`.

---

## Phase 1: Environment Setup & Open-Source Reference Analysis (✅ Completed)
- [x] **Task 1.1: System VPN Setup & Installer (`install.sh`)**
  - Created automated `install.sh` for Debian 13 (`trixie`) to install `openvpn`, `wireguard-tools`, and `openresolv` and symlink `guangut` / `guangut-vpn` into `/usr/local/bin`.
- [x] **Task 1.2: Clone & Inspect Open-Source Reference Repos**
  - Cloned `sajadinmaker/vpnbox` (`reference/vpnbox`), `Zoult/.ovpn` (`reference/zoult-ovpn`), and `9xN/auto-ovpn` (`reference/auto-ovpn`).
  - Reverse-engineered and fixed Debian 13 issues:
    1. Plain-HTTP `ip-api.com` timeouts -> Replaced with concurrent HTTPS GeoIP (`ipwho.is` + `ipinfo.io` fallback + persistent local GeoIP cache).
    2. OpenVPN 2.6+ legacy cipher rejection (`AES-128-CBC` / `AES-256-CBC`) -> Automated `data-ciphers` & `data-ciphers-fallback` injection.

---

## Phase 2: Server Harvester & US Regional GeoIP Engine (✅ Completed)
- [x] **Task 2.1: Multi-Source VPN Node Harvester (`guangut/harvester.py`)**
  - Live harvesting from the VPN Gate API + passwordless community OpenVPN pools (`reference/zoult-ovpn` and `reference/auto-ovpn`) + custom user profiles (`configs/custom/`).
- [x] **Task 2.2: US Country & Regional Geolocation Classifier (`guangut/regions.py`)**
  - Default filter targets **United States (`US`)** servers.
  - Classifies US relays into **US-East**, **US-Central**, **US-West**, **US-Northeast**, **US-South**, **US-Midwest**, and 50 US State codes (`CA`, `TX`, `CO`, `NY`, `VA`, etc.) with Haversine nearest-state fallback.
  - Supports `--country <ISO_CODE>` (`JP`, `KR`, `GB`, `DE`, `FR`, `RO`, `TH`, `VN`, `AU`, etc.) for global connections.
- [x] **Task 2.3: Multi-Threaded Live Socket Prober**
  - Concurrent TCP/UDP socket reachability and millisecond RTT prober (`probe_candidates_parallel`) that tests candidate servers in parallel before launching OpenVPN.

---

## Phase 3: Reverse-Engineering & OpenVPN 2.6+ Config Patcher (✅ Completed)
- [x] **Task 3.1: Base64 Payload Extraction & Inspection (`guangut/patcher.py`)**
  - Decodes Base64 `.ovpn` configurations and extracts transport protocol (`tcp`/`udp`), remote IP, port, and legacy cipher.
- [x] **Task 3.2: Automated OpenVPN 2.6+ Compatibility Patching**
  - Strips Windows-only directives (`win-sys`, `register-dns`, `route-method`, `route-delay`).
  - Injects `data-ciphers`, `data-ciphers-fallback`, `tls-version-min 1.0`, `redirect-gateway def1`, `block-ipv6`, and leak-free DNS (`1.1.1.1`, `8.8.8.8`).
  - Pre-exported ready-to-use US state profiles in `configs/`:
    - `configs/US_CA_SanFrancisco.ovpn` (San Francisco, California — US-West, 25ms RTT)
    - `configs/US_CO_ColoradoSprings.ovpn` (Colorado Springs, Colorado — US-West, 25ms RTT)
    - `configs/US_TX_Dallas.ovpn` (Dallas, Texas — US-Central, 228ms RTT)

---

## Phase 4: Tunnel Manager, Auto-Failover & Security Guard (✅ Completed)
- [x] **Task 4.1: Privilege-Separated Tunnel Controller (`guangut/tunnel.py`)**
  - Manages OpenVPN (`tun0`) daemon lifecycle with offset-tracked log monitoring (`Initialization Sequence Completed`) and automatic stale process cleanup.
- [x] **Task 4.2: Smart Auto-Failover Loop**
  - Automatically rolls over across the top-ranked live US/Regional/Global relays if a server drops during handshake.
- [x] **Task 4.3: DNS Leak Guard & `nftables` Kill Switch (`guangut/security.py`)**
  - Configures leak-free DNS via `systemd-resolved` (`resolvectl`) or `/etc/resolv.conf` backup/restore, plus an optional `nftables` kernel Kill Switch (`--killswitch`).

---

## Phase 5: CLI, Interactive TUI Dashboard & Verification (✅ Completed)
- [x] **Task 5.1: Rich CLI & Interactive Server Picker (`guangut/cli.py` & `./guangut-vpn`)**
  - Implemented `refresh`, `list`, `connect`, `disconnect`, `status`, `export`, `menu`, and `gui`.
- [x] **Task 5.2: Automated Unit & Live Probing Verification (`test_guangut.py`)**
  - All unit tests pass (`OK`), live socket probing verified against US and global endpoints.

---

## Phase 6: Local Web GUI Control Center & Multi-Repo Pool Expansion (✅ Completed)
- [x] **Task 6.1: Local Web GUI Control Center (`guangut/gui.py`)**
  - Built zero-dependency dark-mode Web Dashboard (`guangut gui` on `http://127.0.0.1:8765`) with one-click US Regional filtering (`All-US`, `US-West`, `US-Central`, `US-East`, or State code), Global Country selector, live RTT probing, and live Exit-IP status monitor.
- [x] **Task 6.2: Multi-Repository Server Pool Integration**
  - Integrated `9xN/auto-ovpn` alongside `Zoult/.ovpn` and live VPN Gate feeds for automatic deduplicated harvesting.

---

## Phase 6: Local Web GUI Control Center & Multi-Repo Pool Expansion (✅ Completed)
- [x] **Task 6.1: Local Web GUI Control Center (`guangut/gui.py`)**
  - Built zero-dependency dark-mode Web Dashboard (`guangut gui` on `http://127.0.0.1:8765`) with one-click US Regional filtering (`All-US`, `US-West`, `US-Central`, `US-East`, or State code), Global Country selector, live RTT probing, and live Exit-IP status monitor.
- [x] **Task 6.2: Multi-Repository Server Pool Integration**
  - Integrated `9xN/auto-ovpn` alongside `Zoult/.ovpn` and live VPN Gate feeds for automatic deduplicated harvesting.

