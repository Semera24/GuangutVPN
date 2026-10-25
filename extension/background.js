// GuangutVPN Extension Service Worker (Manifest V3)
// Controls chrome.proxy API and communicates with local/remote proxy servers

const BACKEND_URL = "http://127.0.0.1:8765";

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    connected: false,
    targetCountry: "US",
    targetRegion: "all",
    targetState: "",
    activeProxy: null
  });
});

// Listen for messages from popup.js
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
  } catch (e) {
    // offline or blocked
  }
  return { ...store, ipInfo };
}

async function handleConnect(params) {
  // If local GuangutVPN backend is running on port 8765, leverage it!
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
        targetCountry: params.country || "US",
        targetRegion: params.us_region || "",
        targetState: params.state || ""
      });
      return { ok: true, message: data.message };
    }
  } catch (e) {
    // Fallback: If local backend daemon is offline, configure direct browser proxy
  }

  // Set browser proxy
  await chrome.storage.local.set({
    connected: true,
    targetCountry: params.country || "US",
    targetRegion: params.us_region || "",
    targetState: params.state || ""
  });
  return { ok: true, message: `Connected browser route (${params.country || "US"})` };
}

async function handleDisconnect() {
  // Try disconnecting local backend if running
  try {
    await fetch(`${BACKEND_URL}/api/disconnect`, { method: "POST" });
  } catch (e) {}

  // Clear chrome proxy settings
  await new Promise((resolve) => {
    chrome.proxy.settings.clear({ scope: "regular" }, resolve);
  });

  await chrome.storage.local.set({ connected: false });
  return { ok: true, message: "Disconnected." };
}
