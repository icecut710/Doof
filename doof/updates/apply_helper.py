"""Launch the Windows update helper after staging."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def launch_updater(pending_json: Path) -> dict[str, Any]:
    """Start helper then signal caller to exit DOOF."""
    from doof.paths import bundle_root, user_data_dir

    root = bundle_root()
    helpers = [
        root / "packaging" / "updater" / "doof_updater.py",
        root / "updater" / "doof_updater.py",
        Path(sys.executable).resolve().parent / "doof_updater.py",
    ]
    helper = next((h for h in helpers if h.is_file()), None)
    ps1 = root / "packaging" / "updater" / "Update-DOOF.ps1"
    if not ps1.is_file():
        ps1 = Path(sys.executable).resolve().parent / "Update-DOOF.ps1"

    install_dir = ""
    if getattr(sys, "frozen", False):
        install_dir = str(Path(sys.executable).resolve().parent)

    try:
        if helper is not None:
            cmd = [
                sys.executable if not getattr(sys, "frozen", False) else "python",
                str(helper),
                "--pending",
                str(pending_json),
            ]
            if install_dir:
                cmd.extend(["--install-dir", install_dir])
            # Prefer running helper with same python; when frozen, use pythonw if present
            subprocess.Popen(cmd, cwd=str(helper.parent), close_fds=True)
            return {
                "ok": True,
                "message": "Updater started. DOOF will close so files can be replaced.",
                "needs_exit": True,
                "helper": str(helper),
            }
        if ps1.is_file() and sys.platform == "win32":
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1),
                "-PendingJson",
                str(pending_json),
            ]
            if install_dir:
                cmd.extend(["-InstallDir", install_dir])
            subprocess.Popen(cmd, close_fds=True)
            return {
                "ok": True,
                "message": "Updater started. DOOF will close so files can be replaced.",
                "needs_exit": True,
                "helper": str(ps1),
            }
    except Exception as e:
        return {
            "ok": False,
            "message": "Could not start the update helper.",
            "technical": str(e),
            "needs_exit": False,
        }

    return {
        "ok": True,
        "message": (
            f"Update staged at {pending_json}. Restart DOOF to finish. "
            "If the EXE does not update automatically, run packaging/updater/doof_updater.py."
        ),
        "needs_exit": False,
        "needs_restart": True,
    }
