"""DOOF v0.2 — friend-ready onedir EXE build.

Run from the project root (Windows recommended for QtWebEngine):

    python packaging/build_exe.py

Steps:
  1. npm install + production frontend build
  2. Verify mrnaddaf / icon / checkpoint assets
  3. PyInstaller onedir via packaging/doof.spec
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str] | str, cwd: Path | None = None, shell: bool = False) -> None:
    print(f"[build] $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(cwd or ROOT), shell=shell)
    if r.returncode != 0:
        print(f"[build] FAILED (exit {r.returncode})")
        sys.exit(r.returncode)


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "package.json").is_file():
        print("[build] ERROR: frontend/package.json missing")
        sys.exit(1)

    print("[build] Installing frontend dependencies…")
    run("npm install", cwd=frontend, shell=True)

    print("[build] Production frontend build…")
    run("npm run build", cwd=frontend, shell=True)

    index = frontend / "dist" / "index.html"
    if not index.is_file():
        print(f"[build] ERROR: expected {index}")
        sys.exit(1)
    print(f"[build] OK frontend → {index}")

    # Vite copies public/ into dist/
    naddaf = frontend / "dist" / "mrnaddaf.png"
    if not naddaf.is_file():
        src = frontend / "public" / "mrnaddaf.png"
        if src.is_file():
            shutil.copy2(src, naddaf)
            print("[build] copied mrnaddaf.png into dist")
        else:
            print("[build] WARNING: mrnaddaf.png missing from frontend dist")


def verify_assets() -> None:
    required = [
        ROOT / "assets" / "doof_icon.ico",
        ROOT / "frontend" / "dist" / "index.html",
        ROOT / "checkpoints" / "doof_v01.pt",
    ]
    optional_icon = ROOT / "assets" / "doof.ico"
    for p in required:
        if not p.exists():
            if p.name == "doof_icon.ico" and optional_icon.exists():
                continue
            if p.name == "doof_v01.pt":
                print(f"[build] WARNING: {p} missing — first run will bootstrap weights")
                continue
            print(f"[build] ERROR: required asset missing: {p}")
            sys.exit(1)
        print(f"[build] OK {p.relative_to(ROOT)}")


def build_exe() -> Path:
    spec = ROOT / "packaging" / "doof.spec"
    if not spec.is_file():
        print(f"[build] ERROR: {spec} not found")
        sys.exit(1)

    print("[build] Running PyInstaller (onedir)…")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(spec),
            "--clean",
            "--noconfirm",
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build"),
        ],
        cwd=ROOT,
    )

    exe = ROOT / "dist" / "DOOF" / "DOOF.exe"
    if not exe.is_file():
        alt = ROOT / "dist" / "DOOF" / "DOOF"
        if alt.is_file():
            exe = alt
    if not exe.exists():
        print("[build] ERROR: DOOF executable not found under dist/DOOF/")
        sys.exit(1)

    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"[build] EXE: {exe} ({size_mb:.1f} MB)")
    folder = ROOT / "dist" / "DOOF"
    total = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
    print(f"[build] Folder: {folder} ({total / (1024 * 1024):.0f} MB total)")
    return exe


def main() -> int:
    print("=== DOOF v0.2 friend-ready packaging ===")
    build_frontend()
    verify_assets()
    build_exe()
    print()
    print("Distribute the entire folder:")
    print(f"  {ROOT / 'dist' / 'DOOF'}")
    print("Friend runs:  DOOF.exe  (do not move only the .exe)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
