"""Extra HTTP handlers: updates, admin, device, models, hosted brain."""
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

    # -------- Models --------
    if path == "/api/models" and method == "GET":
        from doof.models import list_registry, model_compatible
        from doof.runtime import probe_hardware

        hw = probe_hardware()
        models = []
        for m in list_registry():
            ok, reason = model_compatible(m, hw)
            d = m.as_dict()
            d["compatible"] = ok
            d["compatibility_detail"] = reason
            models.append(d)
        _json(handler, 200, {"models": models, "cache": True})
        return True

    if path == "/api/models/ensure" and method == "POST":
        from doof.models import ensure_model

        body = read_json()
        mid = str(body.get("model_id") or "doof-base")
        ver = body.get("version")
        try:
            m = ensure_model(mid, str(ver) if ver else None)
            _json(handler, 200, {"ok": True, "model": m.as_dict()})
        except Exception as e:
            _json(handler, 400, {"ok": False, "error": str(e)})
        return True

    if path == "/api/brain/hosted" and method == "GET":
        from doof.cloud.hosted_brain import hosted_config, hosted_health

        _json(handler, 200, {"config": hosted_config(), "health": hosted_health()})
        return True

    # -------- Device preference --------
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
                    "physical_gpu": hw.get("physical_gpu"),
                    "torch_cuda": hw.get("torch_cuda"),
                    "cuda_devices": hw.get("cuda_devices"),
                    "mps_available": hw.get("mps_available"),
                    "cpu_count": hw.get("cpu_count"),
                    "ram_gb": hw.get("ram_gb"),
                    "acceleration": hw.get("acceleration"),
                    "acceleration_detail": hw.get("acceleration_detail"),
                    "torch_available": hw.get("torch_available"),
                    "torch_error": hw.get("torch_error"),
                    "build_kind": hw.get("build_kind"),
                },
            },
        )
        return True

    if path == "/api/device" and method == "POST":
        from doof.runtime import set_device_preference, probe_hardware, resolve_device, import_torch

        body = read_json()
        pref = set_device_preference(str(body.get("preference") or body.get("device") or "auto"))
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
                    "build_kind": hw.get("build_kind"),
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

    if path == "/api/updates/status" and method == "GET":
        from doof.updates import check_for_update, current_version, get_update_settings

        st = check_for_update()
        _json(
            handler,
            200,
            {
                "version": current_version(),
                "settings": get_update_settings(),
                "check": st.as_dict(),
            },
        )
        return True

    if path == "/api/updates/apply" and method == "POST":
        from doof.updates import apply_update, check_for_update
        from doof.updates.apply_helper import launch_updater
        from pathlib import Path
        from doof.paths import user_data_dir

        st = check_for_update()
        result = apply_update(st)
        if result.get("ok") and result.get("needs_restart"):
            pending = user_data_dir() / "updates" / "pending.json"
            if pending.is_file():
                helper = launch_updater(pending)
                result.update(helper)
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

    # -------- Model Sync --------
    if path == "/api/models/sync/check" and method == "GET":
        from doof.models.manager import list_registry, resolve_active_model, model_compatible

        try:
            models = list_registry()
            active = resolve_active_model()
            hw_info = {}
            try:
                from doof.runtime import probe_hardware
                hw_info = probe_hardware()
            except Exception:
                pass
            compatible, reason = model_compatible(active, hw_info) if active else (False, "no model")
            _json(handler, 200, {
                "active_model": active.as_dict() if active else None,
                "registry_count": len(models),
                "compatible": compatible,
                "compatibility_reason": reason,
                "cached": [{"name": m.name, "size": m.size} for m in __import__("doof.models.manager", fromlist=["list_cached"]).list_cached()],
            })
        except Exception as e:
            _json(handler, 500, {"error": str(e)})
        return True

    if path == "/api/models/sync/ensure" and method == "POST":
        from doof.models.manager import ensure_model

        body = read_json()
        model_id = body.get("model_id", "doof-base")
        version = body.get("version")
        try:
            model = ensure_model(model_id, version)
            _json(handler, 200, {"ok": True, "model": model.as_dict()})
        except Exception as e:
            _json(handler, 400, {"error": str(e)})
        return True

    # Model upload with optional cloud sync
    if path == "/api/models/upload" and method == "POST":
        body = read_json()
        ckpt_path = (body.get("path") or body.get("checkpoint_path") or "").strip()
        model_id = (body.get("model_id") or "doof-base").strip()
        version = (body.get("version") or "").strip()
        if not ckpt_path or not version:
            _json(handler, 400, {"error": "path and version required"})
            return True
        try:
            from doof.models.manager import upload_checkpoint
            from pathlib import Path as P
            model = upload_checkpoint(
                P(ckpt_path), model_id, version,
                label=body.get("label", ""),
                channel=body.get("channel", "stable"),
                notes=body.get("notes", ""),
                upload_to_cloud=bool(body.get("upload_to_cloud")),
            )
            _json(handler, 201, {"ok": True, "model": model.as_dict()})
        except Exception as e:
            _json(handler, 400, {"error": str(e)})
        return True

    # Register a model entry (metadata only, no file upload)
    if path == "/api/models/register" and method == "POST":
        body = read_json()
        model_id = (body.get("model_id") or "").strip()
        version = (body.get("version") or "").strip()
        if not model_id or not version:
            _json(handler, 400, {"error": "model_id and version required"})
            return True
        try:
            from doof.models.manager import ModelInfo
            from database import get_db
            db = get_db()
            record = {
                "model_id": model_id,
                "version": version,
                "label": body.get("label", f"{model_id} {version}"),
                "format": body.get("format", "doof-pt"),
                "size_bytes": int(body.get("size_bytes") or 0),
                "sha256": body.get("sha256", ""),
                "download_url": body.get("download_url", ""),
                "channel": body.get("channel", "stable"),
                "status": body.get("status", "candidate"),
                "cpu_supported": bool(body.get("cpu_supported", True)),
                "gpu_supported": bool(body.get("gpu_supported", True)),
                "min_ram_gb": float(body.get("min_ram_gb") or 4),
                "recommended_ram_gb": float(body.get("recommended_ram_gb") or 8),
                "min_vram_gb": float(body.get("min_vram_gb") or 0),
                "recommended_vram_gb": float(body.get("recommended_vram_gb") or 0),
                "notes": body.get("notes", ""),
            }
            if hasattr(db, "insert_model"):
                db.insert_model(record)
            _json(handler, 201, {"ok": True, "model": record})
        except Exception as e:
            _json(handler, 400, {"error": str(e)})
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
        hosted = {}
        try:
            from doof.cloud.hosted_brain import hosted_health

            hosted = hosted_health()
        except Exception:
            hosted = {"available": False}
        _json(
            handler,
            200,
            {
                "allowed": True,
                "role": role_of(profile),
                "currentUserId": (profile or {}).get("id"),
                "health": health_board(),
                "pool": {
                    "paused": pool_paused(),
                    "online": online,
                    "accepting": accepting,
                    "jobs_running": jobs_running,
                },
                "hosted_brain": hosted,
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

    # -------- Admin: User Management --------
    if path == "/api/admin/users" and method == "GET":
        from doof.admin import is_admin, require_admin

        try:
            require_admin(profile)
        except PermissionError:
            _json(handler, 403, {"error": "forbidden"})
            return True
        try:
            from doof.api_full import _load_profiles

            profiles = _load_profiles()
            users = [
                {
                    "id": p.get("id", ""),
                    "email": p.get("email", ""),
                    "name": p.get("name", ""),
                    "role": p.get("role", "user"),
                    "provider": p.get("provider", "local"),
                    "created_at": p.get("created_at", ""),
                }
                for p in profiles
            ]
            _json(handler, 200, {"users": users})
        except Exception as e:
            _json(handler, 500, {"error": str(e)})
        return True

    if path == "/api/admin/users/role" and method == "POST":
        from doof.admin import is_owner, require_owner

        try:
            require_owner(profile)
        except PermissionError:
            _json(handler, 403, {"error": "forbidden"})
            return True
        body = read_json()
        user_id = str(body.get("user_id") or "")
        new_role = str(body.get("role") or "").lower()
        if not user_id or new_role not in ("user", "trusted", "admin", "owner"):
            _json(handler, 400, {"error": "user_id and valid role required"})
            return True
        try:
            from doof.api_full import _load_profiles, _save_profiles

            profiles = _load_profiles()
            target = next((p for p in profiles if p.get("id") == user_id), None)
            if not target:
                _json(handler, 404, {"error": "user not found"})
                return True
            # Prevent self-demotion if owner
            if user_id == (profile or {}).get("id") and new_role != "owner":
                _json(handler, 400, {"error": "cannot demote yourself"})
                return True
            target["role"] = new_role
            _save_profiles(profiles)
            _json(handler, 200, {"ok": True, "user": {"id": target["id"], "email": target.get("email"), "role": new_role}})
        except Exception as e:
            _json(handler, 500, {"error": str(e)})
        return True

    if path == "/api/version" and method == "GET":
        _json(
            handler,
            200,
            {"version": __version__, "protocol": __protocol__, "name": "DOOF"},
        )
        return True

    return False
