"""DOOF Control Room — server-side authorization only.

Roles (profiles.role):
  user    — default
  trusted — elevated member
  admin   — pool + node actions
  owner   — full control including role assignment

Never trust a client-sent "I am admin" claim.
"""
from __future__ import annotations

import time
from typing import Any

ADMIN_ROLES = frozenset({"admin", "owner"})
OWNER_ROLES = frozenset({"owner"})


def role_of(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "user"
    r = str(profile.get("role") or "user").lower()
    if r in ("user", "trusted", "admin", "owner"):
        return r
    return "user"


def is_admin(profile: dict[str, Any] | None) -> bool:
    return role_of(profile) in ADMIN_ROLES


def is_owner(profile: dict[str, Any] | None) -> bool:
    return role_of(profile) in OWNER_ROLES


def require_admin(profile: dict[str, Any] | None) -> None:
    if not is_admin(profile):
        raise PermissionError("Admin access required")


def require_owner(profile: dict[str, Any] | None) -> None:
    if not is_owner(profile):
        raise PermissionError("Owner access required")


def health_board() -> dict[str, Any]:
    """Probe local services. Times are wall-clock ms for the probe itself."""
    services: dict[str, Any] = {}

    def _probe(name: str, fn) -> None:
        t0 = time.perf_counter()
        try:
            fn()
            ms = int((time.perf_counter() - t0) * 1000)
            services[name] = {"status": "healthy", "ms": ms, "label": "Healthy"}
        except Exception as e:
            ms = int((time.perf_counter() - t0) * 1000)
            services[name] = {
                "status": "degraded",
                "ms": ms,
                "label": "Limited",
                "detail": f"{type(e).__name__}",
            }

    def _api():
        return True

    def _db():
        from database import get_db

        db = get_db()
        if hasattr(db, "get_memories"):
            db.get_memories()
        return True

    def _supabase():
        import os

        url = os.environ.get("SUPABASE_URL") or os.environ.get("DOOF_SUPABASE_URL")
        if not url:
            raise RuntimeError("not configured")
        from urllib.request import urlopen

        urlopen(url.rstrip("/") + "/rest/v1/", timeout=3)

    def _compute():
        from doof.compute.pool import current_job_count

        current_job_count()

    def _updates():
        from doof.updates import check_for_update

        # Soft: network may fail; treat "reached or clean miss" as ok
        st = check_for_update()
        if st.error and "Could not reach" in (st.error or ""):
            raise RuntimeError(st.error)

    def _auth():
        import os

        if not (
            os.environ.get("SUPABASE_URL")
            or os.environ.get("DOOF_SUPABASE_URL")
        ):
            # Local auth still works
            return True
        return True

    def _ai():
        from doof.runtime import torch_available

        # Presence of torch is optional; always "healthy" if process is up
        _ = torch_available()

    _probe("api", _api)
    _probe("database", _db)
    _probe("supabase", _supabase)
    _probe("compute_queue", _compute)
    _probe("update_service", _updates)
    _probe("authentication", _auth)
    _probe("ai_provider", _ai)

    overall = "healthy"
    if any(s.get("status") == "degraded" for s in services.values()):
        overall = "degraded"
    return {"overall": overall, "services": services, "ts": time.time()}


def pool_paused() -> bool:
    try:
        from database import get_db

        db = get_db()
        if hasattr(db, "get_pool_control"):
            row = db.get_pool_control()
            if row:
                return bool(row.get("paused"))
    except Exception:
        pass
    # Local fallback flag
    try:
        from doof.paths import user_data_dir
        import json

        p = user_data_dir() / "pool_control.json"
        if p.is_file():
            return bool(json.loads(p.read_text()).get("paused"))
    except Exception:
        pass
    return False


def set_pool_paused(paused: bool, *, by: str | None = None, note: str | None = None) -> dict[str, Any]:
    import json
    from doof.paths import user_data_dir

    record = {
        "paused": bool(paused),
        "paused_by": by,
        "paused_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if paused else None,
        "note": note,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        p = user_data_dir() / "pool_control.json"
        p.write_text(json.dumps(record, indent=2), encoding="utf-8")
    except Exception:
        pass
    try:
        from database import get_db

        db = get_db()
        if hasattr(db, "set_pool_control"):
            db.set_pool_control(record)
    except Exception:
        pass
    return record


def audit(action: str, *, actor: str | None = None, target: str | None = None, detail: dict | None = None) -> None:
    try:
        from database import get_db

        db = get_db()
        if hasattr(db, "insert_audit_event"):
            db.insert_audit_event(
                {
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "detail": detail or {},
                }
            )
    except Exception:
        pass
