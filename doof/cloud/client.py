"""Offline-first Supabase cloud layer for DOOF.

Status states (mutually exclusive intent):
  not_configured  — no URL/key
  unauthorized    — keys present but 401/403
  connected       — reachable and authorized
  unreachable     — network/DNS/timeout
  error           — other HTTP failure
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from doof.paths import user_data_dir, bundle_root

    ROOT = bundle_root()
    CONFIG_PATH = user_data_dir() / "cloud.json"
except Exception:
    ROOT = Path(__file__).resolve().parents[2]
    CONFIG_PATH = ROOT / "data" / "cloud.json"


def _load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "url": os.environ.get("DOOF_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "",
        "anon_key": (
            os.environ.get("DOOF_SUPABASE_ANON_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
            or ""
        ),
        "enabled": False,
    }
    # Prefer user-data cloud.json over stale env if both set
    if CONFIG_PATH.exists():
        try:
            file_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for k in ("url", "anon_key", "enabled"):
                if file_cfg.get(k):
                    cfg[k] = file_cfg[k]
        except Exception:
            pass
    # Also check EXE-adjacent .env is already loaded by api._load_env
    cfg["url"] = str(cfg.get("url") or "").rstrip("/")
    cfg["anon_key"] = str(cfg.get("anon_key") or "").strip()
    cfg["enabled"] = bool(cfg["url"] and cfg["anon_key"])
    return cfg


def cloud_status() -> dict[str, Any]:
    cfg = _load_config()
    if not cfg["enabled"]:
        return {
            "connected": False,
            "status": "not_configured",
            "state": "not_configured",
            "message": "Cloud not configured. Local mode only.",
            "label": "Local kitchen only",
            "detail": "No Supabase URL/key. DOOF still works offline.",
            "url": None,
            "ms": None,
        }

    headers = {
        "apikey": cfg["anon_key"],
        "Authorization": f"Bearer {cfg['anon_key']}",
        "Accept": "application/json",
    }
    # Prefer Auth health — does not require table RLS grants
    probes = [
        cfg["url"] + "/auth/v1/health",
        cfg["url"] + "/rest/v1/",
    ]
    last_err = ""
    for endpoint in probes:
        t0 = time.perf_counter()
        try:
            req = Request(endpoint, headers=headers, method="GET")
            with urlopen(req, timeout=4) as resp:
                ms = int((time.perf_counter() - t0) * 1000)
                code = resp.status
                if 200 <= code < 300:
                    return {
                        "connected": True,
                        "status": "connected",
                        "state": "connected",
                        "message": f"Supabase connected · {ms}ms",
                        "label": "Connected",
                        "detail": f"Responded in {ms}ms",
                        "url": cfg["url"],
                        "ms": ms,
                    }
                if code in (401, 403):
                    return {
                        "connected": False,
                        "status": "unauthorized",
                        "state": "unauthorized",
                        "message": "Cloud configured but unauthorized (check anon key).",
                        "label": "Unauthorized",
                        "detail": "URL is set, but the API key was rejected. Update SUPABASE_ANON_KEY.",
                        "url": cfg["url"],
                        "ms": ms,
                    }
                last_err = f"HTTP {code}"
        except HTTPError as e:
            ms = int((time.perf_counter() - t0) * 1000)
            if e.code in (401, 403):
                return {
                    "connected": False,
                    "status": "unauthorized",
                    "state": "unauthorized",
                    "message": "Cloud configured but unauthorized (check anon key).",
                    "label": "Unauthorized",
                    "detail": "URL is set, but the API key was rejected. Update SUPABASE_ANON_KEY in .env or cloud.json.",
                    "url": cfg["url"],
                    "ms": ms,
                }
            # 404 on /rest/v1/ with valid key can still mean project is up
            if e.code == 404 and "/rest/v1" in endpoint:
                return {
                    "connected": True,
                    "status": "connected",
                    "state": "connected",
                    "message": f"Supabase reachable · {ms}ms",
                    "label": "Connected",
                    "detail": f"Project responded ({e.code}) in {ms}ms",
                    "url": cfg["url"],
                    "ms": ms,
                }
            last_err = f"HTTP {e.code}"
        except URLError as e:
            last_err = str(e.reason if hasattr(e, "reason") else e)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"

    return {
        "connected": False,
        "status": "unreachable",
        "state": "unreachable",
        "message": f"Cloud unreachable: {last_err}",
        "label": "Temporarily unreachable",
        "detail": last_err or "Network error",
        "url": cfg["url"],
        "ms": None,
    }


class CloudClient:
    def __init__(self):
        self.cfg = _load_config()

    @property
    def available(self) -> bool:
        return bool(self.cfg.get("enabled"))

    def status(self) -> dict[str, Any]:
        return cloud_status()
