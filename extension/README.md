# 🧩 GuangutVPN — Universal Browser Extension (Manifest V3)

The **GuangutVPN Browser Extension** works seamlessly across **every operating system** (macOS M1 Apple Silicon, Intel, Linux, Windows, ChromeOS) on any Chromium-based browser (**Chrome**, **Brave**, **Edge**, **Vivaldi**, **Opera**).

---

## 🌟 Features in the Extension
- **1-Click US Regional Routing**:
  - `[US] All`: Connect to the fastest US server.
  - `[US-West] CA/CO`: Route via California or Colorado.
  - `[US-Central] TX`: Route via Texas.
- **Global Country Selector**: Quick-switch to Japan (`JP`), South Korea (`KR`), United Kingdom (`GB`), Germany (`DE`), France (`FR`), etc.
- **Live Exit IP & GeoIP Detection**: Automatically shows your active public IP and city/state directly inside the popup.
- **Zero Root / Zero Sudo Required**: Operates via standard browser extension proxy controls (`chrome.proxy` API).
- **Dual Mode**: Can interact with your local GuangutVPN backend (`http://127.0.0.1:8765`) or operate independently!

---

## 🚀 How to Install in Chrome / Brave (30 Seconds)

1. Open **Chrome** or **Brave** (on Linux, your Mac M1, or Windows).
2. Go to the Extensions manager page:
   - In Chrome: `chrome://extensions`
   - In Brave: `brave://extensions`
3. Toggle on **Developer mode** (top-right corner switch).
4. Click the **Load unpacked** button in the top-left corner.
5. Select the `extension/` folder inside this repository:
   `/home/yona/Projects/GuangutVPN/extension` (or on Mac: `.../GuangutVPN/extension`).
6. Click the extension puzzle icon in your browser toolbar and pin **GuangutVPN**!

---

## 📁 Extension Structure
```text
extension/
├── manifest.json       # Manifest V3 extension configuration
├── popup.html          # Dark-mode popup UI
├── popup.js            # Popup interactivity & location monitor
├── background.js       # Background service worker & proxy switcher
├── icons/              # Extension icons (16px, 48px, 128px)
└── README.md           # Extension installation guide
```
