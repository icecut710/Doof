"""Extra HTTP handlers for updates, admin, device preference (v0.3).

Mounted via doof.api_mount onto Handler.do_GET / do_POST.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from doof import __version__, __protocol__


def _json(handler, code: int, body: dict[str, Any]) -> None:
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def try_handle(
    handler,
    method: str,
    path: str,
    *,
    get_profile: Callable[[], dict | None],
    read_json: Callable[[], dict],
) -> bool:
    profile = None
    try:
        profile = get_profile()
    except Exception:
        profile = None

    # -------- Device preference (local inference hardware) --------
    if path == "/api/device" and method == "GET":
        from doof.runtime import (
            device_options,
            get_device_preference,
            probe_hardware,
            resolve_device,
            import_torch,
        )

        hw = probe_hardware(force=True)
        torch = import_torch()
        dev_str, dev_label = resolve_device(torch)
        _json(
            handler,
            200,
            {
                "preference": get_device_preference(),
                "active_device": dev_str,
                "active_label": dev_label,
                "options": device_options(),
                "hardware": {
                    "device_label": hw.get("device_label"),
                    "cuda_detected": hw.get("cuda_detected"),
                    "cuda_available": hw.get("cuda_available"),
                    "cuda_devices": hw.get("cuda_devices"),
                    "mps_available": hw.get("mps_available"),
                    "cpu_count": hw.get("cpu_count"),
                    "ram_gb": hw.get("ram_gb"),
                    "acceleration": hw.get("acceleration"),
                    "acceleration_detail": hw.get("acceleration_detail"),
                    "torch_available": hw.get("torch_available"),
                    "torch_error": hw.get("torch_error"),
                },
            },
        )
        return True

    if path == "/api/device" and method == "POST":
        from doof.runtime import set_device_preference, probe_hardware, resolve_device, import_torch

        body = read_json()
        pref = set_device_preference(str(body.get("preference") or body.get("device") or "auto"))
        # Force model reload on next chat
        try:
            import doof.api as api_mod

            with api_mod._lock:
                api_mod._inf = None
                api_mod._loaded = None
        except Exception:
            pass
        hw = probe_hardware(force=True)
        torch = import_torch()
        dev_str, dev_label = resolve_device(torch)
        _json(
            handler,
            200,
            {
                "ok": True,
                "preference": pref,
                "active_device": dev_str,
                "active_label": dev_label,
                "hardware": {
                    "acceleration": hw.get("acceleration"),
                    "acceleration_detail": hw.get("acceleration_detail"),
                    "cuda_devices": hw.get("cuda_devices"),
                    "torch_available": hw.get("torch_available"),
                    "torch_error": hw.get("torch_error"),
                },
            },
        )
        return True

    # -------- Updates --------
    if path == "/api/updates/check" and method == "GET":
        from doof.updates import check_for_update

        st = check_for_update()
        _json(handler, 200, st.as_dict())
        return True

    if path == "/api/updates/apply" and method == "POST":
        from doof.updates import apply_update, check_for_update

        st = check_for_update()
        result = apply_update(st)
        _json(handler, 200 if result.get("ok") else 400, result)
        return True

    if path == "/api/updates/settings" and method == "GET":
        from doof.updates import get_update_settings

        _json(handler, 200, get_update_settings())
        return True

    if path == "/api/updates/settings" and method == "POST":
        from doof.updates import save_update_settings

        body = read_json()
        _json(handler, 200, save_update_settings(body))
        return True

    # -------- Admin --------
    if path == "/api/admin/overview" and method == "GET":
        from doof.admin import health_board, is_admin, pool_paused, role_of

        if not is_admin(profile):
            _json(handler, 403, {"allowed": False, "error": "forbidden"})
            return True
        nodes: list[dict] = []
        try:
            from database import get_db

            db = get_db()
            if hasattr(db, "get_nodes"):
                nodes = db.get_nodes() or []
        except Exception:
            nodes = []
        online = sum(1 for n in nodes if n.get("status") == "online")
        accepting = sum(1 for n in nodes if n.get("accepting_jobs"))
        jobs_running = 0
        try:
            from doof.compute.pool import current_job_count

            jobs_running = current_job_count()
        except Exception:
            pass
        _json(
            handler,
            200,
            {
                "allowed": True,
                "role": role_of(profile),
                "health": health_board(),
                "pool": {
                    "paused": pool_paused(),
                    "online": online,
                    "accepting": accepting,
                    "jobs_running": jobs_running,
                },
                "nodes": nodes[:50],
                "version": {
                    "client": __version__,
                    "backend": __version__,
                    "protocol": __protocol__,
                },
            },
        )
        return True

    if path == "/api/admin/pool/pause" and method == "POST":
        from doof.admin import audit, require_admin, set_pool_paused

        try:
            require_admin(profile)
        except PermissionError:
            _json(handler, 403, {"ok": False, "error": "forbidden"})
            return True
        body = read_json()
        paused = bool(body.get("paused", True))
        actor = None
        if profile:
            actor = str(profile.get("id") or profile.get("email") or "")
        rec = set_pool_paused(paused, by=actor, note=str(body.get("note") or ""))
        audit("pool_pause" if paused else "pool_resume", actor=actor, detail=rec)
        _json(handler, 200, {"ok": True, **rec})
        return True

    if path == "/api/admin/node/disable" and method == "POST":
        from doof.admin import audit, require_admin

        try:
            require_admin(profile)
        except PermissionError:
            _json(handler, 403, {"ok": False, "error": "forbidden"})
            return True
        body = read_json()
        nid = str(body.get("node_id") or "")
        if not nid:
            _json(handler, 400, {"ok": False, "error": "node_id required"})
            return True
        try:
            from database import get_db

            db = get_db()
            if hasattr(db, "update_node"):
                db.update_node(nid, accepting_jobs=False, status="disabled")
        except Exception as e:
            _json(handler, 500, {"ok": False, "error": str(e)})
            return True
        actor = str((profile or {}).get("id") or "")
        audit("node_disable", actor=actor, target=nid)
        _json(handler, 200, {"ok": True})
        return True

    if path == "/api/version" and method == "GET":
        _json(
            handler,
            200,
            {"version": __version__, "protocol": __protocol__, "name": "DOOF"},
        )
        return True

    return False
