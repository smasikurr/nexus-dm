/**
 * Nexus DM (NDM) - Background Service Worker
 * Handles Context Menus, Browser Download Interception, and Local API Communication.
 */

const API_BASE = "http://127.0.0.1:45678";

// Interceptable file extensions
const INTERCEPT_EXTENSIONS = [
  ".zip", ".rar", ".7z", ".tar", ".gz", ".iso",
  ".exe", ".msi", ".apk", ".bin",
  ".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v",
  ".mp3", ".wav", ".flac", ".aac",
  ".pdf", ".epub"
];

// Initialize Context Menus
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "nexus_download_link",
    title: "⚡ Download with Nexus DM",
    contexts: ["link", "image", "video", "audio"]
  });

  chrome.contextMenus.create({
    id: "nexus_download_page_media",
    title: "🎬 Download Page Video with Nexus DM",
    contexts: ["page"]
  });

  // Default settings
  chrome.storage.local.get(["autoIntercept", "showFloatingButton"], (res) => {
    if (res.autoIntercept === undefined) {
      chrome.storage.local.set({ autoIntercept: true });
    }
    if (res.showFloatingButton === undefined) {
      chrome.storage.local.set({ showFloatingButton: true });
    }
  });
});

// Handle Context Menu Clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  let targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;

  if (info.menuItemId === "nexus_download_link" && targetUrl) {
    sendToNexusDM({
      url: targetUrl,
      referer: tab ? tab.url : "",
      user_agent: navigator.userAgent
    });
  } else if (info.menuItemId === "nexus_download_page_media" && tab) {
    chrome.tabs.sendMessage(tab.id, { action: "get_media_streams" }, (response) => {
      if (response && response.streams && response.streams.length > 0) {
        sendToNexusDM({
          url: response.streams[0].url,
          filename: response.streams[0].title,
          referer: tab.url,
          user_agent: navigator.userAgent
        });
      } else {
        // Fallback to page URL (e.g. YouTube video URL handled by engine's yt-dlp)
        sendToNexusDM({
          url: tab.url,
          referer: tab.url,
          user_agent: navigator.userAgent
        });
      }
    });
  }
});

// Intercept Browser Downloads (if enabled)
chrome.downloads.onCreated.addListener(async (downloadItem) => {
  const { autoIntercept } = await chrome.storage.local.get(["autoIntercept"]);
  if (!autoIntercept) return;

  const url = downloadItem.finalUrl || downloadItem.url;
  if (!url || url.startsWith("blob:") || url.startsWith("data:")) return;

  const urlLower = url.toLowerCase();
  const filename = downloadItem.filename ? downloadItem.filename.toLowerCase() : "";

  const shouldIntercept = INTERCEPT_EXTENSIONS.some(ext => 
    urlLower.endsWith(ext) || urlLower.includes(ext + "?") || filename.endsWith(ext)
  );

  if (shouldIntercept) {
    // Check if Nexus DM desktop server is online
    const isOnline = await checkServerStatus();
    if (isOnline) {
      chrome.downloads.cancel(downloadItem.id, () => {
        chrome.downloads.erase({ id: downloadItem.id });
      });

      sendToNexusDM({
        url: url,
        filename: downloadItem.filename || "",
        referer: downloadItem.referrer || "",
        user_agent: navigator.userAgent
      });
    }
  }
});

// Check Server Status
async function checkServerStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/ping`, { method: "GET" });
    const data = await res.json();
    return data && data.status === "ok";
  } catch (err) {
    return false;
  }
}

// Send Download Payload to Nexus DM Desktop App
async function sendToNexusDM(payload) {
  try {
    const res = await fetch(`${API_BASE}/api/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.success) {
      notify("Nexus DM", `Download started: ${data.filename || 'File'}`);
    } else {
      notify("Nexus DM Error", data.error || "Failed to start download");
    }
  } catch (err) {
    notify("Nexus DM Offline", "Desktop app is not running. Please launch Nexus DM on your PC.");
  }
}

// Notification Helper
function notify(title, message) {
  console.log(`[Nexus DM] ${title}: ${message}`);
}

// Message Dispatcher from Content Script & Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "download_stream") {
    sendToNexusDM({
      url: request.url,
      filename: request.title || "",
      referer: sender.tab ? sender.tab.url : "",
      user_agent: navigator.userAgent
    });
    sendResponse({ status: "sent" });
  } else if (request.action === "check_status") {
    checkServerStatus().then(online => {
      sendResponse({ online: online });
    });
    return true; // Keep message channel open for async response
  }
});
