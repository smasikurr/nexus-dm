"""
Nexus DM (NDM) - Configuration Manager
"""

import os
import json
from pathlib import Path

APP_NAME = "Nexus DM"
APP_VERSION = "1.0.0"
DEFAULT_PORT = 45678

# Extension mapping to categories
CATEGORY_EXTENSIONS = {
    "Video": [".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".ts", ".m3u8"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".opus"],
    "Compressed": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".iso", ".xz"],
    "Document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".epub"],
    "Program": [".exe", ".msi", ".apk", ".bat", ".cmd", ".ps1", ".dmg", ".bin"]
}

def get_default_download_dir():
    # Prefer D:\Downloads if D drive exists, otherwise standard user Downloads
    d_downloads = Path("D:/Downloads")
    if d_downloads.parent.exists():
        try:
            d_downloads.mkdir(parents=True, exist_ok=True)
            return str(d_downloads)
        except Exception:
            pass
    
    user_downloads = Path.home() / "Downloads"
    user_downloads.mkdir(parents=True, exist_ok=True)
    return str(user_downloads)

def get_app_data_dir():
    app_data = Path(os.environ.get("APPDATA", str(Path.home()))) / "NexusDM"
    app_data.mkdir(parents=True, exist_ok=True)
    return app_data

class Config:
    def __init__(self):
        self.config_file = get_app_data_dir() / "settings.json"
        self.download_dir = get_default_download_dir()
        self.port = DEFAULT_PORT
        self.max_connections = 16
        self.auto_start_downloads = True
        self.show_progress_dialog = True
        self.theme = "dark" # dark or light
        self.speed_limit_kb = 0 # 0 = unlimited
        self.load()

    def load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.download_dir = data.get("download_dir", self.download_dir)
                    self.port = data.get("port", self.port)
                    self.max_connections = data.get("max_connections", self.max_connections)
                    self.auto_start_downloads = data.get("auto_start_downloads", self.auto_start_downloads)
                    self.show_progress_dialog = data.get("show_progress_dialog", self.show_progress_dialog)
                    self.theme = data.get("theme", self.theme)
                    self.speed_limit_kb = data.get("speed_limit_kb", self.speed_limit_kb)
            except Exception as e:
                print(f"[Config] Error loading config: {e}")

    def save(self):
        try:
            data = {
                "download_dir": self.download_dir,
                "port": self.port,
                "max_connections": self.max_connections,
                "auto_start_downloads": self.auto_start_downloads,
                "show_progress_dialog": self.show_progress_dialog,
                "theme": self.theme,
                "speed_limit_kb": self.speed_limit_kb
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def detect_category(self, filename: str) -> str:
        ext = os.path.splitext(filename.lower())[1]
        for cat, extensions in CATEGORY_EXTENSIONS.items():
            if ext in extensions:
                return cat
        return "Other"

config = Config()
