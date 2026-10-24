# 🛡️ GuangutVPN

**GuangutVPN** is a native Linux Kernel VPN client, US Regional/State GeoIP Harvester, and Automated OpenVPN 2.6+ Configuration Patcher built for **Debian GNU/Linux 13 (Trixie)**.

---

## ✨ Key Features

1. **🇺🇸 All-US & Part-of-US (Region / State) Targeting**:
   - **All-US (`--us-region all`)**: Concurrent socket probing across all United States servers to pick the fastest live relay.
   - **Part-of-US (`--us-region west|central|east|south|northeast|midwest`)**: Route specifically through US-West (`CA`, `CO`, `WA`, `OR`), US-Central (`TX`, `IL`), or US-East (`NY`, `VA`, `FL`, `DC`).
   - **Specific US State (`--state CA`, `--state TX`, `--state CO`)**: Target individual US states with automatic nearest-state Haversine distance fallback.
2. **🌐 Global Country Option (`--country <CODE>`)**:
   - Switch to **15+ other countries** (`JP`, `KR`, `GB`, `DE`, `FR`, `TH`, `VN`, `RO`, `RU`, `AU`, `IN`, `AE`, etc.) anytime.
3. **🔧 Reverse-Engineered OpenVPN 2.6+ Auto-Patcher (`guangut/patcher.py`)**:
   - Automatically strips Windows-only directives (`win-sys`, `register-dns`) and injects `data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC:AES-128-CBC`, `data-ciphers-fallback`, `tls-version-min 1.0`, `redirect-gateway def1`, `block-ipv6`, and leak-free DNS (`1.1.1.1`, `8.8.8.8`).
4. **🖥️ 3 Ways to Use It**:
   - **Rich CLI** (`guangut connect`, `guangut list`, `guangut status`, `guangut disconnect`)
   - **Interactive Terminal Dashboard** (`guangut` or `guangut menu`)
   - **Local Web GUI Control Center** (`guangut gui` -> opens `http://127.0.0.1:8765`)

---

## 🚀 Step 1: One-Time System Package Installation

Run the installer script in your terminal (it will prompt for your `sudo` password to install `openvpn`, `wireguard-tools`, and `openresolv`, and link `guangut` to `/usr/local/bin`):

```bash
cd /home/yona/Projects/GuangutVPN
sudo ./install.sh
```

---

## 💻 Step 2: Usage Examples

### A. Connect to United States (All-US or Part-of-US)
```bash
# Connect to the fastest US server (All-US)
sudo guangut connect

# Connect to US-West (California / Colorado / West Coast)
sudo guangut connect --us-region west

# Connect to US-Central (Texas / Central US)
sudo guangut connect --us-region central

# Connect to a specific US State (e.g., California, Colorado, Texas)
sudo guangut connect --state CA
sudo guangut connect --state CO
sudo guangut connect --state TX

# Connect with Kernel nftables Kill Switch enabled
sudo guangut connect --us-region west --killswitch
```

### B. Connect to Other Countries (Global Option)
```bash
# List all available countries and server counts
guangut list --countries

# Connect to Japan, South Korea, UK, Germany, France, etc.
sudo guangut connect --country JP
sudo guangut connect --country KR
sudo guangut connect --country GB
sudo guangut connect --country DE
```

### C. Check Status, Launch Web GUI, or Disconnect
```bash
# Check tunnel interface (tun0), uptime, and verified public exit IP
guangut status

# Launch the interactive Terminal Dashboard
guangut menu

# Launch the Local Web GUI Dashboard in your browser (http://127.0.0.1:8765)
sudo guangut gui

# Disconnect VPN and restore system DNS & firewall
sudo guangut disconnect
```

