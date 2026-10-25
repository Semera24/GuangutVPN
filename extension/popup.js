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
        opt.textContent = `${tag} ${s.name}`;
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
        extIp.textContent = res.ipInfo.ip;
        extLoc.textContent = [res.ipInfo.city, res.ipInfo.region, res.ipInfo.country].filter(Boolean).join(", ");
      }
    });
  }

  function connectByIndex(idx) {
    const srv = serverList[idx];
    if (!srv) return;
    picker.value = idx;
    setLog(`Connecting to ${srv.name}...`);
    chrome.runtime.sendMessage({ action: "connectServer", server: srv }, (res) => {
      setLog(res ? res.message : "Connecting...");
      setTimeout(refreshUI, 1500);
    });
  }

  function findServerIndex(stateCode) {
    return serverList.findIndex((s) => s.state === stateCode);
  }

  // Quick State Buttons
  document.getElementById("btn-us-ca").addEventListener("click", () => {
    const idx = findServerIndex("CA");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-us-ny").addEventListener("click", () => {
    const idx = findServerIndex("NY");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-us-va").addEventListener("click", () => {
    const idx = findServerIndex("VA");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-us-tx").addEventListener("click", () => {
    const idx = findServerIndex("TX");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-us-il").addEventListener("click", () => {
    const idx = findServerIndex("IL");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-us-nj").addEventListener("click", () => {
    const idx = findServerIndex("NJ");
    if (idx !== -1) connectByIndex(idx);
  });

  document.getElementById("btn-connect").addEventListener("click", () => {
    const idx = parseInt(picker.value, 10);
    if (!isNaN(idx)) {
      connectByIndex(idx);
    }
  });

  document.getElementById("btn-disconnect").addEventListener("click", () => {
    setLog("Disconnecting...");
    chrome.runtime.sendMessage({ action: "disconnect" }, (res) => {
      setLog(res ? res.message : "Disconnected");
      refreshUI();
    });
  });

  refreshUI();
});
