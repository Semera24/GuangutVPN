# 🛡️ GuangutVPN

**GuangutVPN** is a self-hosted, 100% free and open-source Linux kernel VPN system, US Regional/State GeoIP Harvester, and Automated OpenVPN 2.6+ / WireGuard Patcher built for **Debian GNU/Linux 13 (Trixie)** and modern Linux desktop environments (Xfce, GNOME, KDE).

GuangutVPN combines the performance and security features of the top commercial VPN services (NordVPN, ExpressVPN, ProtonVPN) into a self-contained Linux client with **no subscription fees, no accounts, and zero logging**.

---

## 🏆 Commercial VPN Features vs. GuangutVPN

| Commercial Feature (Nord / Proton / Express) | GuangutVPN Implementation | Location in Codebase |
| :--- | :--- | :--- |
| **Layer-3 Kernel Tunneling** | Native OpenVPN 2.6+ (`tun0`) and WireGuard (`wg0`) | [`guangut/tunnel.py`](guangut/tunnel.py), [`guangut/wireguard.py`](guangut/wireguard.py) |
| **All-US & US Regional Targeting** | Multi-threaded GeoIP classifier: US-West, US-Central, US-East + 50 states | [`guangut/regions.py`](guangut/regions.py), [`guangut/harvester.py`](guangut/harvester.py) |
| **Global Country Expansion** | 15+ countries (`JP`, `KR`, `GB`, `DE`, `FR`, `TH`, `VN`, `RO`, etc.) | [`guangut/harvester.py`](guangut/harvester.py) |
| **NetShield / CleanWeb Ad Blocker** | **GuangutShield**: Zero-latency DNS ad & tracker blocker (1-click toggle) | [`guangut/adblock.py`](guangut/adblock.py) |
| **Automatic Watchdog & Failover** | Background daemon supervising tunnel health with auto-recovery | [`guangut/watchdog.py`](guangut/watchdog.py) |
| **Firewall Kill Switch** | Kernel `nftables` output filter dropping all unencrypted non-tunnel packets | [`guangut/security.py`](guangut/security.py) |
| **DNS Leak Guard** | Automated `systemd-resolved` interface binding (`resolvectl`) + `/etc/resolv.conf` lock | [`guangut/security.py`](guangut/security.py) |
| **System Tray Status Pill** | Native GTK3 taskbar applet with dynamic icon and right-click quick connect | [`guangut/tray.py`](guangut/tray.py) |
| **Local Web Control Center** | Zero-dependency dark-mode Web GUI dashboard (`http://127.0.0.1:8765`) | [`guangut/gui.py`](guangut/gui.py) |
| **Dynamic Credentials Scraper** | Live password scraping from high-speed sources (e.g. VPNBook US) | [`guangut/sources.py`](guangut/sources.py) |
| **Split-Tunneling Browser Mode** | Dedicated browser runner routing directly through the active VPN exit | [`guangut/splittunnel.py`](guangut/splittunnel.py) |

---

## 🚀 Quick Start: Installation

Run the automated installer script in your terminal (elevates with `sudo` to configure system binaries, desktop icon, and passwordless tunnel permissions):

```bash
cd /home/yona/Projects/GuangutVPN
sudo ./install.sh
```

---

## 💻 How to Use GuangutVPN

### 1. Launch from Desktop (Xfce / Applications Menu)
- Open your Application Finder or Menu $\rightarrow$ Search **GuangutVPN** $\rightarrow$ Click to launch the Web GUI Control Center directly in your browser (`http://127.0.0.1:8765`).

### 2. Connect via CLI (All-US or Part-of-US)
```bash
# Connect to fastest US server (All-US socket probe)
sudo guangut connect

# Connect to a specific US Region
sudo guangut connect --us-region west      # California / Colorado / West Coast
sudo guangut connect --us-region central   # Texas / Central US
sudo guangut connect --us-region east      # East Coast

# Connect to a specific US State
sudo guangut connect --state CA
sudo guangut connect --state TX
sudo guangut connect --state CO

# Connect with Kernel nftables Kill Switch enabled
sudo guangut connect --us-region west --killswitch
```

### 3. Connect to Other Countries (Global Mode)
```bash
# List all available countries and server counts
guangut list --countries

# Connect to specific countries
sudo guangut connect --country JP          # Japan
sudo guangut connect --country KR          # South Korea
sudo guangut connect --country GB          # United Kingdom
sudo guangut connect --country DE          # Germany
```

### 4. Commercial Features: AdBlock, Watchdog & System Tray
```bash
# Enable / Toggle GuangutShield DNS Ad & Tracker Blocker
sudo guangut adblock
sudo guangut adblock --disable

# Launch the Health Watchdog & Auto-Failover Daemon
sudo guangut watch --country US --us-region west &

# Launch Desktop System Tray Status Pill (GTK3 panel applet)
guangut tray &

# Launch dedicated browser instance through the VPN
guangut browser --url https://ipinfo.io
```

### 5. Check Status or Disconnect
```bash
# View tunnel interface (tun0), PID, and verified exit IP/Location
guangut status

# Disconnect VPN and restore system DNS & firewall
sudo guangut disconnect
```

---

## 📁 Repository Architecture

```text
GuangutVPN/
├── guangut/                     # Core VPN Engine
│   ├── adblock.py               # GuangutShield DNS ad & malware blocker
│   ├── cli.py                   # CLI parser & interactive terminal dashboard
│   ├── gui.py                   # Local Web GUI dashboard server (port 8765)
│   ├── harvester.py             # Multi-source server harvester & socket prober
│   ├── patcher.py               # OpenVPN 2.6+ reverse-engineering config patcher
│   ├── regions.py               # US State/Region classifier & Haversine distance
│   ├── security.py              # nftables Kill Switch & DNS Leak Guard
│   ├── sources.py               # High-speed dynamic scrapers (VPNBook US)
│   ├── splittunnel.py           # Split-tunneling & dedicated browser launcher
│   ├── tray.py                  # GTK3 Desktop System Tray applet
│   ├── tunnel.py                # OpenVPN daemon lifecycle & GeoIP verifier
│   ├── watchdog.py              # Auto-reconnect health watchdog daemon
│   └── wireguard.py             # WireGuard (wg0) kernel tunnel controller
├── configs/                     # Pre-exported patched US profiles (CA, TX, CO)
├── install.sh                   # System installer & launcher configurator
├── guangutvpn-gui-wrapper.sh    # Non-blocking desktop GUI launcher
├── guangutvpn.desktop           # Freedesktop / Xfce application launcher
├── guangutvpn.svg               # Application vector icon
├── test_guangut.py              # Automated unit test suite
├── vpnPlan.md                   # System architecture specification
└── vpnPlanRoadMap.md            # Detailed engineering roadmap
```
