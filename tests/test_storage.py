"""
Unit Tests for Storage Manager
"""

import os
import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage import Storage

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.storage = Storage(db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.unlink(self.temp_db.name)
            except Exception:
                pass

    def test_add_and_get_download(self):
        item = {
            "id": "test-123",
            "url": "https://example.com/test.zip",
            "filename": "test.zip",
            "file_path": "C:/Downloads/test.zip",
            "total_bytes": 1024000,
            "category": "Compressed"
        }
        self.storage.add_download(item)
        fetched = self.storage.get_download("test-123")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["filename"], "test.zip")
        self.assertEqual(fetched["category"], "Compressed")

    def test_update_progress(self):
        item = {
            "id": "prog-1",
            "url": "https://example.com/video.mp4",
            "filename": "video.mp4",
            "file_path": "C:/Downloads/video.mp4",
            "category": "Video"
        }
        self.storage.add_download(item)
        self.storage.update_progress("prog-1", downloaded_bytes=500000, total_bytes=1000000, speed=1024.5, eta="00:15")
        
        fetched = self.storage.get_download("prog-1")
        self.assertEqual(fetched["downloaded_bytes"], 500000)
        self.assertEqual(fetched["total_bytes"], 1000000)
        self.assertEqual(fetched["eta"], "00:15")

    def test_filter_by_category(self):
        self.storage.add_download({"id": "v1", "url": "a", "filename": "v.mp4", "file_path": "p", "category": "Video"})
        self.storage.add_download({"id": "z1", "url": "b", "filename": "z.zip", "file_path": "p", "category": "Compressed"})
        
        videos = self.storage.get_downloads_by_category("Video")
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["id"], "v1")

    def test_delete_download(self):
        self.storage.add_download({"id": "del-1", "url": "a", "filename": "d.mp4", "file_path": "p"})
        self.assertTrue(self.storage.delete_download("del-1"))
        self.assertIsNone(self.storage.get_download("del-1"))

if __name__ == "__main__":
    unittest.main()
