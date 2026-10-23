# ⚡ Nexus DM (NDM)

> **Elite High-Speed Multi-Threaded Download Manager & Media Grabber**  
> 100% Free • Unlimited Personal Use • No Trials • No Licensing Restrictions

---

## 🌟 Overview

**Nexus DM (NDM)** is an advanced, modern download manager designed from the ground up as a fast, customizable, and completely unrestricted personal alternative to commercial downloaders like IDM.

It consists of two unified components:
1. **Desktop Application (`.EXE`)**: A Python-powered, multi-connection segmented chunk downloader with a sleek Dark/Light mode GUI and real-time chunk visualization.
2. **Browser Extension (Manifest V3)**: A media sniffer for Chrome, Edge, and Brave that injects a floating `[⚡ Download Video]` grabber on HTML5 media players (YouTube, Facebook, Twitter, Vimeo) and seamlessly intercepts browser downloads.

---

## 🚀 Key Features

- **Segmented Multi-Connection Acceleration**: Splits files into 8–32 simultaneous connections via HTTP Range requests for maximum bandwidth utilization.
- **Floating Video & Media Sniffer**: Automatically detects video and audio streams on any webpage and shows an unobtrusive one-click download badge.
- **IDM-Style Segment Progress Visualizer**: Displays a real-time progress bar for each individual parallel connection chunk.
- **Smart Category Organization**: Automatically sorts downloads into Video, Audio, Compressed, Document, and Program categories.
- **Pause & Resume**: Seamlessly pause and resume large files without losing downloaded data.
- **Local REST Bridge**: Robust, zero-config local API on `127.0.0.1:45678` with full CORS support.
- **Streaming Site Support**: Integrated `yt-dlp` backend for YouTube and video platforms.

---

## 🛠️ Installation & Setup

### 1. Run the Desktop App
```bash
# Install dependencies
pip install customtkinter requests httpx yt-dlp

# Run Desktop Application
python -m app.main
```

### 2. Build the Standalone Windows `.EXE`
To package the app into a single, portable executable:
```bash
pyinstaller --noconfirm --onedir --windowed --name "NexusDM" --icon "app/icons/app.ico" app/main.py
```
The compiled executable will be located in `dist/NexusDM/NexusDM.exe`.

### 3. Load the Browser Extension
1. Open Google Chrome, Brave, or Microsoft Edge.
2. Navigate to `chrome://extensions/` (or `edge://extensions/`).
3. Enable **Developer mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select the folder:
   `D:\WORKFLOW\TOOLS\DM\nexus-dm\extension`
5. The **Nexus DM** icon will appear in your browser toolbar with status `🟢 Online`.

---

## 🧪 Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

All tests verify:
- Persistent SQLite storage & category queries.
- Multi-threaded segmented range chunking.
- Local REST API server & CORS headers.

---

## 📄 License
MIT License - Personal & Open Source.
