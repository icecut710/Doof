"""Bundle vs user-data path resolution for dev and frozen (PyInstaller) runs."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def bundle_root() -> Path:
    """Read-only resources shipped with the app (code, frontend, checkpoints, icons)."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # doof/paths.py → doof/ → project root
    return Path(__file__).resolve().parents[1]


def user_data_dir() -> Path:
    """Writable runtime state (profiles, memory, sessions, settings).

    Frozen builds must not write into the onedir/_internal tree (and must not
    depend on the original Git checkout). On Windows this is %LOCALAPPDATA%\\DOOF.
    """
    if is_frozen():
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        d = base / "DOOF"
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = bundle_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def checkpoints_dir() -> Path:
    """Prefer bundled checkpoints; fall back to user data if needed."""
    bundled = bundle_root() / "checkpoints"
    if bundled.is_dir():
        return bundled
    d = user_data_dir() / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def assets_dir() -> Path:
    return bundle_root() / "assets"


def frontend_dist() -> Path:
    return bundle_root() / "frontend" / "dist"
