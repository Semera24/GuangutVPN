// GuangutVPN Extension Service Worker (Manifest V3)
// Configures real proxy routing via chrome.proxy and synchronizes with local backend

const BACKEND_URL = "http://127.0.0.1:8765";
const PROXY_LIST_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies.json";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    connected: false,
    targetCountry: "US",
    targetRegion: "all",
    targetState: "",
    activeProxy: null
  });
});

chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "getStatus") {
    handleGetStatus().then(sendResponse);
    return true;
  }
  if (req.action === "connect") {
    handleConnect(req.params).then(sendResponse);
    return true;
  }
  if (req.action === "disconnect") {
    handleDisconnect().then(sendResponse);
    return true;
  }
});

async function handleGetStatus() {
  const store = await chrome.storage.local.get(["connected", "targetCountry", "targetRegion", "targetState", "activeProxy"]);
  let ipInfo = null;
  try {
    const res = await fetch("https://ipwho.is/", { cache: "no-store" });
    const data = await res.json();
    if (data && data.success) {
      ipInfo = {
        ip: data.ip,
        city: data.city,
        region: data.region,
        country: data.country
      };
    }
  } catch (e) {}
  return { ...store, ipInfo };
}

function applyBrowserProxy(host, port, scheme = "socks5") {
  return new Promise((resolve, reject) => {
    const config = {
      mode: "fixed_servers",
      rules: {
        singleProxy: {
          scheme: scheme,
          host: host,
          port: parseInt(port, 10)
        },
        bypassList: ["<local>", "127.0.0.1", "localhost", "192.168.0.0/16", "10.0.0.0/8"]
      }
    };
    chrome.proxy.settings.set({ value: config, scope: "regular" }, () => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}

async function fetchCandidateProxy(country = "US", region = "all", state = "") {
  try {
    const res = await fetch(PROXY_LIST_URL, { cache: "no-store" });
    const list = await res.json();
    if (Array.isArray(list)) {
      // Filter by country (e.g. US)
      let matched = list.filter(p => {
        const cCode = p.geolocation?.country?.iso_code;
        return cCode && cCode.toUpperCase() === country.toUpperCase();
      });

      if (!matched.length && country !== "US") {
        matched = list.filter(p => p.geolocation?.country?.iso_code === "US");
      }

      // Filter by state if provided
      if (state && state.trim()) {
        const stLower = state.toLowerCase().trim();
        const stateMatched = matched.filter(p => {
          const cName = (p.geolocation?.city?.names?.en || "").toLowerCase();
          return cName.includes(stLower);
        });
        if (stateMatched.length) matched = stateMatched;
      }

      // Prefer SOCKS5 or HTTPS
      matched.sort((a, b) => {
        const score = (p) => (p.protocol === "socks5" ? 3 : p.protocol === "https" ? 2 : p.protocol === "http" ? 1 : 0);
        return score(b) - score(a);
      });

      if (matched.length) {
        const p = matched[0];
        const scheme = p.protocol === "socks4" ? "socks4" : p.protocol === "socks5" ? "socks5" : "http";
        return {
          host: p.host,
          port: p.port,
          scheme: scheme,
          city: p.geolocation?.city?.names?.en || country
        };
      }
    }
  } catch (e) {}
  return null;
}

async function handleConnect(params) {
  const country = params.country || "US";
  const region = params.us_region || "all";
  const state = params.state || "";

  // 1. Try local GuangutVPN daemon on port 8765 first if running
  try {
    const res = await fetch(`${BACKEND_URL}/api/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params)
    });
    const data = await res.json();
    if (data && data.ok) {
      await chrome.storage.local.set({
        connected: true,
        targetCountry: country,
        targetRegion: region,
        targetState: state,
        activeProxy: "Local Daemon (tun0)"
      });
      return { ok: true, message: `Connected via Local Daemon: ${data.message}` };
    }
  } catch (e) {}

  // 2. Standalone Browser Extension Mode: apply real cloud proxy into chrome.proxy
  const candidate = await fetchCandidateProxy(country, region, state);
  if (candidate) {
    try {
      await applyBrowserProxy(candidate.host, candidate.port, candidate.scheme);
      await chrome.storage.local.set({
        connected: true,
        targetCountry: country,
        targetRegion: region,
        targetState: state,
        activeProxy: `${candidate.scheme}://${candidate.host}:${candidate.port}`
      });
      return {
        ok: true,
        message: `Connected: ${candidate.scheme.toUpperCase()}://${candidate.host}:${candidate.port} (${candidate.city})`
      };
    } catch (err) {
      return { ok: false, message: `Proxy setup error: ${err.message || err}` };
    }
  }

  return { ok: false, message: "No live proxy relays reachable right now. Try again." };
}

async function handleDisconnect() {
  try {
    await fetch(`${BACKEND_URL}/api/disconnect`, { method: "POST" });
  } catch (e) {}

  await new Promise((resolve) => {
    chrome.proxy.settings.clear({ scope: "regular" }, resolve);
  });

  await chrome.storage.local.set({
    connected: false,
    activeProxy: null
  });
  return { ok: true, message: "Disconnected (Direct route restored)." };
}
