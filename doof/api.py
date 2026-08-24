"""DOOF local HTTP API — v0.2 Alpha.

Endpoints
---------
GET  /api/health
GET  /api/hardware
GET  /api/model
GET  /api/checkpoints
GET  /api/models/versions
GET  /api/training
GET  /api/training/jobs
GET  /api/approved_examples
GET  /api/approved_examples/count
GET  /api/network
GET  /api/settings
GET  /api/cloud
GET  /api/knowledge
GET  /api/memory
GET  /api/feedback
GET  /api/nodes
GET  /api/scheduler

POST /api/generate
POST /api/training/start
POST /api/training/stop
POST /api/training/build_dataset
POST /api/training/jobs
POST /api/training/jobs/{id}/cancel
POST /api/model/load
POST /api/reload
POST /api/settings
POST /api/knowledge          (legacy compat)
POST /api/memory
POST /api/memory/{id}/approve
POST /api/feedback
POST /api/feedback/{id}/approve
POST /api/nodes/register
POST /api/nodes/heartbeat
POST /api/models/promote
POST /api/approved_examples

DELETE /api/memory/{id}
DELETE /api/nodes/{id}
DELETE /api/approved_examples/{id}
"""
from __future__ import annotations

import json
import os
import platform
import re
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv optional in frozen builds
    pass

from database import get_db

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CKPT_DIR = ROOT / "checkpoints"
DATA_DIR = ROOT / "data"
TRAIN = DATA_DIR / "train.txt"
KNOW = DATA_DIR / "knowledge.json"
SETT = DATA_DIR / "settings.json"
NODES_PATH = DATA_DIR / "nodes.json"
VERSIONS_PATH = DATA_DIR / "brain_versions.json"
VERSIONS_PATH = DATA_DIR / "brain_versions.json"
PROFILES_PATH = DATA_DIR / "profiles.json"
SESSIONS_PATH = DATA_DIR / "sessions.json"

# Heartbeat thread interval (seconds)

# Heartbeat thread interval (seconds)
_HEARTBEAT_INTERVAL = 30
# How long before a node is considered stale (seconds)
_NODE_TIMEOUT = 60

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_inf = None
_loaded: str | None = None
_train: dict[str, Any] = {
    "running": False,
    "step": 0,
    "loss": None,
    "epoch": 0,
    "message": "idle",
    "history": [],
    "lr": 3e-4,
    "speed": None,
    "eta_seconds": None,
    "dataset_version": None,
}
_stop = threading.Event()
_settings = {
    "temperature": 0.7,
    "max_new_tokens": 80,
    "top_k": 50,
    "context_length": 64,
}

# Local node identity (set on first registration / heartbeat)
_local_node_id: str | None = None

# Local node identity (set on first registration / heartbeat)
_local_node_id: str | None = None

# ---------------------------------------------------------------------------
# Auth — local profiles (Owner / Trusted) + sessions
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_profiles() -> list[dict[str, Any]]:
    if not PROFILES_PATH.exists():
        return []
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_profiles(profiles: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _hash_password(password: str, salt: str) -> str:
    import hashlib

    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1
    ).hex()


def _public_profile(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": p.get("id"),
        "email": p.get("email"),
        "name": p.get("name") or (p.get("email") or "").split("@")[0],
        "role": p.get("role", "trusted"),
        "created_at": p.get("created_at"),
        "provider": p.get("provider", "local"),
    }


def _create_session(profile_id: str) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    sessions: list[dict[str, Any]] = []
    if SESSIONS_PATH.exists():
        try:
            sessions = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            sessions = []
    sessions.append({"token": token, "profile_id": profile_id, "created_at": _utcnow()})
    sessions = sessions[-200:]
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_PATH.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    return token


def _profile_from_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        sessions = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    entry = next((s for s in sessions if s.get("token") == token), None)
    if not entry:
        return None
    profile = next(
        (p for p in _load_profiles() if p.get("id") == entry.get("profile_id")), None
    )
    return _public_profile(profile) if profile else None


def _bearer_token(h: BaseHTTPRequestHandler) -> str | None:
    auth = h.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _supabase_signin(
    email: str, password: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Try Supabase password auth.

    Returns ``(user, None)`` on success, ``(None, "email_unverified")`` when
    the account exists but hasn't confirmed their email, or ``(None, None)``
    when Supabase is not configured / unreachable (local fallback).
    """
    cfg = _supabase_cfg()
    if not cfg:
        return None, None
    url, key = cfg
    try:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        req = Request(
            f"{url}/auth/v1/token?grant_type=password",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"apikey": key, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        user = data.get("user") or {}
        return {"id": user.get("id"), "email": user.get("email"), "provider": "supabase"}, None
    except HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("msg", "")
        except Exception:
            msg = ""
        if "confirm" in msg.lower() or "verified" in msg.lower():
            return None, "email_unverified"
        return None, None
    except Exception:
        return None, None


def _supabase_cfg() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    return (url, key) if url and key else None


def _supabase_signup(email: str, password: str) -> tuple[int, dict[str, Any]]:
    """Real signup through Supabase Auth (sends verification email)."""
    cfg = _supabase_cfg()
    if not cfg:
        return 0, {}
    url, key = cfg
    try:
        from urllib.request import Request, urlopen

        req = Request(
            f"{url}/auth/v1/signup",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"apikey": key, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        session_token = data.get("access_token")
        if session_token:
            # Email confirmation disabled — verified immediately.
            profiles = _load_profiles()
            profile = next((p for p in profiles if p.get("email") == email), None)
            if profile is None:
                role = "owner" if not profiles else "trusted"
                profile = {
                    "id": (data.get("user") or {}).get("id") or str(uuid.uuid4()),
                    "email": email,
                    "name": "",
                    "role": role,
                    "created_at": _utcnow(),
                    "provider": "supabase",
                    "email_verified": True,
                }
                profiles.append(profile)
                _save_profiles(profiles)
            token = _create_session(profile["id"])
            return 200, {"token": token, "profile": _public_profile(profile)}
        # Confirmation email sent — no session until verified.
        return 200, {"status": "verify_email_sent"}
    except Exception as e:
        body = getattr(e, "read", None)
        msg = ""
        try:
            msg = json.loads(body().decode()).get("msg", "") if callable(body) else ""
        except Exception:
            pass
        if "already registered" in msg or "already exists" in msg:
            return 409, {"error": "account already exists — sign in instead"}
        return 502, {"error": f"Supabase connection lost ({msg or e})"}


def auth_config() -> dict[str, Any]:
    cfg = _supabase_cfg()
    if cfg:
        return {
            "provider": "supabase",
            "oauth": True,
            "email_verification": True,
            "authorize_url": f"{cfg[0]}/auth/v1/authorize?provider=google&response_type=token",
        }
    return {"provider": "local", "oauth": False, "email_verification": False}


def auth_resend(email: str) -> tuple[int, dict[str, Any]]:
    cfg = _supabase_cfg()
    if not cfg:
        return 400, {"error": "email verification requires Supabase"}
    url, key = cfg
    try:
        from urllib.request import Request, urlopen

        req = Request(
            f"{url}/auth/v1/resend",
            data=json.dumps({"type": "signup", "email": email}).encode(),
            headers={"apikey": key, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=8) as resp:
            resp.read()
        return 200, {"ok": True}
    except Exception as e:
        return 502, {"error": f"Couldn't reach Supabase ({e})"}


def auth_oauth(access_token: str) -> tuple[int, dict[str, Any]]:
    """Exchange a Supabase OAuth access token (Google implicit flow) for a
    DOOF session.  Identity is verified server-side via /auth/v1/user."""
    cfg = _supabase_cfg()
    if not cfg:
        return 400, {"error": "Google sign-in requires Supabase configuration"}
    url, key = cfg
    try:
        from urllib.request import Request, urlopen

        req = Request(
            f"{url}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        with urlopen(req, timeout=8) as resp:
            user = json.loads(resp.read())
        email = (user.get("email") or "").lower()
        if not email:
            return 401, {"error": "Google account has no email"}
        profiles = _load_profiles()
        profile = next((p for p in profiles if p.get("email") == email), None)
        if profile is None:
            role = "owner" if not profiles else "trusted"
            profile = {
                "id": user.get("id") or str(uuid.uuid4()),
                "email": email,
                "name": (user.get("user_metadata") or {}).get("full_name", ""),
                "role": role,
                "created_at": _utcnow(),
                "provider": "google",
                "email_verified": True,
            }
            profiles.append(profile)
            _save_profiles(profiles)
        token = _create_session(profile["id"])
        return 200, {"token": token, "profile": _public_profile(profile)}
    except Exception as e:
        return 401, {"error": f"Google authentication failed ({e})"}


def auth_signup(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return 400, {"error": "email and password required"}
    if len(password) < 6:
        return 400, {"error": "password must be at least 6 characters"}

    profiles = _load_profiles()
    if any(p.get("email") == email for p in profiles):
        return 409, {"error": "account already exists — sign in instead"}

    # Supabase Auth is the real authority when configured — this sends the
    # verification email and only yields a session once verified.
    code, payload = _supabase_signup(email, password)
    if code:
        return code, payload

    # Local development fallback (no mail service): verified immediately.
    role = "owner" if not profiles else "trusted"
    salt = uuid.uuid4().hex
    profile: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": (body.get("name") or "").strip(),
        "role": role,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "created_at": _utcnow(),
        "provider": "local",
        "email_verified": True,
    }
    profiles.append(profile)
    _save_profiles(profiles)

    token = _create_session(profile["id"])
    return 200, {"token": token, "profile": _public_profile(profile)}


def auth_login(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return 400, {"error": "email and password required"}

    # Supabase Auth is the real authority when configured.
    sb_user, sb_err = _supabase_signin(email, password)
    if sb_err == "email_unverified":
        return 403, {"error": "Verify your email before entering DOOF.", "code": "email_unverified"}

    profiles = _load_profiles()
    profile = next((p for p in profiles if p.get("email") == email), None)

    if sb_user:
        if profile is None:
            role = "owner" if not profiles else "trusted"
            profile = {
                "id": sb_user.get("id") or str(uuid.uuid4()),
                "email": email,
                "name": "",
                "role": role,
                "created_at": _utcnow(),
                "provider": "supabase",
                "email_verified": True,
            }
            profiles.append(profile)
            _save_profiles(profiles)
        token = _create_session(profile["id"])
        return 200, {"token": token, "profile": _public_profile(profile)}

    # Local fallback
    if profile is None:
        return 401, {"error": "no account found — create one first"}
    if _hash_password(password, profile.get("salt", "")) != profile.get("password_hash"):
        return 401, {"error": "wrong password"}
    if profile.get("email_verified") is False:
        return 403, {"error": "Verify your email before entering DOOF.", "code": "email_unverified"}
    token = _create_session(profile["id"])
    return 200, {"token": token, "profile": _public_profile(profile)}


# ---------------------------------------------------------------------------
# CORS / helpers
# ---------------------------------------------------------------------------
# CORS / helpers
# ---------------------------------------------------------------------------


def _cors(h: BaseHTTPRequestHandler) -> None:
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")


def _json(h: BaseHTTPRequestHandler, code: int, data: Any) -> None:
    b = json.dumps(data, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(b)))
    _cors(h)
    h.end_headers()
    h.wfile.write(b)


def _body(h: BaseHTTPRequestHandler) -> dict[str, Any]:
    n = int(h.headers.get("Content-Length", 0))
    if n <= 0:
        return {}
    try:
        return json.loads(h.rfile.read(n))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Database adapter proxy
# ---------------------------------------------------------------------------


def _db():
    """Return the active database adapter (Supabase or local JSON)."""
    return get_db()


# ---------------------------------------------------------------------------
# Hardware / model helpers (preserved from v0.1)
# ---------------------------------------------------------------------------


def _find_ckpt(pref: str | None = None) -> Path:
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    if pref:
        p = Path(pref) if Path(pref).is_absolute() else ROOT / pref
        if p.exists():
            return p
    for n in ("doof_v01.pt", "doof_v0.1.pt"):
        if (CKPT_DIR / n).exists():
            return CKPT_DIR / n
    steps = sorted(CKPT_DIR.glob("doof_step_*.pt"))
    if steps:
        return steps[-1]
    raise FileNotFoundError("No checkpoint found. Run: python -m doof train")


def get_inf(ckpt: str | None = None):
    global _inf, _loaded
    with _lock:
        path = str(_find_ckpt(ckpt))
        if _inf is not None and _loaded == path:
            return _inf
        from doof.inference import DOOFInference
        _inf = DOOFInference(path)
        _loaded = path
        return _inf


def hardware() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cuda_available": False,
        "cuda_device_count": 0,
        "cuda_devices": [],
        "cuda_version": None,
        "mps_available": False,
        "device": "cpu",
        "torch_version": None,
        "cpu_count": None,
    }
    try:
        import os
        info["cpu_count"] = os.cpu_count()
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["device"] = "cuda"
            info["cuda_device_count"] = torch.cuda.device_count()
            info["cuda_version"] = getattr(torch.version, "cuda", None)
            for i in range(info["cuda_device_count"]):
                p = torch.cuda.get_device_properties(i)
                info["cuda_devices"].append(
                    {
                        "index": i,
                        "name": p.name,
                        "total_memory_gb": round(p.total_memory / (1024**3), 2),
                    }
                )
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["mps_available"] = True
            info["device"] = "mps"
    except Exception as e:
        info["error"] = str(e)
    return info


def model_info() -> dict[str, Any]:
    try:
        inf = get_inf()
        n = sum(p.numel() for p in inf.model.parameters())
        return {
            "loaded": True,
            "step": getattr(inf, "step", 0),
            "loss": getattr(inf, "loss", None),
            "parameters": n,
            "parameters_m": round(n / 1e6, 2),
            "d_model": inf.model.d_model,
            "max_seq_len": inf.model.max_seq_len,
            "vocab_size": inf.tokenizer.vocab_size,
            "device": str(inf.device),
            "checkpoint": _loaded,
            "architecture": "decoder-only Transformer",
        }
    except Exception as e:
        return {"loaded": False, "error": str(e)}


def list_ckpts() -> list[dict[str, Any]]:
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    db = _db()
    try:
        versions = db.get_versions()
    except Exception:
        versions = []
    version_map = {v["checkpoint_name"]: v for v in versions}
    out = []
    for p in sorted(CKPT_DIR.glob("*.pt")):
        m: dict[str, Any] = {
            "name": p.name,
            "path": str(p),
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "mtime": p.stat().st_mtime,
            "loaded": _loaded == str(p),
        }
        vinfo = version_map.get(p.name, {})
        m["version_label"] = vinfo.get("label")
        m["status"] = vinfo.get("status", "archived")
        try:
            import torch
            ck = torch.load(p, map_location="cpu", weights_only=False)
            m["step"] = ck.get("step")
            m["loss"] = ck.get("loss")
            mc = ck.get("model_config") or {}
            m["d_model"] = mc.get("d_model")
            m["max_seq_len"] = mc.get("max_seq_len")
        except Exception:
            pass
        out.append(m)
    return out


# ---------------------------------------------------------------------------
# Brain version registry
# ---------------------------------------------------------------------------


def _load_versions() -> list[dict[str, Any]]:
    """Load brain versions from the active database adapter."""
    db = _db()
    try:
        return db.get_versions()
    except Exception:
        if VERSIONS_PATH.exists():
            try:
                return json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []


def _save_versions(versions: list[dict[str, Any]]) -> None:
    """Persist brain versions via the database adapter."""
    db = _db()
    for v in versions:
        try:
            db.insert_version(v)
        except Exception:
            pass


def promote_checkpoint(
    checkpoint_name: str,
    label: str,
    promoted_by: str = "system",
) -> dict[str, Any]:
    """Mark a checkpoint as production, demoting any current production.

    **Never auto-promote without evaluation.**  If the checkpoint's brain
    version record has no evaluation, the promotion will still succeed but
    the version is flagged with ``eval_passed=None``.
    """
    versions = _load_versions()
    db = _db()
    # Demote current production
    new_versions = []
    for v in versions:
        if v.get("status") == "production":
            try:
                db.update_version(v["id"], status="archived",
                                  promoted_at=v.get("promoted_at"))
            except Exception:
                v["status"] = "archived"
            new_versions.append(v)
        else:
            new_versions.append(v)

    # Find or create entry
    existing = next(
        (v for v in new_versions if v.get("checkpoint_name") == checkpoint_name),
        None,
    )
    promoted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if existing:
        try:
            db.update_version(
                existing["id"],
                label=label,
                status="production",
                promoted_at=promoted_at,
                promoted_by=promoted_by,
            )
        except Exception:
            pass
        existing.update({
            "label": label,
            "status": "production",
            "promoted_at": promoted_at,
            "promoted_by": promoted_by,
        })
    else:
        record = {
            "id": str(uuid.uuid4()),
            "checkpoint_name": checkpoint_name,
            "label": label,
            "status": "production",
            "promoted_at": promoted_at,
            "promoted_by": promoted_by,
            "created_at": promoted_at,
        }
        try:
            db.insert_version(record)
        except Exception:
            pass
        versions.append(record)
        existing = record

    # Force reload of inference
    global _inf, _loaded
    with _lock:
        _inf = None
        _loaded = None

    return {"ok": True, "checkpoint": checkpoint_name, "label": label,
            "eval_passed": existing.get("eval_passed")}


# ---------------------------------------------------------------------------
# Knowledge (legacy compat)
# ---------------------------------------------------------------------------


def knowledge_items() -> list[dict[str, Any]]:
    if KNOW.exists():
        try:
            return json.loads(KNOW.read_text(encoding="utf-8"))
        except Exception:
            pass
    items = []
    if TRAIN.exists():
        for i, line in enumerate(TRAIN.read_text(encoding="utf-8").splitlines()):
            if line.strip():
                items.append(
                    {"id": f"k-{i}", "text": line.strip(), "approved": True, "source": "train.txt"}
                )
    return items


def save_knowledge(items: list[dict[str, Any]]) -> None:
    KNOW.parent.mkdir(parents=True, exist_ok=True)
    KNOW.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [it["text"] for it in items if it.get("approved") and it.get("text")]
    TRAIN.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------


def _get_store():
    from doof.intelligence.store import get_store
    return get_store()


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def _load_feedback() -> list[dict[str, Any]]:
    """Load feedback from the active database adapter."""
    db = _db()
    try:
        return db.get_feedback()
    except Exception:
        feedback_path = DATA_DIR / "feedback.json"
        if feedback_path.exists():
            try:
                data = json.loads(feedback_path.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
            except Exception:
                pass
        return []


def _save_feedback(items: list[dict[str, Any]]) -> None:
    """Persist feedback via the database adapter."""
    db = _db()
    for item in items:
        try:
            db.insert_feedback(item)
        except Exception:
            pass


def add_feedback(
    prompt: str,
    response: str,
    rating: str,
    correction: str = "",
    created_by: str = "local",
    memories_used: list | None = None,
) -> dict[str, Any]:
    from doof.intelligence.quality import score_response
    db = _db()
    item: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "response": response,
        "rating": rating,
        "correction": correction,
        "created_by": created_by,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "memories_used": memories_used or [],
        "approved": rating == "good" or bool(correction),
    }
    quality = score_response(prompt, correction or response, rating=rating)
    item["quality"] = quality["total"]
    item["training_ready"] = quality["training_ready"]
    try:
        db.insert_feedback(item)
    except Exception:
        _save_feedback(_load_feedback() + [item])
    return item


def approve_feedback(feedback_id: str, approved_by: str = "local") -> dict[str, Any] | None:
    """Promote an approved feedback item into the ``approved_examples`` table.

    This is the **only** sanctioned path from raw conversation feedback to
    training data.  The original feedback is *not* trained on directly.
    """
    db = _db()
    feedback_items = _load_feedback()
    fb = next((f for f in feedback_items if f.get("id") == feedback_id), None)
    if fb is None:
        return None

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    example: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "prompt": fb.get("prompt", ""),
        "response": fb.get("correction") or fb.get("response", ""),
        "rating": fb.get("rating", "good"),
        "correction": fb.get("correction", ""),
        "quality": fb.get("quality", 0),
        "training_ready": fb.get("training_ready", True),
        "approved": True,
        "approved_at": now,
        "approved_by": approved_by,
        "created_by": fb.get("created_by", "local"),
        "created_at": fb.get("created_at", now),
        "source": "feedback",
        "memory_ids": fb.get("memories_used", []),
    }
    try:
        result = db.insert_approved_example(example)
        # Mark the original feedback as approved (but NOT automatically
        # training-ready — it still needs quality scoring)
        db.update_feedback(feedback_id, approved=True)
        result["source_feedback_id"] = feedback_id
        return result
    except Exception:
        # Local fallback
        examples_path = DATA_DIR / "approved_examples.json"
        examples = []
        if examples_path.exists():
            try:
                examples = json.loads(examples_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        examples.append(example)
        examples_path.write_text(
            json.dumps(examples, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        example["source_feedback_id"] = feedback_id
        return example


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _load_nodes() -> list[dict[str, Any]]:
    """Load nodes from the active database adapter."""
    db = _db()
    try:
        return db.get_nodes()
    except Exception:
        if NODES_PATH.exists():
            try:
                data = json.loads(NODES_PATH.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
            except Exception:
                pass
        return []


def _save_nodes(nodes: list[dict[str, Any]]) -> None:
    """Persist nodes via the database adapter (upsert each)."""
    db = _db()
    for n in nodes:
        try:
            db.upsert_node(n)
        except Exception:
            pass


def get_nodes_with_local() -> list[dict[str, Any]]:
    """Return all nodes, auto-updating the local node entry from hardware()."""
    global _local_node_id
    hw = hardware()
    db = _db()

    try:
        nodes = db.get_nodes()
    except Exception:
        nodes = []

    # Check if local node exists
    local_id = "local"
    local_node = next((n for n in nodes if n.get("id") == local_id), None)

    gpu_name = "CPU"
    vram_gb = 0.0
    if hw.get("cuda_available") and hw.get("cuda_devices"):
        dev = hw["cuda_devices"][0]
        gpu_name = dev.get("name", "Unknown GPU")
        vram_gb = dev.get("total_memory_gb", 0.0)
    elif hw.get("mps_available"):
        gpu_name = "Apple MPS"

    now_ts = time.time()
    local_data: dict[str, Any] = {
        "id": local_id,
        "name": platform.node() or "Local-PC",
        "gpu": gpu_name,
        "vram_gb": vram_gb,
        "device": hw.get("device", "cpu"),
        "cuda_available": hw.get("cuda_available", False),
        "platform": hw.get("platform", ""),
        "torch_version": hw.get("torch_version"),
        "status": "online",
        "last_seen": now_ts,
        "is_local": True,
        "training_active": _train.get("running", False),
    }

    if local_node:
        # Update last_seen for local node
        try:
            db.update_node(local_id, **local_data)
        except Exception:
            local_node.update(local_data)
    else:
        try:
            db.upsert_node(local_data)
        except Exception:
            nodes.insert(0, local_data)
    _local_node_id = local_id

    # Mark stale nodes as offline (no heartbeat for 60s)
    for node in nodes:
        if node.get("id") == local_id:
            continue
        last = node.get("last_seen", 0)
        if isinstance(last, (int, float)) and (now_ts - last) > _NODE_TIMEOUT:
            node["status"] = "offline"
            try:
                db.update_node(node["id"], status="offline")
            except Exception:
                pass

    # Re-fetch to get updated state
    try:
        nodes = db.get_nodes()
        # Ensure local node is present with current data
        for n in nodes:
            if n.get("id") == local_id:
                n.update(local_data)
                break
        else:
            nodes.insert(0, local_data)
    except Exception:
        pass

    return nodes


def _mark_local_node_training(training: bool) -> None:
    """Update the local node's training_active flag."""
    global _local_node_id
    if _local_node_id:
        db = _db()
        try:
            db.update_node(_local_node_id, training_active=training)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Training (preserved + enhanced)
# ---------------------------------------------------------------------------


def run_train(epochs: int = 3, resume_from: str | None = None) -> None:
    global _train, _inf, _loaded
    _stop.clear()
    try:
        import torch
        import torch.nn.functional as F
        from torch.amp import autocast
        from tqdm import tqdm
        from doof.training import DOOFTrainer, TrainingConfig

        cfg = TrainingConfig(
            data_path=str(TRAIN),
            checkpoint_dir=str(CKPT_DIR),
            epochs=epochs,
            batch_size=8,
            seq_len=64,
            learning_rate=3e-4,
            save_every=50,
        )
        tr = DOOFTrainer(cfg)
        if resume_from:
            path = (
                Path(resume_from)
                if Path(resume_from).is_absolute()
                else ROOT / resume_from
            )
            if path.exists():
                ck = torch.load(path, map_location=tr.device, weights_only=False)
                tr.model.load_state_dict(ck["model_state_dict"])

        tokens = tr.load_data()
        step = 0
        loss_val = 0.0

        with _lock:
            _train.update({"running": True, "message": "training", "history": []})
        _mark_local_node_training(True)

        total_steps = cfg.epochs * 100
        t_start = time.time()

        for epoch in range(cfg.epochs):
            if _stop.is_set():
                break
            for batch_i in tqdm(range(100), desc=f"Epoch {epoch+1}"):
                if _stop.is_set():
                    break
                tr.model.train()
                x, y = tr.create_batches(tokens)
                tr.optimizer.zero_grad(set_to_none=True)
                with autocast(
                    device_type=tr.device.type,
                    dtype=torch.float16,
                    enabled=tr.device.type == "cuda",
                ):
                    logits = tr.model(x)
                    loss = F.cross_entropy(
                        logits.reshape(-1, logits.size(-1)), y.reshape(-1)
                    )
                tr.scaler.scale(loss).backward()
                tr.scaler.unscale_(tr.optimizer)
                torch.nn.utils.clip_grad_norm_(tr.model.parameters(), 1.0)
                tr.scaler.step(tr.optimizer)
                tr.scaler.update()
                step += 1
                loss_val = float(loss.item())

                elapsed = time.time() - t_start
                speed = step / elapsed if elapsed > 0 else 0.0
                remaining_steps = total_steps - step
                eta = remaining_steps / speed if speed > 0 else None

                with _lock:
                    _train.update(
                        {
                            "step": step,
                            "loss": loss_val,
                            "epoch": epoch + 1,
                            "message": f"epoch {epoch+1}/{cfg.epochs} · step {step}",
                            "speed": round(speed, 2),
                            "eta_seconds": round(eta) if eta else None,
                        }
                    )
                    h = _train["history"]
                    h.append({"step": step, "loss": loss_val})
                    if len(h) > 500:
                        _train["history"] = h[-500:]
                if step % cfg.save_every == 0:
                    tr.save_checkpoint(step, loss_val)

        tr.save_checkpoint(step, loss_val)
        torch.save(
            {
                "model_state_dict": tr.model.state_dict(),
                "step": step,
                "loss": loss_val,
                "model_config": {
                    "vocab_size": tr.tokenizer.vocab_size,
                    "max_seq_len": cfg.seq_len,
                    "d_model": tr.model.d_model,
                },
            },
            CKPT_DIR / "doof_v01.pt",
        )

        # Register brain version after training (as candidate, not production)
        db = _db()
        versions = _load_versions()
        label = f"v{len(versions) + 1}.0.0-candidate"
        try:
            db.insert_version({
                "checkpoint_name": "doof_v01.pt",
                "label": label,
                "status": "candidate",
                "promoted_by": "local",
            })
        except Exception:
            pass

        with _lock:
            _inf = None
            _loaded = None
            _train.update(
                {
                    "running": False,
                    "message": "complete",
                    "step": step,
                    "speed": None,
                    "eta_seconds": None,
                }
            )
        _mark_local_node_training(False)
    except Exception as e:
        with _lock:
            _train.update(
                {
                    "running": False,
                    "message": f"error: {e}",
                    "error": traceback.format_exc(),
                }
            )
        _mark_local_node_training(False)


# ---------------------------------------------------------------------------
# Training stats helper
# ---------------------------------------------------------------------------


def training_stats() -> dict[str, Any]:
    """Return enriched training status including job queue and worker pool."""
    db = _db()

    # Feedback stats
    try:
        feedback = db.get_feedback()
    except Exception:
        feedback = []
    approved = [f for f in feedback if f.get("approved")]
    training_ready = [f for f in feedback if f.get("training_ready")]

    # Approved examples counts
    try:
        ex_counts = db.count_approved_examples()
    except Exception:
        ex_counts = {"total": 0, "approved": 0, "training_ready": 0}

    # Memory stats
    store = _get_store()
    mem_stats = store.stats()

    # Brain versions
    versions = _load_versions()
    production = next(
        (v for v in reversed(versions) if v.get("status") == "production"), None
    )

    # Training jobs queue
    try:
        queued_jobs = db.get_training_jobs(status="queued")
        running_jobs = db.get_training_jobs(status="running")
    except Exception:
        queued_jobs = []
        running_jobs = []

    # Online nodes / workers
    try:
        online_nodes = db.get_online_nodes()
    except Exception:
        online_nodes = []
    workers_online = len(online_nodes)

    with _lock:
        state = dict(_train)

    state["approved_examples"] = ex_counts.get("approved", len(approved))
    state["training_ready_examples"] = ex_counts.get("training_ready", len(training_ready))
    state["total_feedback"] = len(feedback)
    state["memory_count"] = mem_stats["approved"]
    state["brain_version"] = production.get("label") if production else "1.0.0"
    state["production_checkpoint"] = production.get("checkpoint_name") if production else None
    state["training_queue"] = [
        {
            "id": j.get("id"),
            "type": j.get("type", "train"),
            "priority": j.get("priority", 5),
            "created_at": j.get("created_at"),
            "payload": j.get("payload"),
            "assigned_worker": j.get("worker"),
        }
        for j in queued_jobs
    ]
    state["running_jobs"] = [
        {
            "id": j.get("id"),
            "step": j.get("step"),
            "epoch": j.get("epoch"),
            "total_epochs": j.get("total_epochs"),
            "loss": j.get("loss"),
            "worker": j.get("worker"),
        }
        for j in running_jobs
    ]
    state["workers_online"] = workers_online
    state["examples_count"] = ex_counts.get("total", len(approved))
    state["online_nodes"] = [
        {
            "id": n.get("id"),
            "name": n.get("name"),
            "gpu": n.get("gpu"),
            "vram_gb": n.get("vram_gb"),
            "status": n.get("status", "online"),
            "is_local": n.get("is_local", False),
            "training_active": n.get("training_active", False),
        }
        for n in online_nodes
    ]
    return state


# ---------------------------------------------------------------------------
# Training jobs (distributed compute queue)
# ---------------------------------------------------------------------------


def get_training_jobs_api(*, status: str | None = None, limit: int = 50) -> list[dict]:
    db = _db()
    try:
        return db.get_training_jobs(status=status, limit=limit)
    except Exception:
        return []


def create_training_job(
    body: dict[str, Any], created_by: str = "local"
) -> dict[str, Any]:
    """Create a training job and assign it to the strongest online worker."""
    from doof.intelligence.scheduler import assign_training_job

    payload = {
        "epochs": int(body.get("epochs", 3)),
        "seq_len": int(body.get("seq_len", 64)),
        "batch_size": int(body.get("batch_size", 8)),
        "learning_rate": float(body.get("learning_rate", 3e-4)),
        "resume_from": body.get("resume_from"),
        "dataset_version": body.get("dataset_version"),
    }
    priority = int(body.get("priority", 5))
    return assign_training_job(payload=payload, priority=priority,
                               created_by=created_by)


def cancel_training_job(job_id: str) -> bool:
    db = _db()
    try:
        return bool(db.update_training_job(job_id, status="cancelled"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Approved examples API
# ---------------------------------------------------------------------------


def get_approved_examples_api(
    *, approved_only: bool = True, limit: int = 500
) -> list[dict]:
    db = _db()
    try:
        return db.get_approved_examples(
            approved_only=approved_only, training_ready_only=False, limit=limit
        )
    except Exception:
        return []


def add_approved_example(body: dict[str, Any]) -> dict[str, Any]:
    db = _db()
    record = {
        "prompt": (body.get("prompt") or "").strip(),
        "response": (body.get("response") or "").strip(),
        "rating": body.get("rating", "good"),
        "correction": body.get("correction", ""),
        "quality": body.get("quality"),
        "training_ready": body.get("training_ready", True),
        "approved": body.get("approved", True),
        "created_by": body.get("created_by", "local"),
        "source": body.get("source", "manual"),
        "memory_ids": body.get("memory_ids") or [],
    }
    if not record["prompt"] or not record["response"]:
        raise ValueError("prompt and response required")
    try:
        return db.insert_approved_example(record)
    except Exception:
        # Local fallback
        examples_path = DATA_DIR / "approved_examples.json"
        examples = []
        if examples_path.exists():
            try:
                examples = json.loads(examples_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        record.setdefault("approved_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        record.setdefault("approved_by", record["created_by"])
        examples.append(record)
        examples_path.write_text(
            json.dumps(examples, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return record


def delete_approved_example_api(example_id: str) -> bool:
    db = _db()
    try:
        return db.delete_approved_example(example_id)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[api] {args[0]}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        _cors(self)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            # Health
            if path in ("/", "/api/health"):
                _json(self, 200, {"ok": True, "service": "doof", "version": "0.2.0"})

            # Hardware
            elif path == "/api/hardware":
                _json(self, 200, hardware())

            # Model
            elif path == "/api/model":
                _json(self, 200, model_info())

            # Checkpoints (legacy)
            elif path == "/api/checkpoints":
                _json(self, 200, {"checkpoints": list_ckpts()})

            # Model versions
            elif path == "/api/models/versions":
                _json(self, 200, {"checkpoints": list_ckpts(), "versions": _load_versions()})

            # Training status (enriched)
            elif path == "/api/training":
                _json(self, 200, training_stats())

            # Training jobs queue
            elif path == "/api/training/jobs":
                _json(self, 200, {"jobs": get_training_jobs_api()})

            # Approved examples
            elif path == "/api/approved_examples":
                approved_only = urlparse(self.path).query.lower() != "approved=false"
                _json(self, 200, {"examples": get_approved_examples_api(approved_only=approved_only)})

            # Approved examples count
            elif path == "/api/approved_examples/count":
                db = _db()
                try:
                    counts = db.count_approved_examples()
                except Exception:
                    counts = {"total": 0, "approved": 0, "training_ready": 0}
                _json(self, 200, counts)

            # Network summary (connected users / GPU / VRAM / status)
            elif path == "/api/network":
                nodes = get_nodes_with_local()
                online = [n for n in nodes if n.get("status") == "online"]
                total_vram = sum(n.get("vram_gb", 0) or 0 for n in online)
                connected_users = sum(1 for n in online if not n.get("is_local")) + 1  # +1 for local
                _json(
                    self,
                    200,
                    {
                        "nodes": nodes,
                        "nodes_online": len(online),
                        "connected_users": connected_users,
                        "total_vram_gb": round(total_vram, 1),
                        "training_active": any(n.get("training_active") for n in online),
                        "workers_online": len(online),
                    },
                )

            # Settings
            elif path == "/api/settings":
                with _lock:
                    _json(self, 200, dict(_settings))

            # Cloud
            elif path == "/api/cloud":
                from doof.cloud import cloud_status
                _json(self, 200, cloud_status())

            # Knowledge (legacy)
            elif path == "/api/knowledge":
                items = knowledge_items()
                _json(
                    self,
                    200,
                    {
                        "items": items,
                        "text": "\n".join(
                            i["text"] for i in items if i.get("approved")
                        ),
                    },
                )

            # Memory
            elif path == "/api/memory":
                store = _get_store()
                _json(
                    self,
                    200,
                    {
                        "memories": store.list_all(),
                        "stats": store.stats(),
                    },
                )

            # Feedback
            elif path == "/api/feedback":
                items = _load_feedback()
                training_ready = [f for f in items if f.get("training_ready")]
                _json(
                    self,
                    200,
                    {
                        "items": items,
                        "total": len(items),
                        "approved": sum(1 for f in items if f.get("approved")),
                        "training_ready": len(training_ready),
                    },
                )

            # Nodes
            elif path == "/api/nodes":
                nodes = get_nodes_with_local()
                total_vram = sum(n.get("vram_gb", 0) or 0 for n in nodes if n.get("status") == "online")
                online = [n for n in nodes if n.get("status") == "online"]
                _json(
                    self,
                    200,
                    {
                        "nodes": nodes,
                        "nodes_online": len(online),
                        "connected_users": len(online),
                        "total_vram_gb": round(total_vram, 1),
                        "training_active": any(n.get("training_active") for n in online),
                    },
                )

            # Current session profile
            elif path == "/api/me":
                _json(self, 200, {"profile": _profile_from_token(_bearer_token(self))})

            # Auth capabilities (which login options to show)
            elif path == "/api/auth/config":
                _json(self, 200, auth_config())

            # Scheduler
            elif path == "/api/scheduler":
                from doof.intelligence.scheduler import get_scheduler
                _json(self, 200, get_scheduler().status())

            else:
                _json(self, 404, {"error": "not found"})

        except Exception as e:
            _json(self, 500, {"error": str(e), "trace": traceback.format_exc()})

    def do_POST(self) -> None:
        global _inf, _loaded
        path = urlparse(self.path).path
        body = _body(self)
        try:
            # Generate
            if path == "/api/generate":
                prompt = (body.get("prompt") or "").strip()
                if not prompt:
                    _json(self, 400, {"error": "prompt required"})
                    return

                with _lock:
                    temp = float(body.get("temperature", _settings["temperature"]))
                    mx = int(body.get("max_new_tokens", _settings["max_new_tokens"]))
                    tk = int(body.get("top_k", _settings.get("top_k", 50)))

                # RAG retrieval
                memories_used: list[dict] = []
                try:
                    from doof.intelligence.rag import retrieve_memories, build_context
                    memories_used = retrieve_memories(prompt, top_k=5)
                    if memories_used:
                        context = build_context(memories_used)
                        augmented_prompt = f"{context}\n\nUser: {prompt}\nDOOF:"
                        # Increment usage on retrieved memories
                        store = _get_store()
                        for mem in memories_used:
                            store.increment_usage(mem["id"])
                    else:
                        augmented_prompt = prompt
                except Exception:
                    augmented_prompt = prompt

                inf = get_inf()
                t0 = time.time()
                text = inf.generate(augmented_prompt, max_new_tokens=mx, temperature=temp, top_k=tk)
                if text.startswith(augmented_prompt):
                    text = text[len(augmented_prompt):].lstrip()

                _json(
                    self,
                    200,
                    {
                        "text": text,
                        "prompt": prompt,
                        "elapsed_ms": int((time.time() - t0) * 1000),
                        "memories_used": memories_used,
                    },
                )

            # Auth
            elif path == "/api/auth/signup":
                code, payload = auth_signup(body)
                _json(self, code, payload)

            elif path == "/api/auth/login":
                code, payload = auth_login(body)
                _json(self, code, payload)

            elif path == "/api/auth/resend":
                code, payload = auth_resend((body.get("email") or "").strip().lower())
                _json(self, code, payload)

            elif path == "/api/auth/oauth":
                code, payload = auth_oauth(body.get("access_token") or "")
                _json(self, code, payload)

            elif path == "/api/auth/logout":
                token = _bearer_token(self)
                if token and SESSIONS_PATH.exists():
                    try:
                        sessions = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
                        sessions = [s for s in sessions if s.get("token") != token]
                        SESSIONS_PATH.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                _json(self, 200, {"ok": True})

            # Training start
            elif path == "/api/training/start":
                with _lock:
                    if _train["running"]:
                        _json(self, 409, {"error": "already running"})
                        return
                    _train["running"] = True
                    _train["message"] = "starting"
                threading.Thread(
                    target=run_train,
                    kwargs={
                        "epochs": int(body.get("epochs", 3)),
                        "resume_from": body.get("resume_from"),
                    },
                    daemon=True,
                ).start()
                _json(self, 200, {"ok": True})

            # Training stop
            elif path == "/api/training/stop":
                _stop.set()
                _json(self, 200, {"ok": True})

            # Build dataset
            elif path == "/api/training/build_dataset":
                from doof.intelligence.dataset import build_dataset
                result = build_dataset(
                    version=body.get("version"),
                    min_quality=float(body.get("min_quality", 55.0)),
                )
                with _lock:
                    _train["dataset_version"] = result.get("version")
                _json(self, 200, result)

            # Create training job (distributed)
            elif path == "/api/training/jobs":
                job = create_training_job(body)
                _json(self, 201, {"ok": True, "job": job})

            # Cancel training job
            elif re.match(r"^/api/training/jobs/[^/]+/cancel$", path):
                job_id = path.split("/")[4]
                ok = cancel_training_job(job_id)
                _json(self, 200, {"ok": ok, "cancelled": job_id})

            # Knowledge (legacy)
            elif path == "/api/knowledge":
                if "items" in body:
                    save_knowledge(body["items"])
                    _json(self, 200, {"ok": True, "count": len(body["items"])})
                elif "text" in body:
                    lines = [l.strip() for l in body["text"].splitlines() if l.strip()]
                    items = [
                        {"id": f"k-{i}", "text": l, "approved": True, "source": "edit"}
                        for i, l in enumerate(lines)
                    ]
                    save_knowledge(items)
                    _json(self, 200, {"ok": True, "count": len(items)})
                else:
                    _json(self, 400, {"error": "items or text required"})

            # Memory — add
            elif path == "/api/memory":
                content = (body.get("content") or body.get("text") or "").strip()
                if not content:
                    _json(self, 400, {"error": "content required"})
                    return
                store = _get_store()
                item = store.add(
                    content,
                    created_by=body.get("created_by", "local"),
                    importance=body.get("importance", "medium"),
                    category=body.get("category", "general"),
                    tags=body.get("tags") or [],
                    approved=body.get("approved", True),
                )
                _json(self, 201, {"ok": True, "memory": item})

            # Memory approve
            elif re.match(r"^/api/memory/[^/]+/approve$", path):
                mem_id = path.split("/")[3]
                store = _get_store()
                updated = store.update(mem_id, approved=body.get("approved", True))
                if updated:
                    _json(self, 200, {"ok": True, "memory": updated})
                else:
                    _json(self, 404, {"error": "memory not found"})

            # Feedback
            elif path == "/api/feedback":
                prompt = (body.get("prompt") or "").strip()
                response = (body.get("response") or "").strip()
                rating = (body.get("rating") or "").strip()
                if not prompt or not response or rating not in ("good", "bad"):
                    _json(self, 400, {"error": "prompt, response, and rating (good|bad) required"})
                    return
                item = add_feedback(
                    prompt=prompt,
                    response=response,
                    rating=rating,
                    correction=body.get("correction", ""),
                    created_by=body.get("created_by", "local"),
                    memories_used=body.get("memories_used"),
                )
                _json(self, 201, {"ok": True, "feedback": item})

            # Approve feedback → move to approved_examples
            elif re.match(r"^/api/feedback/[^/]+/approve$", path):
                fb_id = path.split("/")[3]
                result = approve_feedback(fb_id, approved_by=body.get("approved_by", "local"))
                if result:
                    _json(self, 200, {"ok": True, "example": result})
                else:
                    _json(self, 404, {"error": "feedback not found"})

            # Node register
            elif path == "/api/nodes/register":
                name = (body.get("name") or platform.node() or "Unknown").strip()
                db = _db()
                nodes = _load_nodes()
                now_ts = time.time()
                existing = next((n for n in nodes if n.get("name") == name), None)

                node_data: dict[str, Any] = {
                    "name": name,
                    "gpu": body.get("gpu", "Unknown GPU"),
                    "vram_gb": float(body.get("vram_gb", 0)),
                    "device": body.get("device", "cpu"),
                    "cuda_available": body.get("cuda_available", False),
                    "platform": body.get("platform", platform.system()),
                    "torch_version": body.get("torch_version"),
                    "status": "online",
                    "last_seen": now_ts,
                    "is_local": body.get("is_local", False),
                    "training_active": body.get("training_active", False),
                }

                if existing:
                    node_data["id"] = existing["id"]
                try:
                    saved = db.upsert_node(node_data)
                    saved.setdefault("id", node_data["id"])
                    saved.setdefault("registered_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                except Exception:
                    saved = node_data

                # Track local node id
                if saved.get("is_local"):
                    global _local_node_id
                    _local_node_id = saved["id"]

                _json(self, 201, {"ok": True, "node": saved})

            # Node heartbeat
            elif path == "/api/nodes/heartbeat":
                node_id = body.get("id")
                db = _db()
                # Find node by id or name
                nodes = _load_nodes()
                node = next((n for n in nodes if n.get("id") == node_id), None)
                if node is None and node_id:
                    # Try matching by name
                    node = next((n for n in nodes if n.get("name") == node_id), None)
                if node:
                    update_fields = {
                        "last_seen": time.time(),
                        "status": "online",
                        "training_active": body.get("training_active", False),
                    }
                    if body.get("gpu"):
                        update_fields["gpu"] = body["gpu"]
                    if body.get("vram_gb") is not None:
                        update_fields["vram_gb"] = float(body["vram_gb"])
                    try:
                        db.update_node(node["id"], **update_fields)
                    except Exception:
                        node.update(update_fields)
                        _save_nodes(nodes)
                    _json(self, 200, {"ok": True})
                else:
                    _json(self, 404, {"error": "node not found"})

            # Model promote
            elif path == "/api/models/promote":
                ckpt_name = body.get("checkpoint_name") or body.get("name")
                label = body.get("label") or ckpt_name
                if not ckpt_name:
                    _json(self, 400, {"error": "checkpoint_name required"})
                    return
                result = promote_checkpoint(
                    ckpt_name, label, promoted_by=body.get("promoted_by", "local")
                )
                _json(self, 200, result)

            # Promote with evaluation gate
            elif path == "/api/models/promote_with_eval":
                ckpt_name = body.get("checkpoint_name") or body.get("name")
                if not ckpt_name:
                    _json(self, 400, {"error": "checkpoint_name required"})
                    return
                # Evaluate first
                from doof.intelligence.evaluate import evaluate_checkpoint
                eval_result = evaluate_checkpoint(ckpt_name)
                db = _db()
                # Find or create the version record
                versions = _load_versions()
                vinfo = next((v for v in versions if v.get("checkpoint_name") == ckpt_name), None)
                if vinfo:
                    db.update_version(
                        vinfo["id"],
                        eval_result=eval_result,
                        eval_passed=eval_result.get("status") == "ok",
                        perplexity=eval_result.get("perplexity"),
                        evaluated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    )
                # Only promote if evaluation passes
                if eval_result.get("status") == "ok" and eval_result.get("perplexity") is not None:
                    result = promote_checkpoint(
                        ckpt_name,
                        body.get("label") or ckpt_name,
                        promoted_by=body.get("promoted_by", "local"),
                    )
                    _json(self, 200, {"ok": True, "promoted": result, "evaluation": eval_result})
                else:
                    _json(self, 200, {
                        "ok": False,
                        "reason": "evaluation_failed",
                        "evaluation": eval_result,
                    })

            # Add approved example
            elif path == "/api/approved_examples":
                try:
                    record = add_approved_example(body)
                    _json(self, 201, {"ok": True, "example": record})
                except ValueError as e:
                    _json(self, 400, {"error": str(e)})

            # Model load
            elif path == "/api/model/load":
                with _lock:
                    _inf = None
                    _loaded = None
                try:
                    get_inf(body.get("checkpoint") or body.get("path"))
                    _json(self, 200, {"ok": True, "checkpoint": _loaded})
                except Exception as e:
                    _json(self, 400, {"error": str(e)})

            # Reload
            elif path == "/api/reload":
                with _lock:
                    _inf = None
                    _loaded = None
                _json(self, 200, {"ok": True})

            # Settings
            elif path == "/api/settings":
                with _lock:
                    for k in ("temperature", "max_new_tokens", "top_k", "context_length"):
                        if k in body:
                            _settings[k] = (
                                float(body[k]) if k == "temperature" else int(body[k])
                            )
                    SETT.parent.mkdir(parents=True, exist_ok=True)
                    SETT.write_text(json.dumps(_settings, indent=2, ensure_ascii=False), encoding="utf-8")
                    _json(self, 200, dict(_settings))

            else:
                _json(self, 404, {"error": "not found"})

        except Exception as e:
            _json(self, 500, {"error": str(e), "trace": traceback.format_exc()})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        try:
            # DELETE /api/memory/{id}
            m = re.match(r"^/api/memory/([^/]+)$", path)
            if m:
                mem_id = m.group(1)
                store = _get_store()
                if store.delete(mem_id):
                    _json(self, 200, {"ok": True, "deleted": mem_id})
                else:
                    _json(self, 404, {"error": "memory not found"})
                return

            # DELETE /api/nodes/{id}
            m = re.match(r"^/api/nodes/([^/]+)$", path)
            if m:
                node_id = m.group(1)
                db = _db()
                try:
                    ok = db.delete_node(node_id)
                except Exception:
                    ok = False
                if not ok:
                    # Try local fallback
                    nodes = _load_nodes()
                    original_len = len(nodes)
                    nodes = [n for n in nodes if n.get("id") != node_id]
                    if len(nodes) < original_len:
                        _save_nodes(nodes)
                        ok = True
                if ok:
                    _json(self, 200, {"ok": True, "deleted": node_id})
                else:
                    _json(self, 404, {"error": "node not found"})
                return

            # DELETE /api/approved_examples/{id}
            m = re.match(r"^/api/approved_examples/([^/]+)$", path)
            if m:
                ex_id = m.group(1)
                ok = delete_approved_example_api(ex_id)
                if ok:
                    _json(self, 200, {"ok": True, "deleted": ex_id})
                else:
                    _json(self, 404, {"error": "example not found"})
                return

            _json(self, 404, {"error": "not found"})

        except Exception as e:
            _json(self, 500, {"error": str(e)})


# ---------------------------------------------------------------------------
# Background heartbeat thread (node liveness)
# ---------------------------------------------------------------------------


_heartbeat_thread: threading.Thread | None = None


def _heartbeat_loop() -> None:
    """Background thread that sends heartbeats for the local node."""
    while not _stop.is_set():
        try:
            get_nodes_with_local()
        except Exception:
            pass
        _stop.wait(_HEARTBEAT_INTERVAL)


def _start_heartbeat() -> None:
    global _heartbeat_thread
    if _heartbeat_thread and _heartbeat_thread.is_alive():
        return
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, daemon=True, name="doof-heartbeat"
    )
    _heartbeat_thread.start()


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if SETT.exists():
        try:
            _settings.update(json.loads(SETT.read_text(encoding="utf-8")))
        except Exception:
            pass

    # Register local node on startup
    get_nodes_with_local()

    # Start background heartbeat
    _start_heartbeat()

    s = ThreadingHTTPServer((host, port), Handler)
    print(f"DOOF API v0.2 listening on http://{host}:{port}")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        s.shutdown()


if __name__ == "__main__":
    run_server()
