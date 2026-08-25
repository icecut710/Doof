"""DOOF v0.3 update client: manifest check, checksum verification, staging."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from doof import __version__ as INSTALLED

DEFAULT_MANIFEST_URL = os.environ.get("DOOF_UPDATE_MANIFEST_URL", "https://raw.githubusercontent.com/icecut710/Doof/main/releases/manifest.json")

@dataclass
class UpdateStatus:
    current: str = INSTALLED
    latest: str | None = None
    available: bool = False
    mandatory: bool = False
    channel: str = "stable"
    notes: str = ""
    notes_human: str = ""
    download_url: str | None = None
    sha256: str | None = None
    min_supported: str | None = None
    incompatible: bool = False
    error: str | None = None
    checked_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

def current_version() -> str:
    return INSTALLED

def get_update_settings() -> dict[str, Any]:
    """Persisted auto-update preferences (channel, check-on-start)."""
    defaults = {
        "channel": "stable",
        "check_on_start": True,
        "manifest_url": DEFAULT_MANIFEST_URL,
    }
    try:
        from doof.paths import user_data_dir
        path = user_data_dir() / "update_settings.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update({k: data[k] for k in defaults if k in data})
    except Exception:
        pass
    return defaults


def save_update_settings(update: dict[str, Any]) -> dict[str, Any]:
    cur = get_update_settings()
    for k in list(cur):
        if k in update:
            cur[k] = update[k]
    try:
        from doof.paths import user_data_dir
        path = user_data_dir() / "update_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cur


def _parse_ver(v: str) -> tuple[int, ...]:
    parts = []
    for p in (v or "0").strip().lstrip("vV").split("."):
        digits = ""
        for ch in p:
            if ch.isdigit(): digits += ch
            else: break
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0])[:4])

def _newer(a: str, b: str) -> bool:
    return _parse_ver(a) > _parse_ver(b)

def _fetch_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": f"DOOF/{INSTALLED}", "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def check_for_update(*, channel: str | None = None, force: bool = False) -> UpdateStatus:
    status = UpdateStatus(channel=(channel or "stable"))
    try:
        manifest = _fetch_json(DEFAULT_MANIFEST_URL)
        releases = manifest.get("releases") or []
        candidates = [r for r in releases if isinstance(r, dict) and str(r.get("channel", "stable")) == status.channel]
        if not candidates: candidates = [r for r in releases if isinstance(r, dict)]
        if not candidates:
            status.error = "No releases listed in manifest"
            return status
        best = max(candidates, key=lambda r: _parse_ver(str(r.get("version", "0"))))
        status.latest = str(best.get("version") or "")
        status.notes = str(best.get("notes") or "")
        status.notes_human = str(best.get("notes_human") or status.notes)
        status.download_url = best.get("download_url") or best.get("url")
        status.sha256 = best.get("sha256")
        status.min_supported = best.get("min_supported")
        status.mandatory = bool(best.get("mandatory"))
        status.incompatible = bool(status.min_supported and _newer(status.min_supported, INSTALLED))
        if status.incompatible:
            status.mandatory = True
        status.available = status.incompatible or bool(status.latest and _newer(status.latest, INSTALLED))
    except Exception as exc:
        status.error = f"Could not reach update server: {type(exc).__name__}"
    return status

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def apply_update(status: UpdateStatus | None = None, *, progress_cb=None) -> dict[str, Any]:
    st = status or check_for_update()
    if not st.available or not st.download_url:
        return {"ok": False, "message": "No update available", "needs_restart": False}
    from doof.paths import user_data_dir
    stage = user_data_dir() / "updates" / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    dest = stage / f"doof-{st.latest}.zip"
    try:
        if progress_cb: progress_cb("Downloading…")
        req = Request(str(st.download_url), headers={"User-Agent": f"DOOF/{INSTALLED}"})
        with urlopen(req, timeout=120) as resp, dest.open("wb") as out:
            while chunk := resp.read(256 * 1024): out.write(chunk)
        if st.sha256 and _sha256_file(dest).lower() != str(st.sha256).lower():
            dest.unlink(missing_ok=True)
            return {"ok": False, "message": "Update failed verification. The download was discarded.", "needs_restart": False}
        extract = stage / f"extract-{st.latest}"
        if extract.exists(): shutil.rmtree(extract, ignore_errors=True)
        extract.mkdir(parents=True)
        with zipfile.ZipFile(dest) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    return {"ok": False, "message": "Update package rejected (unsafe paths).", "needs_restart": False}
            zf.extractall(extract)
        pending = user_data_dir() / "updates" / "pending.json"
        pending.write_text(json.dumps({"version": st.latest, "extract": str(extract), "sha256": st.sha256}, indent=2), encoding="utf-8")
        return {"ok": True, "message": f"DOOF {st.latest} is ready. Restart to finish updating.", "needs_restart": True, "version": st.latest}
    except Exception as exc:
        return {"ok": False, "message": "Update failed. Your current version is unchanged.", "needs_restart": False, "technical": f"{type(exc).__name__}: {exc}"}

def finish_pending_update() -> dict[str, Any] | None:
    from doof.paths import user_data_dir
    pending = user_data_dir() / "updates" / "pending.json"
    if not pending.is_file(): return None
    try:
        data = json.loads(pending.read_text(encoding="utf-8"))
        extract = Path(data["extract"])
        overlay = user_data_dir() / "overlay"
        overlay.mkdir(parents=True, exist_ok=True)
        for name in ("frontend", "doof"):
            src = extract / name
            if src.exists():
                dst = overlay / name
                if dst.exists(): shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
        pending.rename(pending.with_suffix(".done.json"))
        return {"ok": True, "version": data.get("version"), "mode": "overlay"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
