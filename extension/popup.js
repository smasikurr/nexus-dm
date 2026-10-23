/**
 * Nexus DM (NDM) - Popup Logic
 */

document.addEventListener("DOMContentLoaded", async () => {
  const statusChip = document.getElementById("status-chip");
  const mediaList = document.getElementById("media-list");
  const toggleIntercept = document.getElementById("toggle-intercept");
  const toggleFloat = document.getElementById("toggle-float");
  const manualUrlInput = document.getElementById("manual-url");
  const btnQuickDownload = document.getElementById("btn-quick-download");

  // 1. Check Server Status
  chrome.runtime.sendMessage({ action: "check_status" }, (res) => {
    if (res && res.online) {
      statusChip.className = "status-badge status-online";
      statusChip.textContent = "● Online";
    } else {
      statusChip.className = "status-badge status-offline";
      statusChip.textContent = "● Offline";
    }
  });

  // 2. Load Toggles
  chrome.storage.local.get(["autoIntercept", "showFloatingButton"], (res) => {
    toggleIntercept.checked = res.autoIntercept !== false;
    toggleFloat.checked = res.showFloatingButton !== false;
  });

  toggleIntercept.addEventListener("change", () => {
    chrome.storage.local.set({ autoIntercept: toggleIntercept.checked });
  });

  toggleFloat.addEventListener("change", () => {
    chrome.storage.local.set({ showFloatingButton: toggleFloat.checked });
  });

  // 3. Scan Current Tab Media
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTab && activeTab.id) {
    chrome.tabs.sendMessage(activeTab.id, { action: "get_media_streams" }, (response) => {
      if (chrome.runtime.lastError || !response || !response.streams || response.streams.length === 0) {
        // If on YouTube or similar, offer direct page video download
        if (activeTab.url && (activeTab.url.includes("youtube.com") || activeTab.url.includes("youtu.be"))) {
          renderMediaItems([{
            title: activeTab.title || "YouTube Video",
            url: activeTab.url
          }]);
        }
        return;
      }
      renderMediaItems(response.streams);
    });
  }

  function renderMediaItems(streams) {
    if (!streams || streams.length === 0) return;
    mediaList.innerHTML = "";

    streams.forEach(stream => {
      const row = document.createElement("div");
      row.className = "media-item";
      row.innerHTML = `
        <div class="media-title" title="${stream.title}">${stream.title}</div>
        <button class="btn-download-sm">⚡ Download</button>
      `;

      row.querySelector("button").addEventListener("click", () => {
        chrome.runtime.sendMessage({
          action: "download_stream",
          url: stream.url,
          title: stream.title
        });
        row.querySelector("button").textContent = "✓ Sent";
        setTimeout(() => { row.querySelector("button").textContent = "⚡ Download"; }, 2000);
      });

      mediaList.appendChild(row);
    });
  }

  // 4. Quick Download Button
  btnQuickDownload.addEventListener("click", () => {
    const url = manualUrlInput.value.trim();
    if (url) {
      chrome.runtime.sendMessage({
        action: "download_stream",
        url: url
      });
      manualUrlInput.value = "";
      btnQuickDownload.textContent = "✓ Sent";
      setTimeout(() => { btnQuickDownload.textContent = "Send"; }, 1800);
    }
  });
});
