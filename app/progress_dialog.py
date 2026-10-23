"""
Nexus DM (NDM) - IDM-Style Download Progress Dialog
Features: Real-time speed, ETA, overall progress, and multi-connection segment visualizer!
"""

import os
import subprocess
import customtkinter as ctk
from pathlib import Path
import sys
from typing import Optional, Dict

try:
    from .engine import format_bytes, format_speed, DownloadState
except (ImportError, ValueError):
    try:
        from app.engine import format_bytes, format_speed, DownloadState
    except (ImportError, ValueError):
        from engine import format_bytes, format_speed, DownloadState

class ProgressDialog(ctk.CTkToplevel):
    def __init__(self, parent, task, on_close=None):
        super().__init__(parent)
        self.task = task
        self.on_close = on_close
        self.title(f"Downloading - {self.task.filename}")
        self.geometry("560x340")
        self.minsize(520, 320)
        self.attributes("-topmost", True)

        self._is_active = True
        try:
            candidates = []
            if getattr(sys, "frozen", False):
                candidates.append(Path(sys._MEIPASS) / "app" / "icons" / "app.ico")
                candidates.append(Path(sys._MEIPASS) / "icons" / "app.ico")
            candidates.append(Path(__file__).resolve().parent / "icons" / "app.ico")
            for c in candidates:
                if c.exists():
                    self.iconbitmap(str(c))
                    break
        except Exception:
            pass
        self._setup_ui()
        self.task.add_listener(self._on_task_update)
        self.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _setup_ui(self):
        # 1. Header Frame
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 6))

        self.lbl_title = ctk.CTkLabel(
            header,
            text=self.task.filename,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.lbl_title.pack(fill="x")

        self.lbl_url = ctk.CTkLabel(
            header,
            text=self.task.url,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w"
        )
        self.lbl_url.pack(fill="x")

        # 2. Main Stats Grid
        stats_frame = ctk.CTkFrame(self, corner_radius=8)
        stats_frame.pack(fill="x", padx=16, pady=6)

        # Status & Size
        r1 = ctk.CTkFrame(stats_frame, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=4)
        self.lbl_status = ctk.CTkLabel(r1, text="Status: Downloading...", font=ctk.CTkFont(size=12))
        self.lbl_status.pack(side="left")
        self.lbl_size = ctk.CTkLabel(r1, text="Size: 0 B / 0 B", font=ctk.CTkFont(size=12))
        self.lbl_size.pack(side="right")

        # Speed & ETA
        r2 = ctk.CTkFrame(stats_frame, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=4)
        self.lbl_speed = ctk.CTkLabel(r2, text="Transfer rate: 0.00 B/s", font=ctk.CTkFont(size=12))
        self.lbl_speed.pack(side="left")
        self.lbl_eta = ctk.CTkLabel(r2, text="Time left: --:--", font=ctk.CTkFont(size=12))
        self.lbl_eta.pack(side="right")

        # 3. Overall Progress Bar
        bar_frame = ctk.CTkFrame(self, fg_color="transparent")
        bar_frame.pack(fill="x", padx=16, pady=6)

        self.progress_bar = ctk.CTkProgressBar(bar_frame, height=16, corner_radius=4)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")

        self.lbl_percent = ctk.CTkLabel(bar_frame, text="0.0%", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_percent.pack(anchor="e", pady=(2, 0))

        # 4. Multi-Segment Chunks Visualizer (IDM Style)
        chunk_container = ctk.CTkFrame(self, corner_radius=6)
        chunk_container.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            chunk_container,
            text=f"Multi-Connection Stream Visualizer ({self.task.num_connections} Segments)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="gray"
        ).pack(anchor="w", padx=8, pady=(4, 2))

        self.chunk_bars_frame = ctk.CTkFrame(chunk_container, fg_color="transparent")
        self.chunk_bars_frame.pack(fill="x", padx=8, pady=(0, 6))

        self.chunk_widgets = []
        for i in range(self.task.num_connections):
            pb = ctk.CTkProgressBar(self.chunk_bars_frame, height=8, corner_radius=2)
            pb.set(0)
            pb.pack(side="left", fill="x", expand=True, padx=1)
            self.chunk_widgets.append(pb)

        # 5. Buttons Action Row
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(10, 12))

        self.btn_pause = ctk.CTkButton(btn_frame, text="Pause", width=80, command=self._toggle_pause)
        self.btn_pause.pack(side="left", padx=(0, 6))

        self.btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="#d9534f", hover_color="#c9302c", command=self._handle_cancel)
        self.btn_cancel.pack(side="left", padx=6)

        self.btn_open_folder = ctk.CTkButton(btn_frame, text="Open Folder", width=95, command=self._open_folder)
        self.btn_open_folder.pack(side="right", padx=(6, 0))

        self.btn_open_file = ctk.CTkButton(btn_frame, text="Open File", width=85, command=self._open_file, state="disabled")
        self.btn_open_file.pack(side="right", padx=6)

    def _toggle_pause(self):
        if self.task.status == DownloadState.DOWNLOADING:
            self.task.pause()
            self.btn_pause.configure(text="Resume")
        elif self.task.status == DownloadState.PAUSED:
            self.task.start()
            self.btn_pause.configure(text="Pause")

    def _handle_cancel(self):
        self.task.cancel()
        self._handle_close()

    def _open_file(self):
        if os.path.exists(self.task.file_path):
            try:
                os.startfile(self.task.file_path)
            except Exception:
                pass

    def _open_folder(self):
        folder = os.path.dirname(self.task.file_path)
        if os.path.exists(folder):
            try:
                subprocess.Popen(f'explorer "{folder}"')
            except Exception:
                pass

    def _on_task_update(self, info: Dict):
        if not self._is_active:
            return
        self.after(0, self._apply_update, info)

    def _apply_update(self, info: Dict):
        if not self._is_active:
            return

        total = info["total_bytes"]
        downloaded = info["downloaded_bytes"]
        pct = (downloaded / total) if total > 0 else 0
        pct_clamped = min(max(pct, 0.0), 1.0)

        self.progress_bar.set(pct_clamped)
        self.lbl_percent.configure(text=f"{pct_clamped * 100:.1f}%")
        self.lbl_size.configure(text=f"Size: {format_bytes(downloaded)} / {format_bytes(total) if total > 0 else 'Unknown'}")
        self.lbl_speed.configure(text=f"Transfer rate: {info['speed_formatted']}")
        self.lbl_eta.configure(text=f"Time left: {info['eta']}")

        status_txt = info["status"].capitalize()
        self.lbl_status.configure(text=f"Status: {status_txt}")

        # Update chunk visualizers
        chunks = info.get("chunks", [])
        for i, chunk in enumerate(chunks):
            if i < len(self.chunk_widgets):
                c_total = chunk.get("total", 1)
                c_down = chunk.get("downloaded", 0)
                cp = min(max(c_down / c_total, 0.0), 1.0) if c_total > 0 else 0
                self.chunk_widgets[i].set(cp)

        if info["status"] == DownloadState.COMPLETED:
            self.btn_pause.configure(state="disabled")
            self.btn_cancel.configure(text="Close", fg_color="gray")
            self.btn_open_file.configure(state="normal")
            for pb in self.chunk_widgets:
                pb.set(1.0)

        elif info["status"] == DownloadState.FAILED:
            self.lbl_status.configure(text=f"Error: {info['error_message']}", text_color="#d9534f")
            self.btn_pause.configure(state="disabled")

    def _handle_close(self):
        self._is_active = False
        self.task.remove_listener(self._on_task_update)
        if self.on_close:
            self.on_close(self)
        self.destroy()
