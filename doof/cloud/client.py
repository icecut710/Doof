"""Offline-first Supabase cloud layer for DOOF."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

try:
    from doof.paths import user_data_dir, bundle_root
    ROOT = bundle_root()
    CONFIG_PATH = user_data_dir() / "cloud.json"
except Exception:
    ROOT = Path(__file__).resolve().parents[2]
    CONFIG_PATH = ROOT / "data" / "cloud.json"

def _load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "url": os.environ.get("DOOF_SUPABASE_URL", ""),
        "anon_key": os.environ.get("DOOF_SUPABASE_ANON_KEY", ""),
        "enabled": False,
    }
    if CONFIG_PATH.exists():
        try:
            cfg.update({k: v for k, v in json.loads(CONFIG_PATH.read_text()).items() if v})
        except Exception:
            pass
    cfg["enabled"] = bool(cfg.get("url") and cfg.get("anon_key"))
    return cfg

def cloud_status() -> dict[str, Any]:
    cfg = _load_config()
    if not cfg["enabled"]:
        return {"connected": False, "status": "offline", "message": "Cloud not configured. Local mode only.", "url": None}
    try:
        import urllib.request
        req = urllib.request.Request(
            cfg["url"].rstrip("/") + "/rest/v1/",
            headers={"apikey": cfg["anon_key"], "Authorization": f"Bearer {cfg['anon_key']}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            ok = 200 <= resp.status < 500
        return {"connected": ok, "status": "connected" if ok else "error", "message": "Supabase reachable" if ok else "error", "url": cfg["url"]}
    except Exception as e:
        return {"connected": False, "status": "offline", "message": f"Cloud unreachable: {e}", "url": cfg["url"]}

class CloudClient:
    def __init__(self):
        self.cfg = _load_config()
    @property
    def available(self) -> bool:
        return bool(self.cfg.get("enabled"))
    def status(self) -> dict[str, Any]:
        return cloud_status()
