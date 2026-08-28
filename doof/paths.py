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
    Override with DOOF_DATA_DIR for portable installs / tests.
    """
    env = os.environ.get("DOOF_DATA_DIR")
    if env:
        d = Path(env)
        d.mkdir(parents=True, exist_ok=True)
        return d
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


def overlay_dir() -> Path:
    """User-data overlay for staged updates. Checked before bundle resources."""
    d = user_data_dir() / "overlay"
    d.mkdir(parents=True, exist_ok=True)
    return d


def checkpoints_dir() -> Path:
    """Writable checkpoint directory (trained checkpoints land here).

    Dev:  <repo>/checkpoints
    Frozen: %LOCALAPPDATA%\\DOOF\\checkpoints — never inside the immutable
    PyInstaller bundle, so users can keep training after installing the EXE.

    Override with DOOF_CHECKPOINTS_DIR for portable installs / tests.
    Read-only shipped checkpoints are found via bundled_checkpoints_dir().
    """
    env = os.environ.get("DOOF_CHECKPOINTS_DIR")
    if env:
        d = Path(env)
        d.mkdir(parents=True, exist_ok=True)
        return d
    if is_frozen():
        d = user_data_dir() / "checkpoints"
    else:
        d = bundle_root() / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def bundled_checkpoints_dir() -> Path:
    """Read-only checkpoints shipped with the app (bundle resources)."""
    return bundle_root() / "checkpoints"


def assets_dir() -> Path:
    return bundle_root() / "assets"


def frontend_dist() -> Path:
    """Check overlay first, then bundled frontend."""
    ov = overlay_dir() / "frontend" / "dist"
    if ov.is_dir() and any(ov.iterdir()):
        return ov
    return bundle_root() / "frontend" / "dist"
