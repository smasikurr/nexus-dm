"""
Nexus DM (NDM) - Local REST API Server
Bridge between the Browser Extension and the Desktop Download Engine.
Runs on 127.0.0.1:45678 with full CORS support.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional

from .config import config, APP_NAME, APP_VERSION
from .engine import engine
from .storage import storage

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class NexusApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress noisy default HTTP request logging in console
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/ping":
            self._send_json(200, {
                "status": "ok",
                "app": APP_NAME,
                "version": APP_VERSION,
                "port": config.port,
                "download_dir": config.download_dir
            })
        elif path == "/api/downloads":
            items = storage.get_all_downloads()
            self._send_json(200, {"success": True, "downloads": items})
        elif path == "/api/active":
            active_info = [t.get_info() for t in engine.tasks.values()]
            self._send_json(200, {"success": True, "active": active_info})
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if path == "/api/download":
            url = body.get("url")
            if not url:
                self._send_json(400, {"error": "URL is required"})
                return

            filename = body.get("filename")
            referer = body.get("referer")
            cookies = body.get("cookies")
            user_agent = body.get("user_agent")

            headers = {}
            if referer:
                headers["Referer"] = referer
            if cookies:
                headers["Cookie"] = cookies
            if user_agent:
                headers["User-Agent"] = user_agent

            task = engine.create_task(
                url=url,
                filename=filename,
                headers=headers if headers else None,
                auto_start=config.auto_start_downloads
            )

            self._send_json(200, {
                "success": True,
                "task_id": task.id,
                "filename": task.filename,
                "status": task.status
            })

        elif path == "/api/pause":
            task_id = body.get("id")
            if task_id:
                engine.pause_task(task_id)
                self._send_json(200, {"success": True, "id": task_id})
            else:
                self._send_json(400, {"error": "Missing task id"})

        elif path == "/api/resume":
            task_id = body.get("id")
            if task_id:
                engine.resume_task(task_id)
                self._send_json(200, {"success": True, "id": task_id})
            else:
                self._send_json(400, {"error": "Missing task id"})

        elif path == "/api/cancel":
            task_id = body.get("id")
            if task_id:
                engine.cancel_task(task_id)
                self._send_json(200, {"success": True, "id": task_id})
            else:
                self._send_json(400, {"error": "Missing task id"})

        else:
            self._send_json(404, {"error": "Not Found"})

class ApiServer:
    def __init__(self, port: int = 45678):
        self.port = port
        self.server: Optional[ThreadedHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        if self._running:
            return
        try:
            self.server = ThreadedHTTPServer(("127.0.0.1", self.port), NexusApiHandler)
            self._running = True
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"[Nexus DM Server] Listening on http://127.0.0.1:{self.port}")
        except Exception as e:
            print(f"[Nexus DM Server] Failed to start server on port {self.port}: {e}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self._running = False
            print("[Nexus DM Server] Stopped.")

server = ApiServer(config.port)
