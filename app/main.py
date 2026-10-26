"""
Nexus DM (NDM) - Application Launcher
Starts the Local HTTP REST Bridge and Desktop GUI.
"""

import sys
import os
import argparse
from pathlib import Path

import sys
import os
import argparse
from pathlib import Path

# Ensure paths are configured for both direct python run and PyInstaller bundle
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
else:
    root_dir = str(Path(__file__).resolve().parent.parent)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

app_dir = str(Path(__file__).resolve().parent)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

try:
    from app.config import APP_NAME, APP_VERSION
    from app.server import server
    from app.engine import engine
    from app.gui import MainWindow
except (ImportError, ModuleNotFoundError):
    from config import APP_NAME, APP_VERSION
    from server import server
    from engine import engine
    from gui import MainWindow

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION} - Elite Download Manager")
    parser.add_argument("--url", help="Download a URL directly on startup")
    parser.add_argument("--headless", action="store_true", help="Run only background REST API server")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to system tray")
    args = parser.parse_args()

    # 1. Start Local API Server
    server.start()

    # 2. Check if direct download requested via CLI
    if args.url:
        engine.create_task(args.url, auto_start=True)

    if args.headless:
        print("[Nexus DM] Running in headless server mode. Press Ctrl+C to exit.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
            sys.exit(0)

    # 3. Launch Modern Desktop GUI
    app = MainWindow()
    if args.minimized:
        app.withdraw()
    try:
        app.mainloop()
    finally:
        server.stop()

if __name__ == "__main__":
    main()
