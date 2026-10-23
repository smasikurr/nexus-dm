/**
 * Nexus DM (NDM) - Content Script
 * Video & Audio Sniffer with Floating "Download with Nexus DM" Button.
 */

(function () {
  let detectedMedia = [];

  function initMediaObserver() {
    chrome.storage.local.get(["showFloatingButton"], (res) => {
      if (res.showFloatingButton === false) return;
      scanMediaElements();
      
      const observer = new MutationObserver(() => {
        scanMediaElements();
      });
      observer.observe(document.body || document.documentElement, {
        childList: true,
        subtree: true
      });
    });
  }

  function scanMediaElements() {
    const videos = document.querySelectorAll("video");
    videos.forEach(video => {
      attachDownloadButton(video);
      collectMediaStream(video);
    });

    const audios = document.querySelectorAll("audio");
    audios.forEach(audio => {
      collectMediaStream(audio);
    });
  }

  function collectMediaStream(el) {
    const src = el.currentSrc || el.src || (el.querySelector("source") ? el.querySelector("source").src : null);
    if (!src || src.startsWith("data:")) return;

    const title = getMediaTitle();
    const existing = detectedMedia.find(m => m.url === src);
    if (!existing) {
      detectedMedia.push({
        url: src,
        title: title,
        type: el.tagName.toLowerCase(),
        duration: el.duration || 0
      });
    }
  }

  function getMediaTitle() {
    // Attempt to extract title from page or document
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle && ogTitle.content) return sanitizeFilename(ogTitle.content);

    const docTitle = document.title;
    if (docTitle) return sanitizeFilename(docTitle);

    return `video_${Date.now()}`;
  }

  function sanitizeFilename(name) {
    return name.replace(/[\\/:*?"<>|]/g, "_").trim().slice(0, 100);
  }

  function attachDownloadButton(video) {
    if (video.dataset.nexusDmAttached) return;
    video.dataset.nexusDmAttached = "true";

    // Create floating badge wrapper
    const btn = document.createElement("div");
    btn.className = "nexus-dm-float-btn";
    btn.innerHTML = `
      <span class="nexus-dm-icon">⚡</span>
      <span class="nexus-dm-text">Download Video</span>
    `;

    btn.title = "Download this video with Nexus DM";

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();

      let targetUrl = video.currentSrc || video.src;
      if (!targetUrl || targetUrl.startsWith("blob:")) {
        // For blob or stream, pass current page url so yt-dlp/engine handles it
        targetUrl = window.location.href;
      }

      chrome.runtime.sendMessage({
        action: "download_stream",
        url: targetUrl,
        title: getMediaTitle() + ".mp4"
      });

      // Visual feedback
      btn.innerHTML = `<span class="nexus-dm-icon">✓</span> <span class="nexus-dm-text">Sent to NDM</span>`;
      setTimeout(() => {
        btn.innerHTML = `<span class="nexus-dm-icon">⚡</span> <span class="nexus-dm-text">Download Video</span>`;
      }, 2500);
    });

    // Position container
    const parent = video.parentElement;
    if (parent) {
      const pos = window.getComputedStyle(parent).position;
      if (pos === "static") {
        parent.style.position = "relative";
      }
      parent.appendChild(btn);
    }
  }

  // Handle messages from background/popup
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "get_media_streams") {
      scanMediaElements();
      sendResponse({
        streams: detectedMedia,
        pageUrl: window.location.href,
        pageTitle: document.title
      });
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMediaObserver);
  } else {
    initMediaObserver();
  }
})();
