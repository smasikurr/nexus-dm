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

    const title = getMediaTitle(el, src);
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

  function getMediaTitle(video, srcUrl) {
    // 1. Try URL filename first for exact unique file naming
    if (srcUrl) {
      try {
        const urlObj = new URL(srcUrl, window.location.href);
        const pathname = urlObj.pathname;
        const lastSeg = pathname.split("/").pop();
        if (lastSeg && lastSeg.includes(".") && !lastSeg.endsWith(".html") && !lastSeg.endsWith(".php")) {
          return sanitizeFilename(decodeURIComponent(lastSeg));
        }
      } catch (e) {}
    }

    // 2. Try video element accessibility labels or container titles
    if (video) {
      const directLabel = video.getAttribute("aria-label") || video.getAttribute("title") || video.getAttribute("alt");
      if (directLabel) {
        return sanitizeFilename(directLabel) + ".mp4";
      }

      const container = video.closest("article, figure, [data-title], [aria-label], .video-container");
      if (container) {
        const cLabel = container.getAttribute("data-title") || container.getAttribute("aria-label");
        if (cLabel) {
          return sanitizeFilename(cLabel) + ".mp4";
        }
      }
    }

    // 3. Fallback: Page title with unique random suffix
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const baseTitle = (ogTitle && ogTitle.content) || document.title || "video";
    const shortId = Math.random().toString(36).substring(2, 7);
    return `${sanitizeFilename(baseTitle)}_${shortId}.mp4`;
  }

  function sanitizeFilename(name) {
    return name.replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim().slice(0, 80);
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

      const cleanFilename = getMediaTitle(video, targetUrl);

      chrome.runtime.sendMessage({
        action: "download_stream",
        url: targetUrl,
        title: cleanFilename,
        referer: window.location.href
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
