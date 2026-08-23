"""DOOF v0.2 — PyInstaller build script.

Run from the project root:
    python packaging/build_exe.py

Prerequisites:
    pip install pyinstaller
    cd frontend && npm run build   (must be done first)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def check_frontend():
    dist = ROOT / "frontend" / "dist" / "index.html"
    if not dist.exists():
        print("[build] ERROR: Frontend not built.")
        print("  Run:  cd frontend && npm run build")
        sys.exit(1)
    print(f"[build] ✓ Frontend dist found: {dist}")

def build_exe():
    check_frontend()

    spec = ROOT / "packaging" / "DOOF.spec"
    if not spec.exists():
        print("[build] ERROR: DOOF.spec not found.")
        sys.exit(1)

    print("[build] Running PyInstaller…")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec), "--clean", "--noconfirm"],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("[build] ❌ PyInstaller failed.")
        sys.exit(result.returncode)

    print("[build] ✓ Build complete.")
    dist_exe = ROOT / "dist" / "DOOF" / "DOOF.exe"
    if dist_exe.exists():
        print(f"[build] EXE: {dist_exe}")
    else:
        print("[build] (EXE path may differ — check dist/)")

if __name__ == "__main__":
    build_exe()
