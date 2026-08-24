"""Update client: manifest fetch, verify, stage, apply, rollback."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from doof import __version__ as INSTALLED

DEFAULT_MANIFEST_URL = os.environ.get(
    "DOOF_UPDATE_MANIFEST_URL",
    "https://raw.githubusercontent.com/icecut710/Doof/main/releases/manifest.json",
)
CHANNELS = ("stable", "beta")


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
        return {
            "current": self.current,
            "latest": self.latest,
            "available": self.available,
            "mandatory": self.mandatory,
            "channel": self.channel,
            "notes": self.notes,
            "notes_human": self.notes_human or self.notes,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "min_supported": self.min_supported,
            "incompatible": self.incompatible,
            "error": self.error,
            "checked_at": self.checked_at,
        }


def current_version() -> str:
    return INSTALLED


def _settings_path() -> Path:
    from doof.paths import user_data_dir

    return user_data_dir() / "update_settings.json"


def get_update_settings() -> dict[str, Any]:
    defaults = {
        "channel": "stable",
        "auto_check": True,
        "manifest_url": DEFAULT_MANIFEST_URL,
    }
    try:
        p = _settings_path()
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
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
        _settings_path().write_text(json.dumps(cur, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cur


def _parse_ver(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in (v or "0").strip().lstrip("vV").split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def _newer(a: str, b: str) -> bool:
    """True if a > b."""
    return _parse_ver(a) > _parse_ver(b)


def _fetch_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": f"DOOF/{INSTALLED}", "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update(*, channel: str | None = None, force: bool = False) -> UpdateStatus:
    settings = get_update_settings()
    ch = (channel or settings.get("channel") or "stable").lower()
    if ch not in CHANNELS:
        ch = "stable"
    status = UpdateStatus(current=INSTALLED, channel=ch)
    url = str(settings.get("manifest_url") or DEFAULT_MANIFEST_URL)
    try:
        manifest = _fetch_json(url)
    except Exception as e:
        status.error = f"Could not reach update server: {type(e).__name__}"
        return status

    releases = manifest.get("releases") or []
    if isinstance(manifest.get("channels"), dict):
        # Prefer channel pointer if present
        ptr = manifest["channels"].get(ch)
        if isinstance(ptr, str):
            # ptr is a version string — find matching release
            releases = [r for r in releases if str(r.get("version")) == ptr] or releases

    candidates = [
        r
        for r in releases
        if isinstance(r, dict)
        and str(r.get("channel") or "stable").lower() == ch
        and str(r.get("platform") or "windows").lower() in ("windows", "any", "*")
    ]
    if not candidates:
        candidates = [r for r in releases if isinstance(r, dict)]

    if not candidates:
        status.error = "No releases listed in manifest"
        return status

    # Pick highest version
    candidates.sort(key=lambda r: _parse_ver(str(r.get("version") or "0")), reverse=True)
    best = candidates[0]
    latest = str(best.get("version") or "")
    status.latest = latest
    status.notes = str(best.get("notes") or best.get("release_notes") or "")
    status.notes_human = str(
        best.get("notes_human") or best.get("summary") or status.notes or "Bug fixes and improvements."
    )
    status.download_url = best.get("download_url") or best.get("url")
    status.sha256 = best.get("sha256") or best.get("checksum")
    status.min_supported = best.get("min_supported") or best.get("minimum_supported_version")
    status.mandatory = bool(best.get("mandatory") or best.get("required"))

    if status.min_supported and _newer(status.min_supported, INSTALLED):
        status.incompatible = True
        status.available = True
        status.mandatory = True
        return status

    if latest and _newer(latest, INSTALLED):
        status.available = True
    return status


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_update(status: UpdateStatus | None = None, *, progress_cb=None) -> dict[str, Any]:
    """Download, verify, stage. Returns {ok, message, needs_restart}.

    Full binary swap is best-effort on Windows (rename + relaunch helper).
    Pure-asset updates (frontend/dist, personality) can hot-reload without
    a full EXE replace when the package marks kind=assets.
    """
    st = status or check_for_update()
    if not st.available or not st.download_url:
        return {"ok": False, "message": "No update available", "needs_restart": False}

    from doof.paths import user_data_dir

    stage = user_data_dir() / "updates" / "stage"
    backup = user_data_dir() / "updates" / "backup"
    stage.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)

    dest = stage / f"doof-{st.latest}.zip"
    try:
        if progress_cb:
            progress_cb("Downloading…")
        req = Request(
            str(st.download_url),
            headers={"User-Agent": f"DOOF/{INSTALLED}"},
        )
        with urlopen(req, timeout=120) as resp, dest.open("wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)

        if st.sha256:
            if progress_cb:
                progress_cb("Verifying…")
            got = _sha256_file(dest)
            if got.lower() != str(st.sha256).lower():
                dest.unlink(missing_ok=True)
                return {
                    "ok": False,
                    "message": "Update failed verification. The download was discarded.",
                    "needs_restart": False,
                    "technical": f"sha256 mismatch: expected {st.sha256}, got {got}",
                }

        if progress_cb:
            progress_cb("Staging…")
        extract_dir = stage / f"extract-{st.latest}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "r") as zf:
            # Safety: reject path traversal
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    return {
                        "ok": False,
                        "message": "Update package rejected (unsafe paths).",
                        "needs_restart": False,
                    }
            zf.extractall(extract_dir)

        # Write a pending marker so the next launch can finish the swap.
        pending = user_data_dir() / "updates" / "pending.json"
        pending.write_text(
            json.dumps(
                {
                    "version": st.latest,
                    "extract": str(extract_dir),
                    "zip": str(dest),
                    "sha256": st.sha256,
                    "created_at": time.time(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "message": f"DOOF {st.latest} is ready. Restart to finish updating.",
            "needs_restart": True,
            "version": st.latest,
        }
    except URLError as e:
        return {
            "ok": False,
            "message": "Could not download the update. Try again later.",
            "needs_restart": False,
            "technical": str(e),
        }
    except Exception as e:
        return {
            "ok": False,
            "message": "Update failed. Your current version is unchanged.",
            "needs_restart": False,
            "technical": f"{type(e).__name__}: {e}",
        }


def finish_pending_update() -> dict[str, Any] | None:
    """Called at startup. Applies a previously staged update if present."""
    try:
        from doof.paths import user_data_dir, bundle_dir

        pending = user_data_dir() / "updates" / "pending.json"
        if not pending.is_file():
            return None
        data = json.loads(pending.read_text(encoding="utf-8"))
        extract = Path(data.get("extract") or "")
        if not extract.is_dir():
            pending.unlink(missing_ok=True)
            return None

        # Asset-only updates: copy frontend/dist and selected pure-Python modules
        # into user overlay; full binary replace requires the helper script.
        overlay = user_data_dir() / "overlay"
        overlay.mkdir(parents=True, exist_ok=True)
        for name in ("frontend", "doof"):
            src = extract / name
            if src.exists():
                dst = overlay / name
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)

        pending.rename(pending.with_suffix(".done.json"))
        return {"ok": True, "version": data.get("version"), "mode": "overlay"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
