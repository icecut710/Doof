"""DOOF Database Abstraction — Supabase adapter.

Mirrors the exact interface of local.py but routes all reads/writes
through the Supabase REST API.  Requires environment variables:

    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (for server-side writes)
    SUPABASE_ANON_KEY      (for client reads)

Tables required in Supabase (see supabase/schema.sql):
    memories, feedback, nodes, brain_versions, training_jobs,
    approved_examples

This module is intentionally NOT imported unless Supabase is configured.
The API layer always uses get_db() from __init__.py which selects the
correct backend automatically.
"""
from __future__ import annotations

import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
_TIMEOUT = 5


class SupabaseError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {
        "apikey": _KEY,
        "Authorization": f"Bearer {_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _get(table: str, params: str = "") -> list[dict[str, Any]]:
    url = f"{_URL}/rest/v1/{table}?{params}"
    req = Request(url, headers=_headers(), method="GET")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except URLError as e:
        raise SupabaseError(f"GET {table} failed: {e}") from e


def _post(table: str, data: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(data).encode()
    req = Request(f"{_URL}/rest/v1/{table}", data=body, headers=_headers(), method="POST")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            return result[0] if isinstance(result, list) and result else result
    except URLError as e:
        raise SupabaseError(f"POST {table} failed: {e}") from e


def _delete(table: str, id_value: str) -> bool:
    url = f"{_URL}/rest/v1/{table}?id=eq.{id_value}"
    req = Request(url, headers=_headers(), method="DELETE")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status in (200, 204)
    except URLError as e:
        raise SupabaseError(f"DELETE {table} failed: {e}") from e


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _patch(table: str, id_value: str, data: dict[str, Any]) -> dict[str, Any] | list:
    """PATCH a single row by primary key, returning the updated record."""
    url = f"{_URL}/rest/v1/{table}?id=eq.{id_value}"
    body = json.dumps(data).encode()
    h = _headers()
    h["Prefer"] = "return=representation"
    req = Request(url, data=body, headers=h, method="PATCH")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            if isinstance(result, list):
                return result[0] if result else {}
            return result
    except URLError as e:
        raise SupabaseError(f"PATCH {table} failed: {e}") from e


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

def get_memories(*, approved_only: bool = False) -> list[dict[str, Any]]:
    q = "order=created_at.desc"
    if approved_only:
        q += "&approved=eq.true"
    return _get("memories", q)


def insert_memory(content: str, **kwargs: Any) -> dict[str, Any]:
    return _post("memories", {
        "content": content,
        "created_by": kwargs.get("created_by", "local"),
        "importance": kwargs.get("importance", "medium"),
        "category": kwargs.get("category", "general"),
        "tags": kwargs.get("tags") or [],
        "usage_count": 0,
        "approved": kwargs.get("approved", True),
    })


def delete_memory(memory_id: str) -> bool:
    return _delete("memories", memory_id)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def get_feedback() -> list[dict[str, Any]]:
    return _get("feedback", "order=created_at.desc")


def insert_feedback(record: dict[str, Any]) -> dict[str, Any]:
    return _post("feedback", record)


def update_feedback(feedback_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a feedback record by id.  Returns the updated record or None."""
    try:
        data = _patch("feedback", feedback_id, fields)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def get_nodes() -> list[dict[str, Any]]:
    return _get("nodes", "order=last_seen.desc")


def upsert_node(node: dict[str, Any]) -> dict[str, Any]:
    # Supabase upsert via Prefer: resolution=merge-duplicates
    body = json.dumps(node).encode()
    h = _headers()
    h["Prefer"] = "resolution=merge-duplicates,return=representation"
    req = Request(f"{_URL}/rest/v1/nodes", data=body, headers=h, method="POST")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            return result[0] if isinstance(result, list) and result else result
    except URLError as e:
        raise SupabaseError(f"Upsert nodes failed: {e}") from e


def delete_node(node_id: str) -> bool:
    return _delete("nodes", node_id)


def update_node(node_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a node record by id.  Returns the updated record or None."""
    try:
        data = _patch("nodes", node_id, fields)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Brain versions
# ---------------------------------------------------------------------------

def get_versions() -> list[dict[str, Any]]:
    return _get("brain_versions", "order=created_at.desc")


def insert_version(record: dict[str, Any]) -> dict[str, Any]:
    return _post("brain_versions", record)


def update_version(version_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a brain version record by id."""
    try:
        data = _patch("brain_versions", version_id, fields)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# APPROVED EXAMPLES
# ---------------------------------------------------------------------------

def get_approved_examples(
    *,
    approved_only: bool = True,
    training_ready_only: bool = True,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    params = []
    if approved_only:
        params.append("approved=eq.true")
    if training_ready_only:
        params.append("training_ready=eq.true")
    q = f"order=created_at.desc&limit={limit}"
    if params:
        q = "&".join(params) + "&" + q
    return _get("approved_examples", q)


def insert_approved_example(record: dict[str, Any]) -> dict[str, Any]:
    return _post("approved_examples", record)


def delete_approved_example(example_id: str) -> bool:
    return _delete("approved_examples", example_id)


def count_approved_examples() -> dict[str, int]:
    """Return counts of approved examples."""
    try:
        total = len(_get("approved_examples", "select=id"))
        approved = len(_get("approved_examples", "approved=eq.true&select=id"))
        training_ready = len(_get("approved_examples", "training_ready=eq.true&select=id"))
        return {"total": total, "approved": approved, "training_ready": training_ready}
    except Exception:
        return {"total": 0, "approved": 0, "training_ready": 0}


# ---------------------------------------------------------------------------
# TRAINING JOBS (distributed compute queue)
# ---------------------------------------------------------------------------

def get_training_jobs(
    *,
    status: str | None = None,
    worker_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params = []
    if status:
        params.append(f"status=eq.{status}")
    if worker_id:
        params.append(f"worker=eq.{worker_id}")
    q = "order=created_at.desc"
    if params:
        q = "&".join(params) + "&" + q
    return _get("training_jobs", q)


def insert_training_job(record: dict[str, Any]) -> dict[str, Any]:
    return _post("training_jobs", record)


def update_training_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a training job record by id."""
    try:
        data = _patch("training_jobs", job_id, fields)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


def claim_training_job(job_id: str, worker_id: str) -> dict[str, Any] | None:
    """Atomically claim a queued training job.  Uses a filter so only
    ``status=eq.queued`` rows are updated."""
    url = f"{_URL}/rest/v1/training_jobs?id=eq.{job_id}&status=eq.queued"
    body = json.dumps(
        {"status": "running", "worker": worker_id, "started_at": _now_iso()}
    ).encode()
    h = _headers()
    h["Prefer"] = "return=representation"
    req = Request(url, data=body, headers=h, method="PATCH")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            if isinstance(result, list) and result:
                return result[0]
    except URLError:
        pass
    return None


def delete_training_job(job_id: str) -> bool:
    return _delete("training_jobs", job_id)


# ---------------------------------------------------------------------------
# Worker selection helpers
# ---------------------------------------------------------------------------

def get_online_nodes() -> list[dict[str, Any]]:
    """Return nodes that are currently online (status=online)."""
    return _get("nodes", "status=eq.online&order=last_seen.desc")


def get_strongest_online_worker() -> dict[str, Any] | None:
    """Return the online node with the most VRAM, or None if none online."""
    online = get_online_nodes()
    if not online:
        return None
    return sorted(online, key=lambda n: n.get("vram_gb", 0), reverse=True)[0]


def get_compute_jobs(
    *,
    status: str | None = None,
    worker_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params = [f"limit={limit}"]
    if status:
        params.append(f"status=eq.{status}")
    if worker_id:
        params.append(f"worker_node=eq.{worker_id}")
    q = "order=created_at.desc&" + "&".join(params)
    try:
        return _get("compute_jobs", q)
    except Exception:
        return []


def insert_compute_job(record: dict[str, Any]) -> dict[str, Any]:
    return _post("compute_jobs", record)


def update_compute_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    try:
        data = _patch("compute_jobs", job_id, fields)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


def claim_compute_job(job_id: str, worker_id: str) -> dict[str, Any] | None:
    url = f"{_URL}/rest/v1/compute_jobs?id=eq.{job_id}&status=eq.queued"
    body = json.dumps(
        {
            "status": "running",
            "worker_node": worker_id,
            "started_at": _now_iso(),
        }
    ).encode()
    h = _headers()
    h["Prefer"] = "return=representation"
    req = Request(url, data=body, headers=h, method="PATCH")
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            result = json.loads(resp.read())
            if isinstance(result, list) and result:
                return result[0]
    except URLError:
        pass
    return None


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

def list_models() -> list[dict[str, Any]]:
    try:
        data = _get("model_registry", params="order=version.desc")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def insert_model(model: dict[str, Any]) -> dict[str, Any]:
    return _post("model_registry", model)


def update_model(model_id: str, version: str | None = None, **fields: Any) -> dict[str, Any] | None:
    """Update a model registry row.

    Uses (model_id, version) composite key when version is provided,
    otherwise falls back to UUID id for backward compatibility.
    """
    try:
        if version:
            # Composite key lookup
            url = f"{_URL}/rest/v1/model_registry?model_id=eq.{model_id}&version=eq.{version}"
            body = json.dumps(fields).encode()
            h = _headers()
            h["Prefer"] = "return=representation"
            req = Request(url, data=body, headers=h, method="PATCH")
            with urlopen(req, timeout=_TIMEOUT) as resp:
                result = json.loads(resp.read())
                if isinstance(result, list):
                    return result[0] if result else None
                return result
        else:
            # UUID id fallback (legacy callers)
            data = _patch("model_registry", model_id, fields)
            return data if isinstance(data, dict) and data else None
    except Exception:
        return None


def delete_model(model_id: str, version: str | None = None) -> bool:
    """Delete a model registry row.

    Uses (model_id, version) composite key when version is provided,
    otherwise falls back to UUID id for backward compatibility.
    """
    try:
        if version:
            url = f"{_URL}/rest/v1/model_registry?model_id=eq.{model_id}&version=eq.{version}"
        else:
            url = f"{_URL}/rest/v1/model_registry?id=eq.{model_id}"
        h = _headers()
        req = Request(url, headers=h, method="DELETE")
        with urlopen(req, timeout=_TIMEOUT):
            return True
    except URLError:
        return False


# ---------------------------------------------------------------------------
# Model blob storage (Supabase Storage)
# ---------------------------------------------------------------------------

_MODEL_BUCKET = "doof-models"


def _storage_upload(bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes to a Supabase Storage bucket. Returns the public URL."""
    import urllib.parse
    encoded_path = urllib.parse.quote(path, safe="/-_.")
    url = f"{_URL}/storage/v1/object/{bucket}/{encoded_path}"
    h = {
        "apikey": _KEY,
        "Authorization": f"Bearer {_KEY}",
        "Content-Type": content_type,
    }
    req = Request(url, data=data, headers=h, method="POST")
    try:
        with urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())
            # Supabase returns { "Key": "bucket/path" }
            return f"{_URL}/storage/v1/object/public/{bucket}/{encoded_path}"
    except URLError as e:
        # If 409 Conflict (already exists), return the public URL anyway
        if hasattr(e, "code") and e.code == 409:
            return f"{_URL}/storage/v1/object/public/{bucket}/{encoded_path}"
        raise SupabaseError(f"Storage upload failed: {e}") from e


def upload_model_blob(model_id: str, version: str, file_path: str, sha256: str = "") -> str:
    """Upload a .pt checkpoint to Supabase Storage. Returns the public download URL.

    The file is uploaded to ``doof-models/{model_id}/{version}.pt``.
    """
    from pathlib import Path

    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {file_path}")

    data = p.read_bytes()
    blob_path = f"{model_id}/{version}.pt"
    url = _storage_upload(_MODEL_BUCKET, blob_path, data)

    # Also upload the sidecar .json if it exists
    meta = p.with_suffix(".json")
    if meta.is_file():
        try:
            _storage_upload(_MODEL_BUCKET, f"{model_id}/{version}.json", meta.read_bytes(), "application/json")
        except Exception:
            pass

    return url


def get_model_download_url(model_id: str, version: str) -> str:
    """Return the canonical public URL for a model checkpoint in storage."""
    import urllib.parse
    encoded_id = urllib.parse.quote(model_id, safe="")
    encoded_ver = urllib.parse.quote(version, safe="")
    return f"{_URL}/storage/v1/object/public/{_MODEL_BUCKET}/{encoded_id}/{encoded_ver}.pt"
