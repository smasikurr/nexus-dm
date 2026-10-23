"""
Nexus DM (NDM) - Entry Point Script
Used for direct running and PyInstaller executable compilation.
"""
import sys
import os
from pathlib import Path

# If frozen (PyInstaller executable)
if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", str(Path(__file__).resolve().parent))
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)
else:
    root_dir = str(Path(__file__).resolve().parent)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

# Also ensure app directory is on sys.path
app_dir = str(Path(__file__).resolve().parent / "app")
if os.path.exists(app_dir) and app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app.main import main

if __name__ == "__main__":
    main()
