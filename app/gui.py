"""
Nexus DM (NDM) - Main Desktop Dashboard GUI
Built with CustomTkinter for high-DPI modern aesthetic.
"""

import os
import subprocess
import customtkinter as ctk
from typing import Dict, List, Optional
from tkinter import filedialog, messagebox
from pathlib import Path
import sys

try:
    from .config import config, APP_NAME, APP_VERSION
    from .engine import engine, format_bytes, DownloadState
    from .storage import storage
    from .progress_dialog import ProgressDialog
except (ImportError, ValueError):
    try:
        from app.config import config, APP_NAME, APP_VERSION
        from app.engine import engine, format_bytes, DownloadState
        from app.storage import storage
        from app.progress_dialog import ProgressDialog
    except (ImportError, ValueError):
        from config import config, APP_NAME, APP_VERSION
        from engine import engine, format_bytes, DownloadState
        from storage import storage
        from progress_dialog import ProgressDialog

class AddUrlDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_submit):
        super().__init__(parent)
        self.title("Add New Download - Nexus DM")
        self.geometry("520x280")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_submit = on_submit

        self._setup_ui()

    def _setup_ui(self):
        pad = 16
        ctk.CTkLabel(self, text="Download URL:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=pad, pady=(16, 4))
        self.entry_url = ctk.CTkEntry(self, placeholder_text="Paste direct download or media URL (e.g., https://...)", width=480)
        self.entry_url.pack(padx=pad, pady=4)

        # Check clipboard for url
        try:
            clip = self.clipboard_get().strip()
            if clip.startswith("http://") or clip.startswith("https://"):
                self.entry_url.insert(0, clip)
        except Exception:
            pass

        ctk.CTkLabel(self, text="Save Location:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=pad, pady=(10, 4))
        f_row = ctk.CTkFrame(self, fg_color="transparent")
        f_row.pack(fill="x", padx=pad, pady=4)

        self.entry_path = ctk.CTkEntry(f_row, width=380)
        self.entry_path.insert(0, config.download_dir)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(f_row, text="Browse", width=80, command=self._browse_dir)
        btn_browse.pack(side="right")

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=pad, pady=(20, 16))

        btn_start = ctk.CTkButton(btn_box, text="⚡ Download Now", fg_color="#2b7de9", hover_color="#1a63c4", width=140, command=self._submit)
        btn_start.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", width=90, fg_color="gray", command=self.destroy)
        btn_cancel.pack(side="right")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.entry_path.get())
        if d:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, d)

    def _submit(self):
        url = self.entry_url.get().strip()
        path = self.entry_path.get().strip()
        if not url:
            return
        self.on_submit(url, path)
        self.destroy()

class DownloadItemRow(ctk.CTkFrame):
    def __init__(self, parent, item_data: Dict, on_action):
        super().__init__(parent, corner_radius=6, height=64)
        self.item_data = item_data
        self.on_action = on_action
        self.task_id = item_data["id"]

        self.pack(fill="x", padx=8, pady=4)
        self._setup_ui()

    def _setup_ui(self):
        # Category icon badge
        cat = self.item_data.get("category", "Other")
        icon_map = {
            "Video": "🎬",
            "Audio": "🎵",
            "Compressed": "📦",
            "Document": "📄",
            "Program": "💻",
            "Other": "📁"
        }
        badge = icon_map.get(cat, "📁")

        lbl_icon = ctk.CTkLabel(self, text=badge, font=ctk.CTkFont(size=20), width=36)
        lbl_icon.pack(side="left", padx=(10, 6))

        # Main details (filename, size, speed)
        mid_frame = ctk.CTkFrame(self, fg_color="transparent")
        mid_frame.pack(side="left", fill="both", expand=True, padx=4, pady=6)

        self.lbl_name = ctk.CTkLabel(
            mid_frame,
            text=self.item_data["filename"],
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.lbl_name.pack(fill="x")

        # Progress bar
        total = self.item_data.get("total_bytes", 0)
        down = self.item_data.get("downloaded_bytes", 0)
        pct = (down / total) if total > 0 else (1.0 if self.item_data["status"] == DownloadState.COMPLETED else 0.0)

        self.pbar = ctk.CTkProgressBar(mid_frame, height=6, corner_radius=3)
        self.pbar.set(min(max(pct, 0.0), 1.0))
        self.pbar.pack(fill="x", pady=2)

        # Meta text (Size, Speed, Status)
        status = self.item_data["status"].capitalize()
        size_txt = f"{format_bytes(down)} / {format_bytes(total) if total > 0 else 'Unknown'}"
        speed_txt = f" • {self.item_data.get('speed', 0):.1f} KB/s" if self.item_data.get("speed") else ""
        self.lbl_meta = ctk.CTkLabel(
            mid_frame,
            text=f"{status} • {size_txt}{speed_txt}",
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w"
        )
        self.lbl_meta.pack(fill="x")

        # Action buttons
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(side="right", padx=10)

        if self.item_data["status"] == DownloadState.COMPLETED:
            btn_open = ctk.CTkButton(act_frame, text="Open", width=60, height=26, command=lambda: self.on_action("open", self.task_id))
            btn_open.pack(side="left", padx=2)
        elif self.item_data["status"] == DownloadState.DOWNLOADING:
            btn_pause = ctk.CTkButton(act_frame, text="Pause", width=60, height=26, command=lambda: self.on_action("pause", self.task_id))
            btn_pause.pack(side="left", padx=2)
        elif self.item_data["status"] == DownloadState.PAUSED:
            btn_resume = ctk.CTkButton(act_frame, text="Resume", width=60, height=26, command=lambda: self.on_action("resume", self.task_id))
            btn_resume.pack(side="left", padx=2)

        btn_folder = ctk.CTkButton(act_frame, text="📁", width=30, height=26, fg_color="transparent", hover_color="#333333", command=lambda: self.on_action("folder", self.task_id))
        btn_folder.pack(side="left", padx=2)

        btn_del = ctk.CTkButton(act_frame, text="🗑", width=30, height=26, fg_color="transparent", hover_color="#552222", text_color="#ff5555", command=lambda: self.on_action("delete", self.task_id))
        btn_del.pack(side="left", padx=2)

    def update_data(self, item_data: Dict):
        self.item_data = item_data
        total = self.item_data.get("total_bytes", 0)
        down = self.item_data.get("downloaded_bytes", 0)
        pct = (down / total) if total > 0 else (1.0 if self.item_data["status"] == DownloadState.COMPLETED else 0.0)
        self.pbar.set(min(max(pct, 0.0), 1.0))

        status = self.item_data["status"].capitalize()
        size_txt = f"{format_bytes(down)} / {format_bytes(total) if total > 0 else 'Unknown'}"
        speed_txt = f" • {self.item_data.get('speed_formatted', '')}" if self.item_data.get("speed") else ""
        self.lbl_meta.configure(text=f"{status} • {size_txt}{speed_txt}")

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode(config.theme)
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION} - Elite High-Speed Download Manager")
        self.geometry("960x600")
        self.minsize(800, 500)

        # Set application icon if available
        try:
            ico_paths = [
                Path(__file__).resolve().parent / "icons" / "app.ico",
                Path(__file__).resolve().parent.parent / "app" / "icons" / "app.ico",
            ]
            if getattr(sys, "frozen", False):
                ico_paths.insert(0, Path(sys._MEIPASS) / "app" / "icons" / "app.ico")
                ico_paths.insert(0, Path(sys._MEIPASS) / "icons" / "app.ico")
            for p in ico_paths:
                if p.exists():
                    self.iconbitmap(str(p))
                    break
        except Exception:
            pass

        self.active_category = "All"
        self.row_widgets: Dict[str, DownloadItemRow] = {}

        self._setup_ui()
        self._refresh_download_list()

        # Listen to global engine progress
        engine.add_global_listener(self._on_engine_event)
        self.after(2000, self._periodic_check)

    def _setup_ui(self):
        # 1. Top Navigation & Action Toolbar
        toolbar = ctk.CTkFrame(self, height=52, corner_radius=0)
        toolbar.pack(fill="x", side="top")

        btn_add = ctk.CTkButton(toolbar, text="➕ Add URL", width=110, fg_color="#2b7de9", hover_color="#1a63c4", font=ctk.CTkFont(weight="bold"), command=self._show_add_url)
        btn_add.pack(side="left", padx=(12, 6), pady=10)

        btn_open_dl = ctk.CTkButton(toolbar, text="📁 Downloads Folder", width=130, fg_color="#333333", hover_color="#444444", command=self._open_downloads_dir)
        btn_open_dl.pack(side="left", padx=6, pady=10)

        btn_refresh = ctk.CTkButton(toolbar, text="🔄 Refresh", width=90, fg_color="#333333", hover_color="#444444", command=self._refresh_download_list)
        btn_refresh.pack(side="left", padx=6, pady=10)

        # Right side toolbar indicators
        self.lbl_bridge = ctk.CTkLabel(toolbar, text="🟢 Extension Bridge: Online", font=ctk.CTkFont(size=11, weight="bold"), text_color="#5cb85c")
        self.lbl_bridge.pack(side="right", padx=(6, 16))

        # 2. Main Content (Sidebar + Table)
        main_body = ctk.CTkFrame(self, fg_color="transparent")
        main_body.pack(fill="both", expand=True)

        # Left Sidebar (Categories)
        sidebar = ctk.CTkFrame(main_body, width=180, corner_radius=0)
        sidebar.pack(side="left", fill="y", padx=0, pady=0)

        ctk.CTkLabel(sidebar, text="CATEGORIES", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w", padx=16, pady=(16, 8))

        cats = [
            ("📥 All Downloads", "All"),
            ("🎬 Video", "Video"),
            ("🎵 Audio", "Audio"),
            ("📦 Compressed", "Compressed"),
            ("📄 Documents", "Document"),
            ("💻 Programs", "Program"),
            ("📁 Other", "Other")
        ]

        self.cat_buttons = {}
        for label, cat_key in cats:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                anchor="w",
                fg_color="#1f538d" if cat_key == "All" else "transparent",
                hover_color="#223344",
                command=lambda k=cat_key: self._select_category(k)
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.cat_buttons[cat_key] = btn

        # Right List Area
        list_container = ctk.CTkFrame(main_body, fg_color="transparent")
        list_container.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        self.scroll_list = ctk.CTkScrollableFrame(list_container, label_text="Active & Completed Downloads")
        self.scroll_list.pack(fill="both", expand=True)

        # 3. Bottom Status Bar
        statusbar = ctk.CTkFrame(self, height=26, corner_radius=0)
        statusbar.pack(fill="x", side="bottom")

        self.lbl_status_left = ctk.CTkLabel(statusbar, text=f"Ready • Save Dir: {config.download_dir}", font=ctk.CTkFont(size=10), text_color="gray")
        self.lbl_status_left.pack(side="left", padx=12)

        self.lbl_status_right = ctk.CTkLabel(statusbar, text=f"Max Parallel Connections: {config.max_connections}", font=ctk.CTkFont(size=10), text_color="gray")
        self.lbl_status_right.pack(side="right", padx=12)

    def _select_category(self, cat_key: str):
        self.active_category = cat_key
        for k, btn in self.cat_buttons.items():
            btn.configure(fg_color="#1f538d" if k == cat_key else "transparent")
        self._refresh_download_list()

    def _show_add_url(self):
        AddUrlDialog(self, on_submit=self._start_new_download)

    def _start_new_download(self, url: str, path: str):
        task = engine.create_task(url=url, save_path=path, auto_start=True)
        if config.show_progress_dialog:
            ProgressDialog(self, task)
        self._refresh_download_list()

    def _open_downloads_dir(self):
        if os.path.exists(config.download_dir):
            try:
                subprocess.Popen(f'explorer "{config.download_dir}"')
            except Exception:
                pass

    def _handle_item_action(self, action: str, task_id: str):
        item = storage.get_download(task_id)
        if not item:
            return

        if action == "open":
            if os.path.exists(item["file_path"]):
                try:
                    os.startfile(item["file_path"])
                except Exception:
                    pass
        elif action == "folder":
            folder = os.path.dirname(item["file_path"])
            if os.path.exists(folder):
                try:
                    subprocess.Popen(f'explorer "{folder}"')
                except Exception:
                    pass
        elif action == "pause":
            engine.pause_task(task_id)
            self._refresh_download_list()
        elif action == "resume":
            engine.resume_task(task_id)
            self._refresh_download_list()
        elif action == "delete":
            ans = messagebox.askyesno("Delete Download", f"Delete '{item['filename']}' from list?\n(Click Yes to delete record)")
            if ans:
                engine.delete_task(task_id, delete_file=False)
                self._refresh_download_list()

    def _refresh_download_list(self):
        items = storage.get_downloads_by_category(self.active_category)
        existing_ids = set()

        for item in items:
            tid = item["id"]
            existing_ids.add(tid)
            if tid in self.row_widgets:
                self.row_widgets[tid].update_data(item)
            else:
                row = DownloadItemRow(self.scroll_list, item, on_action=self._handle_item_action)
                self.row_widgets[tid] = row

        # Remove rows no longer present
        for tid in list(self.row_widgets.keys()):
            if tid not in existing_ids:
                self.row_widgets[tid].destroy()
                del self.row_widgets[tid]

    def _on_engine_event(self, info: Dict):
        tid = info["id"]
        self.after(0, self._update_row_live, tid, info)

    def _update_row_live(self, tid: str, info: Dict):
        if tid in self.row_widgets:
            self.row_widgets[tid].update_data(info)

    def _periodic_check(self):
        self._refresh_download_list()
        self.after(3000, self._periodic_check)
