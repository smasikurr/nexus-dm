"""
Nexus DM (NDM) - High-Speed Multi-Threaded Chunk Downloader Engine
Supports: Multi-connection segmented downloading, Pause/Resume, yt-dlp streams, live progress.
"""

import os
import time
import uuid
import threading
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Callable
import requests

from .config import config
from .storage import storage

class DownloadState:
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

def format_bytes(size: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def format_speed(bytes_per_sec: float) -> str:
    return f"{format_bytes(bytes_per_sec)}/s"

def format_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400 * 7:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class ChunkWorker(threading.Thread):
    def __init__(self, chunk_id: int, url: str, file_path: str, start_byte: int, end_byte: int,
                 headers: Dict, on_bytes: Callable[[int, int], None], is_running_check: Callable[[], bool]):
        super().__init__(daemon=True)
        self.chunk_id = chunk_id
        self.url = url
        self.file_path = file_path
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.downloaded = 0
        self.headers = headers.copy()
        self.on_bytes = on_bytes
        self.is_running_check = is_running_check
        self.error = None
        self.completed = False

    def run(self):
        cur_start = self.start_byte + self.downloaded
        if cur_start > self.end_byte:
            self.completed = True
            return

        range_header = f"bytes={cur_start}-{self.end_byte}"
        self.headers["Range"] = range_header

        try:
            with requests.get(self.url, headers=self.headers, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(self.file_path, "r+b") as f:
                    f.seek(cur_start)
                    for chunk in r.iter_content(chunk_size=32768):
                        if not self.is_running_check():
                            break
                        if chunk:
                            f.write(chunk)
                            size = len(chunk)
                            self.downloaded += size
                            self.on_bytes(self.chunk_id, size)
                
                if self.start_byte + self.downloaded >= self.end_byte:
                    self.completed = True
        except Exception as e:
            self.error = str(e)

class DownloadTask:
    def __init__(self, task_id: str, url: str, filename: Optional[str] = None, save_path: Optional[str] = None,
                 headers: Optional[Dict] = None, num_connections: int = 16):
        self.id = task_id
        self.url = url
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        self.num_connections = min(max(num_connections, 1), 32)
        self.status = DownloadState.QUEUED
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.speed = 0.0
        self.eta = "--:--"
        self.error_message = ""
        self.category = "Other"
        self.supports_ranges = False

        self.filename = filename or self._extract_filename(url)
        self.file_path = save_path or os.path.join(config.download_dir, self.filename)
        self.category = config.detect_category(self.filename)

        self._workers: List[ChunkWorker] = []
        self._chunks_progress: List[Dict] = []
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._listeners: List[Callable[[Dict], None]] = []
        self._last_time = time.time()
        self._last_bytes = 0

    def _extract_filename(self, url: str) -> str:
        try:
            parsed = urllib.parse.urlparse(url)
            base = os.path.basename(parsed.path)
            if base and "." in base:
                return urllib.parse.unquote(base)
        except Exception:
            pass
        return f"download_{self.id[:8]}.bin"

    def add_listener(self, cb: Callable[[Dict], None]):
        with self._lock:
            if cb not in self._listeners:
                self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[Dict], None]):
        with self._lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    def _notify(self):
        info = self.get_info()
        for listener in list(self._listeners):
            try:
                listener(info)
            except Exception:
                pass

    def get_info(self) -> Dict:
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.filename,
            "file_path": self.file_path,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "speed": self.speed,
            "speed_formatted": format_speed(self.speed),
            "eta": self.eta,
            "status": self.status,
            "category": self.category,
            "error_message": self.error_message,
            "progress_percent": (self.downloaded_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0,
            "chunks": [c.copy() for c in self._chunks_progress]
        }

    def _on_chunk_bytes(self, chunk_id: int, size: int):
        with self._lock:
            self.downloaded_bytes += size
            if 0 <= chunk_id < len(self._chunks_progress):
                self._chunks_progress[chunk_id]["downloaded"] += size

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self.status = DownloadState.DOWNLOADING
        storage.update_status(self.id, self.status)
        threading.Thread(target=self._run_download, daemon=True).start()

    def pause(self):
        self._paused = True
        self._running = False
        self.status = DownloadState.PAUSED
        self.speed = 0.0
        self.eta = "--:--"
        storage.update_status(self.id, self.status)
        self._notify()

    def cancel(self):
        self._running = False
        self._paused = False
        self.status = DownloadState.CANCELLED
        storage.update_status(self.id, self.status)
        self._notify()

    def _is_running(self) -> bool:
        return self._running and not self._paused

    def _probe_server(self) -> bool:
        try:
            head_headers = self.headers.copy()
            resp = requests.head(self.url, headers=head_headers, allow_redirects=True, timeout=15)
            
            # Check content disposition filename
            cd = resp.headers.get("content-disposition", "")
            if "filename=" in cd:
                fname = cd.split("filename=")[1].strip('"\' ;')
                if fname:
                    self.filename = urllib.parse.unquote(fname)
                    self.file_path = os.path.join(os.path.dirname(self.file_path), self.filename)
                    self.category = config.detect_category(self.filename)

            # Check length & range support
            length = resp.headers.get("content-length")
            if length and length.isdigit():
                self.total_bytes = int(length)

            accept_ranges = resp.headers.get("accept-ranges", "").lower()
            self.supports_ranges = (accept_ranges == "bytes") or (resp.status_code == 206)

            # If head failed to give content length, try range 0-0 get request
            if self.total_bytes <= 0:
                test_headers = self.headers.copy()
                test_headers["Range"] = "bytes=0-0"
                with requests.get(self.url, headers=test_headers, stream=True, timeout=10) as r:
                    cr = r.headers.get("content-range", "")
                    if "/" in cr:
                        total_str = cr.split("/")[1]
                        if total_str.isdigit():
                            self.total_bytes = int(total_str)
                            self.supports_ranges = True
            return True
        except Exception as e:
            # Server might reject HEAD, will fallback to stream
            return False

    def _run_download(self):
        try:
            # Ensure unique filename if already exists and not resuming
            if not os.path.exists(self.file_path) or self.downloaded_bytes == 0:
                base_dir = os.path.dirname(self.file_path)
                os.makedirs(base_dir, exist_ok=True)

            self._probe_server()

            # Check if YouTube or media stream that should be handled with yt-dlp
            is_streaming_site = any(domain in self.url.lower() for domain in [
                "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "facebook.com/watch", "twitter.com/i/status"
            ])

            if is_streaming_site:
                self._run_ytdlp_download()
                return

            if self.supports_ranges and self.total_bytes > 1024 * 512:
                self._run_segmented_download()
            else:
                self._run_single_stream_download()

        except Exception as e:
            self.error_message = str(e)
            self.status = DownloadState.FAILED
            storage.update_status(self.id, self.status, self.error_message)
            self._notify()

    def _run_segmented_download(self):
        # Pre-allocate file if starting fresh
        if not os.path.exists(self.file_path) or os.path.getsize(self.file_path) != self.total_bytes:
            with open(self.file_path, "wb") as f:
                f.seek(self.total_bytes - 1)
                f.write(b"\0")

        chunk_size = self.total_bytes // self.num_connections
        self._chunks_progress = []
        self._workers = []

        for i in range(self.num_connections):
            start = i * chunk_size
            end = self.total_bytes - 1 if i == self.num_connections - 1 else (start + chunk_size - 1)
            self._chunks_progress.append({
                "chunk_id": i,
                "start": start,
                "end": end,
                "total": end - start + 1,
                "downloaded": 0
            })
            worker = ChunkWorker(
                chunk_id=i,
                url=self.url,
                file_path=self.file_path,
                start_byte=start,
                end_byte=end,
                headers=self.headers,
                on_bytes=self._on_chunk_bytes,
                is_running_check=self._is_running
            )
            self._workers.append(worker)
            worker.start()

        self._monitor_progress()

    def _run_single_stream_download(self):
        mode = "ab" if self.downloaded_bytes > 0 else "wb"
        headers = self.headers.copy()
        if self.downloaded_bytes > 0 and self.supports_ranges:
            headers["Range"] = f"bytes={self.downloaded_bytes}-"

        with requests.get(self.url, headers=headers, stream=True, timeout=20) as r:
            r.raise_for_status()
            if self.total_bytes <= 0:
                length = r.headers.get("content-length")
                if length and length.isdigit():
                    self.total_bytes = int(length)

            with open(self.file_path, mode) as f:
                last_time = time.time()
                last_bytes = self.downloaded_bytes

                for chunk in r.iter_content(chunk_size=32768):
                    if not self._is_running():
                        break
                    if chunk:
                        f.write(chunk)
                        self.downloaded_bytes += len(chunk)

                        now = time.time()
                        dt = now - last_time
                        if dt >= 0.5:
                            db = self.downloaded_bytes - last_bytes
                            self.speed = db / dt if dt > 0 else 0
                            if self.total_bytes > self.downloaded_bytes and self.speed > 0:
                                self.eta = format_eta((self.total_bytes - self.downloaded_bytes) / self.speed)
                            last_time = now
                            last_bytes = self.downloaded_bytes
                            storage.update_progress(self.id, self.downloaded_bytes, self.total_bytes, self.speed, self.eta)
                            self._notify()

        if self._is_running():
            self._finish_download()

    def _run_ytdlp_download(self):
        try:
            import yt_dlp
        except ImportError:
            self._run_single_stream_download()
            return

        def ytdl_hook(d):
            if not self._is_running():
                raise Exception("Download paused/cancelled by user")
            if d.get("status") == "downloading":
                self.downloaded_bytes = d.get("downloaded_bytes", 0)
                self.total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                self.speed = d.get("speed") or 0.0
                eta_sec = d.get("eta") or 0
                self.eta = format_eta(eta_sec)
                self.filename = os.path.basename(d.get("filename", self.filename))
                self.file_path = d.get("filename", self.file_path)
                storage.update_progress(self.id, self.downloaded_bytes, self.total_bytes, self.speed, self.eta)
                self._notify()
            elif d.get("status") == "finished":
                self.downloaded_bytes = self.total_bytes

        ydl_opts = {
            "outtmpl": os.path.join(config.download_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [ytdl_hook],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([self.url])

        if self._is_running():
            self._finish_download()

    def _monitor_progress(self):
        last_time = time.time()
        last_bytes = self.downloaded_bytes

        while self._is_running():
            all_done = all(w.completed for w in self._workers)
            any_error = any(w.error for w in self._workers)

            if any_error:
                err = next(w.error for w in self._workers if w.error)
                raise Exception(f"Chunk error: {err}")

            now = time.time()
            dt = now - last_time
            if dt >= 0.5:
                db = self.downloaded_bytes - last_bytes
                self.speed = db / dt if dt > 0 else 0
                if self.total_bytes > self.downloaded_bytes and self.speed > 0:
                    self.eta = format_eta((self.total_bytes - self.downloaded_bytes) / self.speed)
                last_time = now
                last_bytes = self.downloaded_bytes
                storage.update_progress(self.id, self.downloaded_bytes, self.total_bytes, self.speed, self.eta)
                self._notify()

            if all_done:
                break
            time.sleep(0.1)

        if self._is_running():
            self._finish_download()

    def _finish_download(self):
        self.status = DownloadState.COMPLETED
        self.downloaded_bytes = self.total_bytes if self.total_bytes > 0 else self.downloaded_bytes
        self.speed = 0.0
        self.eta = "Done"
        self._running = False
        storage.update_status(self.id, self.status)
        self._notify()

class DownloadEngine:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self._lock = threading.Lock()
        self._global_listeners: List[Callable[[Dict], None]] = []

    def add_global_listener(self, cb: Callable[[Dict], None]):
        with self._lock:
            if cb not in self._global_listeners:
                self._global_listeners.append(cb)

    def remove_global_listener(self, cb: Callable[[Dict], None]):
        with self._lock:
            if cb in self._global_listeners:
                self._global_listeners.remove(cb)

    def _on_task_update(self, info: Dict):
        for listener in list(self._global_listeners):
            try:
                listener(info)
            except Exception:
                pass

    def create_task(self, url: str, filename: Optional[str] = None, save_path: Optional[str] = None,
                    headers: Optional[Dict] = None, auto_start: bool = True) -> DownloadTask:
        task_id = str(uuid.uuid4())
        task = DownloadTask(task_id, url, filename, save_path, headers, num_connections=config.max_connections)
        task.add_listener(self._on_task_update)

        storage.add_download({
            "id": task.id,
            "url": task.url,
            "filename": task.filename,
            "file_path": task.file_path,
            "total_bytes": 0,
            "downloaded_bytes": 0,
            "status": DownloadState.QUEUED,
            "category": task.category
        })

        with self._lock:
            self.tasks[task_id] = task

        if auto_start:
            task.start()

        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        with self._lock:
            return self.tasks.get(task_id)

    def pause_task(self, task_id: str):
        task = self.get_task(task_id)
        if task:
            task.pause()

    def resume_task(self, task_id: str):
        task = self.get_task(task_id)
        if task:
            task.start()

    def cancel_task(self, task_id: str):
        task = self.get_task(task_id)
        if task:
            task.cancel()

    def delete_task(self, task_id: str, delete_file: bool = False):
        self.cancel_task(task_id)
        with self._lock:
            self.tasks.pop(task_id, None)
        storage.delete_download(task_id, delete_file=delete_file)

engine = DownloadEngine()
