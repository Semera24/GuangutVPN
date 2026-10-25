// GuangutVPN Popup Script

document.addEventListener("DOMContentLoaded", async () => {
  const badge = document.getElementById("conn-badge");
  const extIp = document.getElementById("ext-ip");
  const extLoc = document.getElementById("ext-loc");
  const extMode = document.getElementById("ext-mode");
  const msg = document.getElementById("status-msg");

  const countryPicker = document.getElementById("country-picker");
  const statePicker = document.getElementById("state-picker");

  async function refreshUI() {
    chrome.runtime.sendMessage({ action: "getStatus" }, (res) => {
      if (!res) return;
      if (res.connected) {
        badge.className = "badge connected";
        badge.textContent = "[ONLINE]";
        extMode.textContent = `${res.targetCountry || "US"} (${res.targetRegion || res.targetState || "all"})`;
        if (res.activeProxy) {
          setLog(`Routing via: ${res.activeProxy}`);
        }
      } else {
        badge.className = "badge disconnected";
        badge.textContent = "[OFFLINE]";
        extMode.textContent = "Direct (Unprotected)";
      }
      if (res.ipInfo) {
        extIp.textContent = res.ipInfo.ip;
        extLoc.textContent = `${res.ipInfo.city || ""}, ${res.ipInfo.region || ""}, ${res.ipInfo.country || ""}`;
      }
    });
  }

  function setLog(text) {
    msg.textContent = text;
  }

  // Quick buttons
  document.getElementById("btn-us-all").addEventListener("click", () => {
    countryPicker.value = "US";
    statePicker.value = "";
    triggerConnect("US", "all", "");
  });

  document.getElementById("btn-us-west").addEventListener("click", () => {
    countryPicker.value = "US";
    statePicker.value = "CA";
    triggerConnect("US", "west", "CA");
  });

  document.getElementById("btn-us-central").addEventListener("click", () => {
    countryPicker.value = "US";
    statePicker.value = "TX";
    triggerConnect("US", "central", "TX");
  });

  document.getElementById("btn-connect").addEventListener("click", () => {
    const c = countryPicker.value;
    const s = statePicker.value.trim();
    triggerConnect(c, c === "US" ? "all" : "", s);
  });

  document.getElementById("btn-disconnect").addEventListener("click", () => {
    setLog("Disconnecting...");
    chrome.runtime.sendMessage({ action: "disconnect" }, (res) => {
      setLog(res ? res.message : "Disconnected");
      refreshUI();
    });
  });

  function triggerConnect(country, us_region, state) {
    setLog(`Connecting to ${country} (${us_region || state || "best"})...`);
    chrome.runtime.sendMessage(
      {
        action: "connect",
        params: { country, us_region, state }
      },
      (res) => {
        setLog(res ? res.message : "Connect request sent");
        setTimeout(refreshUI, 1200);
      }
    );
  }

  refreshUI();
});

