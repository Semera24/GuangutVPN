// GuangutVPN Popup Script

document.addEventListener("DOMContentLoaded", async () => {
  const badge = document.getElementById("conn-badge");
  const extIp = document.getElementById("ext-ip");
  const extLoc = document.getElementById("ext-loc");
  const extNode = document.getElementById("ext-node");
  const msg = document.getElementById("status-msg");
  const picker = document.getElementById("server-picker");

  let serverList = [];

  function setLog(text) {
    msg.textContent = text;
  }

  // Load server list from extension
  chrome.runtime.sendMessage({ action: "getServers" }, (servers) => {
    if (Array.isArray(servers) && servers.length) {
      serverList = servers;
      picker.innerHTML = "";
      servers.forEach((s, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        const tag = s.country === "US" ? `[US - ${s.state || s.city}]` : `[${s.country}]`;
        opt.textContent = `${tag} ${s.name} (${s.scheme.toUpperCase()})`;
        picker.appendChild(opt);
      });
    }
  });

  async function refreshUI() {
    chrome.runtime.sendMessage({ action: "getStatus" }, (res) => {
      if (!res) return;
      if (res.connected) {
        badge.className = "badge connected";
        badge.textContent = "[ONLINE]";
        extNode.textContent = res.selectedServerName || res.targetCountry;
        if (res.activeProxy) {
          setLog(`Active: ${res.selectedServerName} (${res.activeProxy})`);
        }
      } else {
        badge.className = "badge disconnected";
        badge.textContent = "[OFFLINE]";
        extNode.textContent = "Direct (Unprotected)";
      }
      if (res.ipInfo) {
        extIp.textContent = res.ipInfo.ip || "—";
        extLoc.textContent = [res.ipInfo.city, res.ipInfo.region, res.ipInfo.country].filter(Boolean).join(", ") || "United States";
      }
    });
  }

  function connectByIndex(idx) {
    const srv = serverList[idx];
    if (!srv) return;
    picker.value = idx;
    setLog(`Connecting to ${srv.name}...`);
    chrome.runtime.sendMessage({ action: "connectServer", server: srv }, (res) => {
      setLog(res ? res.message : "Connected");
      setTimeout(refreshUI, 1000);
      setTimeout(refreshUI, 2500);
    });
  }

  function findServerIndex(stateCode) {
    return serverList.findIndex((s) => s.state === stateCode);
  }

  // Quick State Buttons
  const bindBtn = (id, state) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("click", () => {
        const idx = findServerIndex(state);
        if (idx !== -1) connectByIndex(idx);
      });
    }
  };

  bindBtn("btn-us-ca", "CA");
  bindBtn("btn-us-va", "VA");
  bindBtn("btn-us-wa", "WA");
  bindBtn("btn-us-az", "AZ");
  bindBtn("btn-us-oh", "OH");
  bindBtn("btn-us-fl", "FL");

  document.getElementById("btn-connect").addEventListener("click", () => {
    const idx = parseInt(picker.value, 10);
    if (!isNaN(idx) && serverList[idx]) {
      connectByIndex(idx);
    }
  });

  document.getElementById("btn-disconnect").addEventListener("click", () => {
    setLog("Disconnecting...");
    chrome.runtime.sendMessage({ action: "disconnect" }, (res) => {
      setLog(res ? res.message : "Disconnected");
      setTimeout(refreshUI, 800);
    });
  });

  // Initial render
  refreshUI();
  setInterval(refreshUI, 5000);
});
