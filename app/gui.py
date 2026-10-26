"""
Nexus DM (NDM) - Main Desktop Dashboard GUI
Faithfully styled and architected after Internet Download Manager (IDM).
Features: Authentic 3D Toolbar, Categories Tree, Full Downloads Grid,
Context Menus, "Download File Info" Dialog, and Options Dialog.
"""

import os
import sys
import subprocess
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

try:
    from .config import config, APP_NAME, APP_VERSION, CATEGORY_EXTENSIONS
    from .engine import engine, format_bytes, format_speed, DownloadState
    from .storage import storage
    from .progress_dialog import ProgressDialog
except (ImportError, ValueError):
    try:
        from app.config import config, APP_NAME, APP_VERSION, CATEGORY_EXTENSIONS
        from app.engine import engine, format_bytes, format_speed, DownloadState
        from app.storage import storage
        from app.progress_dialog import ProgressDialog
    except (ImportError, ValueError):
        from config import config, APP_NAME, APP_VERSION, CATEGORY_EXTENSIONS
        from engine import engine, format_bytes, format_speed, DownloadState
        from storage import storage
        from progress_dialog import ProgressDialog


def get_icon_path(filename: str) -> Optional[Path]:
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates.append(base / "app" / "icons" / filename)
        candidates.append(base / "icons" / filename)
    base_file = Path(__file__).resolve().parent
    candidates.append(base_file / "icons" / filename)
    candidates.append(base_file.parent / "app" / "icons" / filename)
    for p in candidates:
        if p.exists():
            return p
    return None


def get_ctk_icon(icon_name: str, size=(30, 26)):
    p = get_icon_path(icon_name)
    if p:
        try:
            im = Image.open(p)
            return ctk.CTkImage(light_image=im, dark_image=im, size=size)
        except Exception:
            pass
    return None


class AddUrlDialog(ctk.CTkToplevel):
    """
    IDM-style 'Download File Info' Dialog.
    Allows configuring URL, Category, and Destination before starting.
    """
    def __init__(self, parent, on_submit, default_url=""):
        super().__init__(parent)
        self.title("Download File Info - Nexus DM")
        self.geometry("540x310")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_submit = on_submit

        self._setup_icon()
        self._setup_ui(default_url)

    def _setup_icon(self):
        ico = get_icon_path("app.ico")
        if ico:
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

    def _setup_ui(self, default_url):
        pad = 16

        # Header Info Banner
        hdr_frame = ctk.CTkFrame(self, fg_color="transparent")
        hdr_frame.pack(fill="x", padx=pad, pady=(12, 6))

        ico_img = get_ctk_icon("tb_add_url.png", size=(32, 28))
        if ico_img:
            lbl_ico = ctk.CTkLabel(hdr_frame, image=ico_img, text="")
            lbl_ico.pack(side="left", padx=(0, 10))

        lbl_hdr = ctk.CTkLabel(
            hdr_frame,
            text="Enter new address to download",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_hdr.pack(side="left")

        # 1. URL Row
        ctk.CTkLabel(self, text="Address (URL):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=pad, pady=(6, 2))
        self.entry_url = ctk.CTkEntry(self, placeholder_text="https://...", width=500)
        self.entry_url.pack(padx=pad, pady=2)

        # Pre-fill URL if passed or from clipboard
        if default_url:
            self.entry_url.insert(0, default_url)
        else:
            try:
                clip = self.clipboard_get().strip()
                if clip.startswith("http://") or clip.startswith("https://"):
                    self.entry_url.insert(0, clip)
            except Exception:
                pass

        # 2. Category & File Name Preview
        cat_frame = ctk.CTkFrame(self, fg_color="transparent")
        cat_frame.pack(fill="x", padx=pad, pady=6)

        ctk.CTkLabel(cat_frame, text="Category:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        self.cat_var = ctk.StringVar(value="General")
        categories = ["General", "Video", "Audio", "Compressed", "Document", "Program", "Other"]
        self.cat_menu = ctk.CTkOptionMenu(cat_frame, values=categories, variable=self.cat_var, width=130)
        self.cat_menu.pack(side="left")

        # Auto-detect category from URL
        self.entry_url.bind("<KeyRelease>", self._on_url_change)
        self._on_url_change()

        # 3. Save To Location
        ctk.CTkLabel(self, text="Save To (Destination Folder):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=pad, pady=(6, 2))
        f_row = ctk.CTkFrame(self, fg_color="transparent")
        f_row.pack(fill="x", padx=pad, pady=2)

        self.entry_path = ctk.CTkEntry(f_row, width=410)
        self.entry_path.insert(0, config.download_dir)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(f_row, text="Browse...", width=80, command=self._browse_dir)
        btn_browse.pack(side="right")

        # 4. Buttons: Start Download, Download Later, Cancel
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=pad, pady=(16, 12))

        btn_start = ctk.CTkButton(
            btn_box,
            text="⚡ Start Download",
            fg_color="#1f538d",
            hover_color="#14375e",
            font=ctk.CTkFont(weight="bold"),
            width=140,
            command=lambda: self._submit(auto_start=True)
        )
        btn_start.pack(side="right", padx=(8, 0))

        btn_later = ctk.CTkButton(
            btn_box,
            text="⏳ Download Later",
            fg_color="#333333",
            hover_color="#444444",
            width=120,
            command=lambda: self._submit(auto_start=False)
        )
        btn_later.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Cancel",
            width=80,
            fg_color="gray",
            hover_color="#555555",
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def _on_url_change(self, event=None):
        url = self.entry_url.get().strip()
        if url:
            name = url.split("?")[0].rstrip("/").split("/")[-1]
            cat = config.detect_category(name)
            if cat in ["Video", "Audio", "Compressed", "Document", "Program"]:
                self.cat_var.set(cat)

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.entry_path.get())
        if d:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, d)

    def _submit(self, auto_start=True):
        url = self.entry_url.get().strip()
        path = self.entry_path.get().strip()
        if not url:
            messagebox.showwarning("Nexus DM", "Please enter a valid URL.")
            return
        self.on_submit(url, path, auto_start=auto_start)
        self.destroy()


class OptionsDialog(ctk.CTkToplevel):
    """
    IDM-style Configuration & Options Dialog.
    """
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.title("Configuration & Options - Nexus DM")
        self.geometry("520x400")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.on_save = on_save

        self._setup_ui()

    def _setup_ui(self):
        pad = 18

        ctk.CTkLabel(self, text="Nexus DM Configuration", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=pad, pady=(16, 10))

        # Default Download Directory
        ctk.CTkLabel(self, text="Default Download Directory:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=pad, pady=(6, 2))
        f_dir = ctk.CTkFrame(self, fg_color="transparent")
        f_dir.pack(fill="x", padx=pad, pady=2)

        self.entry_dir = ctk.CTkEntry(f_dir, width=380)
        self.entry_dir.insert(0, config.download_dir)
        self.entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(f_dir, text="Browse...", width=80, command=self._browse)
        btn_browse.pack(side="right")

        # Maximum Connections per Download
        ctk.CTkLabel(self, text="Max Connections per Download (Segmented Speed):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=pad, pady=(12, 2))
        self.conn_var = ctk.StringVar(value=str(config.max_connections))
        conn_opts = ["4", "8", "16", "24", "32"]
        self.conn_menu = ctk.CTkOptionMenu(self, values=conn_opts, variable=self.conn_var, width=120)
        self.conn_menu.pack(anchor="w", padx=pad, pady=2)

        # UI Theme
        ctk.CTkLabel(self, text="Application Theme:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=pad, pady=(12, 2))
        self.theme_var = ctk.StringVar(value=config.theme.capitalize())
        self.theme_menu = ctk.CTkOptionMenu(self, values=["Dark", "Light"], variable=self.theme_var, width=120)
        self.theme_menu.pack(anchor="w", padx=pad, pady=2)

        # Toggles
        self.chk_dialog = ctk.CTkCheckBox(self, text="Show IDM-style progress popup on download start")
        if config.show_progress_dialog:
            self.chk_dialog.select()
        self.chk_dialog.pack(anchor="w", padx=pad, pady=(14, 6))

        # Buttons
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", side="bottom", padx=pad, pady=16)

        btn_ok = ctk.CTkButton(btn_box, text="OK / Apply", width=100, command=self._apply)
        btn_ok.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(btn_box, text="Cancel", width=80, fg_color="gray", command=self.destroy)
        btn_cancel.pack(side="right")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.entry_dir.get())
        if d:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, d)

    def _apply(self):
        config.download_dir = self.entry_dir.get().strip()
        config.max_connections = int(self.conn_var.get())
        config.theme = self.theme_var.get().lower()
        config.show_progress_dialog = bool(self.chk_dialog.get())
        config.save()
        ctk.set_appearance_mode(config.theme)
        self.on_save()
        self.destroy()


class MainWindow(ctk.CTk):
    """
    Main Nexus DM Application Dashboard with true IDM Look, Layout, and Features.
    """
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode(config.theme)
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{APP_VERSION} - Elite High-Speed Download Manager")
        self.geometry("1060x640")
        self.minsize(860, 520)

        self.active_category = "All"
        self.active_dialogs: Dict[str, ProgressDialog] = {}
        self.cached_downloads = []

        self._setup_window_icon()
        self._setup_menu_bar()
        self._setup_ui()
        self._setup_context_menu()
        self._setup_keybindings()

        # Engine listeners and timer refresh
        engine.add_global_listener(self._on_engine_event)
        self._refresh_download_list()
        self.after(1000, self._periodic_ui_update)

    def _setup_window_icon(self):
        ico = get_icon_path("app.ico")
        if ico:
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

    def _setup_menu_bar(self):
        """Top classic Win32/Tkinter Menu Bar."""
        menubar = tk.Menu(self)

        # Tasks Menu
        menu_tasks = tk.Menu(menubar, tearoff=0)
        menu_tasks.add_command(label="Add new download...\tCtrl+N", command=self._show_add_url)
        menu_tasks.add_separator()
        menu_tasks.add_command(label="Open Downloads folder", command=self._open_downloads_dir)
        menu_tasks.add_separator()
        menu_tasks.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="Tasks", menu=menu_tasks)

        # File Menu
        menu_file = tk.Menu(menubar, tearoff=0)
        menu_file.add_command(label="Stop download", command=self._action_stop_selected)
        menu_file.add_command(label="Resume download", command=self._action_resume_selected)
        menu_file.add_command(label="Delete\tDel", command=self._action_delete_selected)
        menu_file.add_command(label="Redownload", command=self._action_redownload_selected)
        menu_file.add_separator()
        menu_file.add_command(label="Open file\tEnter", command=self._action_open_selected)
        menu_file.add_command(label="Open folder", command=self._action_open_folder_selected)
        menubar.add_cascade(label="File", menu=menu_file)

        # Downloads Menu
        menu_dl = tk.Menu(menubar, tearoff=0)
        menu_dl.add_command(label="Pause", command=self._action_stop_selected)
        menu_dl.add_command(label="Resume", command=self._action_resume_selected)
        menu_dl.add_command(label="Stop all", command=self._action_stop_all)
        menu_dl.add_command(label="Delete all completed", command=self._action_delete_completed)
        menu_dl.add_separator()
        menu_dl.add_command(label="Options...", command=self._show_options)
        menubar.add_cascade(label="Downloads", menu=menu_dl)

        # View Menu
        menu_view = tk.Menu(menubar, tearoff=0)
        menu_view.add_command(label="Refresh List\tF5", command=self._refresh_download_list)
        menu_view.add_separator()
        menu_view.add_command(label="Toggle Dark / Light Mode", command=self._toggle_theme)
        menubar.add_cascade(label="View", menu=menu_view)

        # Help Menu
        menu_help = tk.Menu(menubar, tearoff=0)
        menu_help.add_command(label="About Nexus DM...", command=self._show_about)
        menubar.add_cascade(label="Help", menu=menu_help)

        self.config(menu=menubar)

    def _setup_ui(self):
        # 1. Authentic IDM 3D Toolbar Frame
        self.toolbar = ctk.CTkFrame(self, height=68, corner_radius=0, fg_color=("#e6e6e6", "#23272e"))
        self.toolbar.pack(fill="x", side="top")

        tb_buttons = [
            ("Add URL", "tb_add_url.png", self._show_add_url),
            ("Resume", "tb_resume.png", self._action_resume_selected),
            ("Stop", "tb_stop.png", self._action_stop_selected),
            ("Stop All", "tb_stop_all.png", self._action_stop_all),
            ("Delete", "tb_delete.png", self._action_delete_selected),
            ("Delete Comp.", "tb_delete_completed.png", self._action_delete_completed),
            ("Options", "tb_options.png", self._show_options),
            ("Scheduler", "tb_scheduler.png", lambda: messagebox.showinfo("Scheduler", "Queue Scheduler is active (running 24/7).")),
            ("Start Queue", "tb_start_queue.png", self._action_start_queue),
            ("Stop Queue", "tb_stop_queue.png", self._action_stop_all),
            ("Grabber", "tb_grabber.png", lambda: messagebox.showinfo("Site Grabber", "Nexus DM Video Grabber is active on all browser video players!")),
        ]

        for label, icon_file, cmd in tb_buttons:
            img = get_ctk_icon(icon_file, size=(32, 28))
            btn = ctk.CTkButton(
                self.toolbar,
                text=label,
                image=img,
                compound="top",
                width=68,
                height=56,
                fg_color="transparent",
                hover_color=("#d0d0d0", "#333942"),
                text_color=("#111111", "#e0e0e0"),
                font=ctk.CTkFont(size=10, weight="bold"),
                command=cmd
            )
            btn.pack(side="left", padx=2, pady=4)

        # Right side status indicator
        self.lbl_bridge = ctk.CTkLabel(
            self.toolbar,
            text="🟢 Extension Bridge: Online",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#5cb85c"
        )
        self.lbl_bridge.pack(side="right", padx=(6, 16))

        # 2. Main Content Split (Left Sidebar Categories + Right Downloads Table)
        main_body = ctk.CTkFrame(self, fg_color="transparent")
        main_body.pack(fill="both", expand=True)

        # Left Sidebar (Categories)
        sidebar = ctk.CTkFrame(main_body, width=190, corner_radius=0, fg_color=("#ebebeb", "#1b1d23"))
        sidebar.pack(side="left", fill="y", padx=0, pady=0)

        ctk.CTkLabel(
            sidebar,
            text="CATEGORIES",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray"
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.categories_data = [
            ("All Downloads", "All", "📥"),
            ("Unfinished", "Unfinished", "⏳"),
            ("Finished", "Finished", "✅"),
            ("Compressed", "Compressed", "📦"),
            ("Documents", "Document", "📄"),
            ("Music / Audio", "Audio", "🎵"),
            ("Programs", "Program", "💻"),
            ("Video", "Video", "🎬"),
            ("Other", "Other", "📁"),
        ]

        self.cat_buttons = {}
        for label, cat_key, emoji in self.categories_data:
            btn = ctk.CTkButton(
                sidebar,
                text=f"{emoji}  {label}",
                anchor="w",
                height=30,
                corner_radius=4,
                fg_color="#1f538d" if cat_key == "All" else "transparent",
                hover_color=("#dcdcdc", "#2d3139"),
                text_color=("#111111", "#ffffff"),
                font=ctk.CTkFont(size=11),
                command=lambda k=cat_key: self._select_category(k)
            )
            btn.pack(fill="x", padx=6, pady=1)
            self.cat_buttons[cat_key] = btn

        # Right Area: Downloads Grid
        right_container = ctk.CTkFrame(main_body, fg_color="transparent")
        right_container.pack(side="right", fill="both", expand=True, padx=6, pady=6)

        # Style TTK Treeview to match current theme
        self._style_treeview()

        tree_scroll_y = ttk.Scrollbar(right_container, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(right_container, orient="horizontal")

        columns = ("filename", "size", "status", "time_left", "speed", "last_try", "category")
        self.tree = ttk.Treeview(
            right_container,
            columns=columns,
            show="headings",
            selectmode="extended",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        # Configure Headings and Columns
        self.tree.heading("filename", text="File Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.heading("time_left", text="Time Left", anchor="center")
        self.tree.heading("speed", text="Transfer Rate", anchor="e")
        self.tree.heading("last_try", text="Last Try Date", anchor="w")
        self.tree.heading("category", text="Category", anchor="center")

        self.tree.column("filename", width=300, minwidth=180, anchor="w")
        self.tree.column("size", width=95, minwidth=70, anchor="e")
        self.tree.column("status", width=110, minwidth=80, anchor="w")
        self.tree.column("time_left", width=90, minwidth=70, anchor="center")
        self.tree.column("speed", width=105, minwidth=80, anchor="e")
        self.tree.column("last_try", width=130, minwidth=100, anchor="w")
        self.tree.column("category", width=90, minwidth=70, anchor="center")

        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # 3. Bottom Status Bar
        self.statusbar = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color=("#e6e6e6", "#1c1e22"))
        self.statusbar.pack(fill="x", side="bottom")

        self.lbl_status_left = ctk.CTkLabel(
            self.statusbar,
            text=f"Ready • Save Dir: {config.download_dir}",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.lbl_status_left.pack(side="left", padx=12)

        self.lbl_speed_total = ctk.CTkLabel(
            self.statusbar,
            text="Total Speed: 0.00 B/s",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#2b7de9"
        )
        self.lbl_speed_total.pack(side="right", padx=14)

    def _style_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        is_dark = (config.theme == "dark")

        bg = "#1e1e1e" if is_dark else "#ffffff"
        fg = "#f0f0f0" if is_dark else "#111111"
        hdr_bg = "#2b2b2b" if is_dark else "#f0f0f0"
        hdr_fg = "#ffffff" if is_dark else "#222222"
        select_bg = "#1f538d" if is_dark else "#0078d7"

        style.configure(
            "Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            rowheight=26,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background=hdr_bg,
            foreground=hdr_fg,
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        style.map(
            "Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", "#ffffff")]
        )

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Resume Download", command=self._action_resume_selected)
        self.context_menu.add_command(label="Stop / Pause", command=self._action_stop_selected)
        self.context_menu.add_command(label="Redownload", command=self._action_redownload_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open File", command=self._action_open_selected)
        self.context_menu.add_command(label="Open Folder", command=self._action_open_folder_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy Download Link", command=self._action_copy_link_selected)
        self.context_menu.add_command(label="Delete", command=self._action_delete_selected)

    def _setup_keybindings(self):
        self.bind("<Control-n>", lambda e: self._show_add_url())
        self.bind("<F5>", lambda e: self._refresh_download_list())
        self.bind("<Delete>", lambda e: self._action_delete_selected())
        self.bind("<Return>", lambda e: self._action_open_selected())

    def _on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _on_tree_double_click(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        task_id = selected[0]
        item = storage.get_download(task_id)
        if not item:
            return

        if item["status"] == DownloadState.COMPLETED:
            self._action_open_selected()
        else:
            task = engine.get_task(task_id)
            if task:
                self._open_progress_dialog(task)
            else:
                self._action_resume_selected()

    def _select_category(self, cat_key: str):
        self.active_category = cat_key
        for k, btn in self.cat_buttons.items():
            if k == cat_key:
                btn.configure(fg_color="#1f538d", text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=("#111111", "#ffffff"))
        self._refresh_download_list()

    def _refresh_download_list(self):
        self.cached_downloads = storage.get_all_downloads()
        self.tree.delete(*self.tree.get_children())

        active_count = 0
        total_speed = 0.0

        for item in self.cached_downloads:
            task_id = item["id"]
            cat = item.get("category", "Other")
            status = item.get("status", "queued")

            # Check if active task in engine
            active_task = engine.get_task(task_id)
            if active_task and active_task.state == DownloadState.DOWNLOADING:
                active_count += 1
                total_speed += active_task.speed

            # Filter by Category
            if self.active_category == "All":
                pass
            elif self.active_category == "Unfinished" and status in [DownloadState.COMPLETED]:
                continue
            elif self.active_category == "Finished" and status != DownloadState.COMPLETED:
                continue
            elif self.active_category in ["Compressed", "Document", "Audio", "Program", "Video", "Other"] and cat != self.active_category:
                continue

            # Format fields
            down = item.get("downloaded_bytes", 0)
            total = item.get("total_bytes", 0)
            size_str = format_bytes(total) if total > 0 else (format_bytes(down) if down > 0 else "Unknown")

            if active_task and active_task.state == DownloadState.DOWNLOADING:
                status_str = f"Downloading ({active_task.progress_percent:.1f}%)"
                speed_str = active_task.speed_formatted
                time_left_str = active_task.eta_formatted
            else:
                status_str = status.capitalize()
                speed_str = ""
                time_left_str = "--:--" if status != DownloadState.COMPLETED else "00:00:00"

            last_try = item.get("created_at", "")[:16]

            self.tree.insert(
                "",
                "end",
                iid=task_id,
                values=(item["filename"], size_str, status_str, time_left_str, speed_str, last_try, cat)
            )

        self.lbl_status_left.configure(text=f"Total: {len(self.cached_downloads)} downloads ({active_count} active) • Save Dir: {config.download_dir}")
        self.lbl_speed_total.configure(text=f"Total Speed: {format_speed(total_speed)}")

    def _periodic_ui_update(self):
        # Update live values in treeview for active downloads without redrawing whole tree
        total_speed = 0.0
        active_count = 0

        for task_id, task in list(engine.tasks.items()):
            if task.state == DownloadState.DOWNLOADING:
                active_count += 1
                total_speed += task.speed

            if self.tree.exists(task_id):
                item = storage.get_download(task_id) or {}
                size_str = format_bytes(task.total_bytes) if task.total_bytes > 0 else format_bytes(task.downloaded_bytes)
                status_str = f"Downloading ({task.progress_percent:.1f}%)" if task.state == DownloadState.DOWNLOADING else task.state.capitalize()
                self.tree.set(task_id, "size", size_str)
                self.tree.set(task_id, "status", status_str)
                self.tree.set(task_id, "speed", task.speed_formatted if task.state == DownloadState.DOWNLOADING else "")
                self.tree.set(task_id, "time_left", task.eta_formatted if task.state == DownloadState.DOWNLOADING else "")

        self.lbl_speed_total.configure(text=f"Total Speed: {format_speed(total_speed)}")
        self.after(800, self._periodic_ui_update)

    def _on_engine_event(self, event_type: str, task):
        def _handle():
            if event_type == "created":
                if config.show_progress_dialog and task.id not in self.active_dialogs:
                    self._open_progress_dialog(task)
                self._refresh_download_list()
            elif event_type in ["completed", "failed", "paused", "downloading"]:
                self._refresh_download_list()
        self.after(0, _handle)

    def _open_progress_dialog(self, task):
        if task.id in self.active_dialogs:
            try:
                dlg = self.active_dialogs[task.id]
                dlg.deiconify()
                dlg.lift()
                dlg.attributes("-topmost", True)
                dlg.focus_force()
                return
            except Exception:
                pass

        try:
            self.deiconify()
            self.lift()
        except Exception:
            pass

        dlg = ProgressDialog(self, task, on_close=lambda *args: self.active_dialogs.pop(task.id, None))
        self.active_dialogs[task.id] = dlg
        dlg.lift()
        dlg.attributes("-topmost", True)
        dlg.focus_force()

    def _show_add_url(self):
        AddUrlDialog(self, on_submit=self._on_add_url_submit)

    def _on_add_url_submit(self, url: str, path: str, auto_start=True):
        task = engine.create_task(url, save_dir=path, auto_start=auto_start)
        if config.show_progress_dialog and auto_start:
            self._open_progress_dialog(task)
        self._refresh_download_list()

    def _show_options(self):
        OptionsDialog(self, on_save=self._on_options_saved)

    def _on_options_saved(self):
        self._style_treeview()
        self._refresh_download_list()

    def _toggle_theme(self):
        new_theme = "light" if config.theme == "dark" else "dark"
        config.theme = new_theme
        config.save()
        ctk.set_appearance_mode(new_theme)
        self._style_treeview()
        self.toolbar.configure(fg_color=("#e6e6e6", "#23272e"))
        self._refresh_download_list()

    def _get_selected_ids(self) -> List[str]:
        return list(self.tree.selection())

    def _action_resume_selected(self):
        ids = self._get_selected_ids()
        for task_id in ids:
            task = engine.resume_task(task_id)
            if task and config.show_progress_dialog:
                self._open_progress_dialog(task)
        self._refresh_download_list()

    def _action_stop_selected(self):
        ids = self._get_selected_ids()
        for task_id in ids:
            engine.pause_task(task_id)
        self._refresh_download_list()

    def _action_stop_all(self):
        for task_id in list(engine.tasks.keys()):
            engine.pause_task(task_id)
        self._refresh_download_list()

    def _action_start_queue(self):
        for item in self.cached_downloads:
            if item["status"] in [DownloadState.PAUSED, DownloadState.QUEUED]:
                engine.resume_task(item["id"])
        self._refresh_download_list()

    def _action_delete_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        ans = messagebox.askyesno("Nexus DM", f"Are you sure you want to delete {len(ids)} selected download(s)?")
        if not ans:
            return
        for task_id in ids:
            engine.cancel_task(task_id)
            storage.delete_download(task_id)
        self._refresh_download_list()

    def _action_delete_completed(self):
        completed = [item for item in self.cached_downloads if item["status"] == DownloadState.COMPLETED]
        if not completed:
            messagebox.showinfo("Nexus DM", "No completed downloads to delete.")
            return
        ans = messagebox.askyesno("Nexus DM", f"Delete all {len(completed)} completed download records?")
        if ans:
            for item in completed:
                storage.delete_download(item["id"])
            self._refresh_download_list()

    def _action_redownload_selected(self):
        ids = self._get_selected_ids()
        for task_id in ids:
            item = storage.get_download(task_id)
            if item:
                engine.cancel_task(task_id)
                storage.delete_download(task_id)
                folder = os.path.dirname(item.get("file_path", config.download_dir))
                engine.create_task(item["url"], filename=item["filename"], save_dir=folder, auto_start=True)
        self._refresh_download_list()

    def _action_open_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        item = storage.get_download(ids[0])
        if not item:
            return

        fpath_str = item.get("file_path", "")
        fpath = Path(fpath_str) if fpath_str else (Path(config.download_dir) / item.get("filename", ""))

        if fpath.exists() and fpath.is_file() and os.path.getsize(str(fpath)) > 0:
            try:
                os.startfile(str(fpath))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")
        else:
            ans = messagebox.askyesno(
                "File Not Found",
                f"The downloaded file was not found at:\n{fpath}\n\nWould you like to re-download it now?"
            )
            if ans:
                self._action_redownload_selected()

    def _action_open_folder_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            self._open_downloads_dir()
            return
        item = storage.get_download(ids[0])
        fpath_str = item.get("file_path", "") if item else ""
        folder = os.path.dirname(fpath_str) if fpath_str else config.download_dir
        if not os.path.exists(folder):
            folder = config.download_dir
        if Path(folder).exists():
            subprocess.Popen(f'explorer "{folder}"')

    def _action_copy_link_selected(self):
        ids = self._get_selected_ids()
        if not ids:
            return
        item = storage.get_download(ids[0])
        if item and item.get("url"):
            self.clipboard_clear()
            self.clipboard_append(item["url"])
            messagebox.showinfo("Nexus DM", "Download link copied to clipboard!")

    def _open_downloads_dir(self):
        d = config.download_dir
        if Path(d).exists():
            subprocess.Popen(f'explorer "{d}"')

    def _show_about(self):
        msg = f"{APP_NAME} v{APP_VERSION}\n" \
              f"High-Speed Segmented Multi-Connection Download Manager\n" \
              f"Featuring Authentic IDM Aesthetics & Full Freedom.\n\n" \
              f"Unlimited Speed • 32 Parallel Connections • yt-dlp Video Grabber\n" \
              f"© 2026 Nexus DM Project."
        messagebox.showinfo(f"About {APP_NAME}", msg)
