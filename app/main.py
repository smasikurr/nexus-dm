"""
Nexus DM (NDM) - Application Launcher
Starts the Local HTTP REST Bridge and Desktop GUI.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import APP_NAME, APP_VERSION
from app.server import server
from app.engine import engine
from app.gui import MainWindow

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION} - Elite Download Manager")
    parser.add_argument("--url", help="Download a URL directly on startup")
    parser.add_argument("--headless", action="store_true", help="Run only background REST API server")
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
    try:
        app.mainloop()
    finally:
        server.stop()

if __name__ == "__main__":
    main()
