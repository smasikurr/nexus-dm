"""
Unit and Integration Tests for Local API Server
"""

import sys
import time
import unittest
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.server import ApiServer

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 45689
        cls.server = ApiServer(port=cls.test_port)
        cls.server.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.5)

    def test_ping_endpoint(self):
        url = f"http://127.0.0.1:{self.test_port}/api/ping"
        res = requests.get(url, timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("app"), "Nexus DM")
        self.assertEqual(res.headers.get("Access-Control-Allow-Origin"), "*")

    def test_download_endpoint(self):
        url = f"http://127.0.0.1:{self.test_port}/api/download"
        payload = {
            "url": "https://speed.hetzner.de/100MB.bin",
            "filename": "hetzner_test.bin"
        }
        res = requests.post(url, json=payload, timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIsNotNone(data.get("task_id"))

    def test_downloads_list(self):
        url = f"http://127.0.0.1:{self.test_port}/api/downloads"
        res = requests.get(url, timeout=5)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIsInstance(data.get("downloads"), list)

if __name__ == "__main__":
    unittest.main()
