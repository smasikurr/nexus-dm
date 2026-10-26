"""
Nexus DM (NDM) - SQLite Storage Manager
"""

import sqlite3
import datetime
import os
from pathlib import Path
from typing import List, Dict, Optional
try:
    from .config import get_app_data_dir
except (ImportError, ValueError):
    try:
        from app.config import get_app_data_dir
    except (ImportError, ValueError):
        from config import get_app_data_dir

class Storage:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = str(get_app_data_dir() / "downloads.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    total_bytes INTEGER DEFAULT 0,
                    downloaded_bytes INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'queued',
                    category TEXT DEFAULT 'Other',
                    speed REAL DEFAULT 0.0,
                    eta TEXT DEFAULT '',
                    error_message TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            conn.commit()

    def add_download(self, item: Dict) -> Dict:
        now = datetime.datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO downloads 
                (id, url, filename, file_path, total_bytes, downloaded_bytes, status, category, speed, eta, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["id"],
                item["url"],
                item["filename"],
                item["file_path"],
                item.get("total_bytes", 0),
                item.get("downloaded_bytes", 0),
                item.get("status", "queued"),
                item.get("category", "Other"),
                item.get("speed", 0.0),
                item.get("eta", ""),
                item.get("error_message", ""),
                now
            ))
            conn.commit()
        return item

    def update_progress(self, download_id: str, downloaded_bytes: int, total_bytes: int, speed: float, eta: str):
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE downloads 
                SET downloaded_bytes = ?, total_bytes = ?, speed = ?, eta = ?
                WHERE id = ?
            """, (downloaded_bytes, total_bytes, speed, eta, download_id))
            conn.commit()

    def update_status(self, download_id: str, status: str, error_message: str = ""):
        now = datetime.datetime.now().isoformat() if status == "completed" else None
        with self._get_connection() as conn:
            if status == "completed":
                conn.execute("""
                    UPDATE downloads 
                    SET status = ?, error_message = ?, completed_at = ?, speed = 0.0, eta = ''
                    WHERE id = ?
                """, (status, error_message, now, download_id))
            else:
                conn.execute("""
                    UPDATE downloads 
                    SET status = ?, error_message = ?
                    WHERE id = ?
                """, (status, error_message, download_id))
            conn.commit()

    def get_download(self, download_id: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM downloads WHERE id = ?", (download_id,)).fetchone()
            return dict(row) if row else None

    def get_by_url(self, url: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM downloads WHERE url = ? ORDER BY created_at DESC LIMIT 1", (url,)).fetchone()
            return dict(row) if row else None

    def find_completed_by_url(self, url: str) -> Optional[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM downloads WHERE url = ? AND status = 'completed' ORDER BY created_at DESC", (url,)).fetchall()
            for r in rows:
                item = dict(r)
                fp = item.get("file_path")
                if fp and os.path.exists(fp) and os.path.getsize(fp) > 0:
                    return item
            return None

    def get_all_downloads(self) -> List[Dict]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM downloads ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_downloads_by_category(self, category: str) -> List[Dict]:
        with self._get_connection() as conn:
            if category.lower() == "all":
                return self.get_all_downloads()
            rows = conn.execute("SELECT * FROM downloads WHERE category = ? ORDER BY created_at DESC", (category,)).fetchall()
            return [dict(r) for r in rows]

    def delete_download(self, download_id: str, delete_file: bool = False) -> bool:
        item = self.get_download(download_id)
        if not item:
            return False

        if delete_file:
            path = Path(item["file_path"])
            if path.exists():
                try:
                    path.unlink()
                except Exception as e:
                    print(f"[Storage] Failed to delete file {path}: {e}")

        with self._get_connection() as conn:
            conn.execute("DELETE FROM downloads WHERE id = ?", (download_id,))
            conn.commit()
        return True

storage = Storage()
