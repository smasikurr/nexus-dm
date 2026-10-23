"""
Unit and Integration Tests for Download Engine and Multi-Part Chunk Downloader
"""

import os
import sys
import time
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine import DownloadEngine, DownloadTask, DownloadState, format_bytes, format_speed, format_eta

class RangeTestHandler(BaseHTTPRequestHandler):
    # Generates a predictable 1 MB payload for testing range requests
    PAYLOAD_SIZE = 1024 * 512 # 512 KB
    PAYLOAD = b"NEXUS_DM_TEST_DATA_" * (PAYLOAD_SIZE // 19 + 1)
    PAYLOAD = PAYLOAD[:PAYLOAD_SIZE]

    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.PAYLOAD)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            parts = range_header.split("=")[1].split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else len(self.PAYLOAD) - 1
            chunk = self.PAYLOAD[start:end+1]

            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.PAYLOAD)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(self.PAYLOAD)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(self.PAYLOAD)

class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 45699
        cls.mock_server = HTTPServer(("127.0.0.1", cls.test_port), RangeTestHandler)
        cls.server_thread = threading.Thread(target=cls.mock_server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.shutdown()
        cls.mock_server.server_close()

    def test_formatters(self):
        self.assertEqual(format_bytes(500), "500.00 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_speed(2048), "2.00 KB/s")
        self.assertEqual(format_eta(65), "01:05")

    def test_segmented_download(self):
        test_url = f"http://127.0.0.1:{self.test_port}/test_file.bin"
        temp_dir = tempfile.mkdtemp()
        save_file = os.path.join(temp_dir, "test_file.bin")

        engine = DownloadEngine()
        task = engine.create_task(url=test_url, save_path=save_file, auto_start=True)

        # Wait for completion
        for _ in range(50):
            if task.status in [DownloadState.COMPLETED, DownloadState.FAILED]:
                break
            time.sleep(0.1)

        self.assertEqual(task.status, DownloadState.COMPLETED)
        self.assertTrue(os.path.exists(save_file))
        self.assertEqual(os.path.getsize(save_file), RangeTestHandler.PAYLOAD_SIZE)

        with open(save_file, "rb") as f:
            downloaded_bytes = f.read()
        self.assertEqual(downloaded_bytes, RangeTestHandler.PAYLOAD)

        # Cleanup
        try:
            os.unlink(save_file)
            os.rmdir(temp_dir)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
