#!/usr/bin/env python3
"""Windows update helper — runs AFTER DOOF.exe has exited.

Usage:
  python doof_updater.py --pending <path-to-pending.json>

Flow:
  1. Wait for DOOF.exe to release file locks
  2. Backup current install
  3. Copy staged files over install dir
  4. Launch new DOOF.exe
  5. Exit
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


def wait_unlock(path: Path, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if path.is_file():
                with path.open("ab"):
                    return
            return
        except OSError:
            time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", required=True, help="Path to pending.json")
    ap.add_argument("--install-dir", default="", help="DOOF install directory")
    ap.add_argument("--launch", action="store_true", default=True)
    args = ap.parse_args()

    pending = Path(args.pending)
    if not pending.is_file():
        print(f"No pending update at {pending}")
        return 1
    data = json.loads(pending.read_text(encoding="utf-8"))
    extract = Path(data.get("extract") or "")
    if not extract.is_dir():
        print("Extract dir missing")
        return 1

    install = Path(args.install_dir) if args.install_dir else Path(sys.executable).resolve().parent
    # When frozen helper lives next to DOOF.exe
    if (install / "DOOF.exe").is_file():
        target = install
    elif (install.parent / "DOOF.exe").is_file():
        target = install.parent
    else:
        target = install

    exe = target / "DOOF.exe"
    wait_unlock(exe, timeout=90)

    backup = target.parent / "DOOF_backup"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    try:
        shutil.copytree(target, backup, dirs_exist_ok=True)
    except Exception as e:
        print(f"Backup warning: {e}")

    # Copy staged payload
    # Prefer extract/DOOF onedir layout or extract root
    src = extract / "DOOF" if (extract / "DOOF").is_dir() else extract
    for item in src.iterdir():
        dest = target / item.name
        try:
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as e:
            print(f"Copy failed {item}: {e}")
            # Rollback
            if backup.exists():
                for b in backup.iterdir():
                    d = target / b.name
                    try:
                        if b.is_dir():
                            if d.exists():
                                shutil.rmtree(d, ignore_errors=True)
                            shutil.copytree(b, d)
                        else:
                            shutil.copy2(b, d)
                    except Exception:
                        pass
            return 2

    pending.rename(pending.with_suffix(".done.json"))
    print(f"Updated to {data.get('version')}")

    if args.launch and exe.is_file():
        subprocess.Popen([str(exe)], cwd=str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
