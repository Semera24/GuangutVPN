// GuangutVPN Extension Service Worker (Manifest V3)
// Configures real proxy routing via chrome.proxy and synchronizes with local backend

const BACKEND_URL = "http://127.0.0.1:8765";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    connected: false,
    targetCountry: "US",
    targetState: "",
    selectedServerName: "United States (All / Fastest)",
    activeProxy: null
  });
});

chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "getStatus") {
    handleGetStatus().then(sendResponse);
    return true;
  }
  if (req.action === "getServers") {
    loadBundledServers().then(sendResponse);
    return true;
  }
  if (req.action === "connectServer") {
    handleConnectServer(req.server).then(sendResponse);
    return true;
  }
  if (req.action === "disconnect") {
    handleDisconnect().then(sendResponse);
    return true;
  }
});

async function loadBundledServers() {
  try {
    const url = chrome.runtime.getURL("servers.json");
    const res = await fetch(url);
    return await res.json();
  } catch (e) {
    return [];
  }
}

async function handleGetStatus() {
  const store = await chrome.storage.local.get([
    "connected",
    "targetCountry",
    "targetState",
    "selectedServerName",
    "activeProxy"
  ]);
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

async function handleConnectServer(srv) {
  // If local GuangutVPN backend is running on port 8765, signal it
  try {
    await fetch(`${BACKEND_URL}/api/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ country: srv.country, state: srv.state })
    });
  } catch (e) {}

  try {
    await applyBrowserProxy(srv.host, srv.port, srv.scheme || "socks5");
    await chrome.storage.local.set({
      connected: true,
      targetCountry: srv.country,
      targetState: srv.state || srv.city,
      selectedServerName: srv.name,
      activeProxy: `${srv.scheme.toUpperCase()}://${srv.host}:${srv.port}`
    });
    return {
      ok: true,
      message: `Connected: ${srv.name} (${srv.host}:${srv.port})`
    };
  } catch (err) {
    return { ok: false, message: `Proxy setup error: ${err.message || err}` };
  }
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
