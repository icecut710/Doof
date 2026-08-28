"""DOOF Database Abstraction — Local JSON adapter.

This module provides the same interface as supabase.py but stores all
data on disk in data/*.json files.  It is the default (offline-first) backend.

All public functions return plain Python dicts/lists so the API layer
never needs to know which backend is in use.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from doof.paths import bundle_root, user_data_dir
    ROOT = bundle_root()
    DATA = user_data_dir()
except Exception:
    ROOT = Path(__file__).resolve().parents[1]
    DATA = ROOT / "data"


def _read(file: Path) -> list[dict[str, Any]]:
    if not file.exists():
        return []
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(file: Path, data: list[dict[str, Any]]) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

_MEMORIES = DATA / "memories.json"


def get_memories(*, approved_only: bool = False) -> list[dict[str, Any]]:
    items = _read(_MEMORIES)
    if approved_only:
        items = [i for i in items if i.get("approved")]
    return items


def insert_memory(content: str, **kwargs: Any) -> dict[str, Any]:
    items = _read(_MEMORIES)
    item: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "content": content,
        "created_at": _now(),
        "created_by": kwargs.get("created_by", "local"),
        "importance": kwargs.get("importance", "medium"),
        "category": kwargs.get("category", "general"),
        "tags": kwargs.get("tags") or [],
        "usage_count": 0,
        "approved": kwargs.get("approved", True),
    }
    items.append(item)
    _write(_MEMORIES, items)
    return item


def delete_memory(memory_id: str) -> bool:
    items = _read(_MEMORIES)
    new = [i for i in items if i.get("id") != memory_id]
    if len(new) == len(items):
        return False
    _write(_MEMORIES, new)
    return True


# ---------------------------------------------------------------------------
# Feedback / Examples
# ---------------------------------------------------------------------------

_FEEDBACK = DATA / "feedback.json"


def get_feedback() -> list[dict[str, Any]]:
    return _read(_FEEDBACK)


def insert_feedback(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_FEEDBACK)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    items.append(record)
    _write(_FEEDBACK, items)
    return record


def update_feedback(feedback_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a feedback record by id.  Returns the updated record or None."""
    items = _read(_FEEDBACK)
    rec = next((f for f in items if f.get("id") == feedback_id), None)
    if rec is None:
        return None
    rec.update(fields)
    _write(_FEEDBACK, items)
    return rec


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

_NODES = DATA / "nodes.json"


def get_nodes() -> list[dict[str, Any]]:
    items = _read(_NODES)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for n in items:
        nid = str(n.get("id") or "")
        if not nid or nid in seen:
            continue
        seen.add(nid)
        out.append(n)
    return out


def upsert_node(node: dict[str, Any]) -> dict[str, Any]:
    nodes = _read(_NODES)
    nid = node.get("id")
    mid = node.get("machine_id")
    existing = None
    if nid:
        existing = next((n for n in nodes if n.get("id") == nid), None)
    if existing is None and mid:
        existing = next((n for n in nodes if n.get("machine_id") == mid), None)
    if existing:
        existing.update(node)
        existing.setdefault("id", nid or existing.get("id") or str(uuid.uuid4()))
        node = existing
    else:
        node.setdefault("id", str(uuid.uuid4()))
        nodes.append(node)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for n in nodes:
        i = str(n.get("id") or "")
        if not i or i in seen:
            continue
        seen.add(i)
        out.append(n)
    _write(_NODES, out)
    return node


def delete_node(node_id: str) -> bool:
    nodes = _read(_NODES)
    new = [n for n in nodes if n.get("id") != node_id]
    if len(new) == len(nodes):
        return False
    _write(_NODES, new)
    return True


def update_node(node_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a node record by id.  Returns the updated record or None."""
    nodes = _read(_NODES)
    rec = next((n for n in nodes if n.get("id") == node_id), None)
    if rec is None:
        return None
    rec.update(fields)
    _write(_NODES, nodes)
    return rec


# ---------------------------------------------------------------------------
# Brain versions
# ---------------------------------------------------------------------------

_VERSIONS = DATA / "brain_versions.json"


def get_versions() -> list[dict[str, Any]]:
    return _read(_VERSIONS)


def insert_version(record: dict[str, Any]) -> dict[str, Any]:
    versions = _read(_VERSIONS)
    # Demote existing production
    for v in versions:
        if v.get("status") == "production" and record.get("status") == "production":
            v["status"] = "archived"
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    versions.append(record)
    _write(_VERSIONS, versions)
    return record


def update_version(version_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a brain version record by id."""
    versions = _read(_VERSIONS)
    rec = next((v for v in versions if v.get("id") == version_id), None)
    if rec is None:
        return None
    rec.update(fields)
    _write(_VERSIONS, versions)
    return rec


# ---------------------------------------------------------------------------
# APPROVED EXAMPLES
# ---------------------------------------------------------------------------

_EXAMPLES = DATA / "approved_examples.json"


def get_approved_examples(
    *,
    approved_only: bool = True,
    training_ready_only: bool = True,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    items = _read(_EXAMPLES)
    if approved_only:
        items = [i for i in items if i.get("approved", True)]
    if training_ready_only:
        items = [i for i in items if i.get("training_ready", True)]
    # Sort by quality descending, then newest
    items.sort(key=lambda x: (x.get("quality", 0), x.get("created_at", "")), reverse=True)
    return items[:limit]


def insert_approved_example(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_EXAMPLES)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    record.setdefault("created_by", "local")
    record.setdefault("approved", True)
    record.setdefault("training_ready", True)
    record.setdefault("approved_at", _now())
    record.setdefault("approved_by", record.get("created_by", "local"))
    record.setdefault("source", "feedback")
    record.setdefault("memory_ids", [])
    items.append(record)
    _write(_EXAMPLES, items)
    return record


def delete_approved_example(example_id: str) -> bool:
    items = _read(_EXAMPLES)
    new = [i for i in items if i.get("id") != example_id]
    if len(new) == len(items):
        return False
    _write(_EXAMPLES, new)
    return True


def count_approved_examples() -> dict[str, int]:
    items = _read(_EXAMPLES)
    return {
        "total": len(items),
        "approved": sum(1 for i in items if i.get("approved")),
        "training_ready": sum(1 for i in items if i.get("training_ready")),
    }


# ---------------------------------------------------------------------------
# TRAINING JOBS (distributed compute queue)
# ---------------------------------------------------------------------------

_JOBS = DATA / "training_jobs.json"


def get_training_jobs(
    *,
    status: str | None = None,
    worker_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    items = _read(_JOBS)
    if status:
        items = [j for j in items if j.get("status") == status]
    if worker_id:
        items = [j for j in items if j.get("worker") == worker_id]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def insert_training_job(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_JOBS)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    record.setdefault("status", "queued")
    record.setdefault("priority", 5)
    record.setdefault("created_by", "local")
    record.setdefault("payload", {})
    items.append(record)
    _write(_JOBS, items)
    return record


def update_training_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    """Update a training job record by id.  Returns the updated record or None."""
    items = _read(_JOBS)
    rec = next((j for j in items if j.get("id") == job_id), None)
    if rec is None:
        return None
    # Always update timestamps for claim/finish transitions
    if fields.get("status") == "running" and "started_at" not in fields:
        fields["started_at"] = _now()
    if fields.get("status") in ("done", "failed", "cancelled") and "finished_at" not in fields:
        fields["finished_at"] = _now()
    rec.update(fields)
    _write(_JOBS, items)
    return rec


def claim_training_job(job_id: str, worker_id: str) -> dict[str, Any] | None:
    """Atomically mark a queued job as running and assign to *worker_id*."""
    items = _read(_JOBS)
    rec = next((j for j in items if j.get("id") == job_id), None)
    if rec is None:
        return None
    if rec.get("status") != "queued":
        return None
    rec["status"] = "running"
    rec["worker"] = worker_id
    rec["started_at"] = _now()
    _write(_JOBS, items)
    return rec


def delete_training_job(job_id: str) -> bool:
    items = _read(_JOBS)
    new = [i for i in items if i.get("id") != job_id]
    if len(new) == len(items):
        return False
    _write(_JOBS, new)
    return True


# ---------------------------------------------------------------------------
# Worker selection helpers
# ---------------------------------------------------------------------------


def get_online_nodes() -> list[dict[str, Any]]:
    """Return nodes that have sent a heartbeat within the last 60s."""
    try:
        from doof.compute.scheduler import is_stale
    except Exception:
        is_stale = None  # type: ignore
    now = time.time()
    nodes = _read(_NODES)
    online = []
    for n in nodes:
        fresh = False
        if is_stale is not None:
            fresh = n.get("is_local") or not is_stale(n)
        else:
            last_seen = n.get("last_seen")
            if isinstance(last_seen, (int, float)) and now - last_seen <= 60:
                fresh = True
            elif n.get("is_local"):
                fresh = True
        if fresh:
            n_copy = dict(n)
            n_copy["status"] = "online"
            online.append(n_copy)
    return online


def get_strongest_online_worker() -> dict[str, Any] | None:
    """Return the online node with the most VRAM, or None if none online."""
    online = get_online_nodes()
    if not online:
        return None
    return sorted(online, key=lambda n: n.get("vram_gb", 0), reverse=True)[0]


# ---------------------------------------------------------------------------
# COMPUTE JOBS (inference / embeddings — typed, never arbitrary code)
# ---------------------------------------------------------------------------

_COMPUTE = DATA / "compute_jobs.json"


def get_compute_jobs(
    *,
    status: str | None = None,
    worker_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    items = _read(_COMPUTE)
    if status:
        items = [j for j in items if j.get("status") == status]
    if worker_id:
        items = [
            j
            for j in items
            if j.get("worker_node") == worker_id or j.get("worker") == worker_id
        ]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def insert_compute_job(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_COMPUTE)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    record.setdefault("status", "queued")
    record.setdefault("priority", 5)
    record.setdefault("payload", {})
    record.setdefault("attempts", 0)
    items.append(record)
    _write(_COMPUTE, items)
    return record


def update_compute_job(job_id: str, **fields: Any) -> dict[str, Any] | None:
    items = _read(_COMPUTE)
    rec = next((j for j in items if j.get("id") == job_id), None)
    if rec is None:
        return None
    rec.update(fields)
    _write(_COMPUTE, items)
    return rec


def claim_compute_job(job_id: str, worker_id: str) -> dict[str, Any] | None:
    items = _read(_COMPUTE)
    rec = next((j for j in items if j.get("id") == job_id), None)
    if rec is None or rec.get("status") != "queued":
        return None
    rec["status"] = "running"
    rec["worker_node"] = worker_id
    rec["started_at"] = _now()
    rec["attempts"] = int(rec.get("attempts") or 0) + 1
    _write(_COMPUTE, items)
    return rec


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------
_REWARDS = DATA / "rewards.json"


def insert_reward(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_REWARDS)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", _now())
    record.setdefault("status", "pending")
    items.append(record)
    _write(_REWARDS, items)
    return record


def get_rewards(status: str | None = None, user_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    items = _read(_REWARDS)
    if status:
        items = [r for r in items if r.get("status") == status]
    if user_id:
        items = [r for r in items if r.get("user_id") == user_id]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def update_reward(reward_id: str, **fields: Any) -> dict[str, Any] | None:
    items = _read(_REWARDS)
    rec = next((r for r in items if r.get("id") == reward_id), None)
    if rec is None:
        return None
    rec.update(fields)
    _write(_REWARDS, items)
    return rec


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
_MODELS = DATA / "model_registry.json"


def list_models() -> list[dict[str, Any]]:
    return _read(_MODELS)


def insert_model(record: dict[str, Any]) -> dict[str, Any]:
    items = _read(_MODELS)
    existing = next(
        (i for i, m in enumerate(items)
         if m.get("model_id") == record.get("model_id")
         and m.get("version") == record.get("version")),
        None,
    )
    if existing is not None:
        items[existing].update(record)
    else:
        items.append(record)
    _write(_MODELS, items)
    return record


def update_model(model_id: str, version: str, **fields: Any) -> dict[str, Any] | None:
    items = _read(_MODELS)
    rec = next(
        (m for m in items if m.get("model_id") == model_id and m.get("version") == version),
        None,
    )
    if rec is None:
        return None
    rec.update(fields)
    _write(_MODELS, items)
    return rec


def delete_model(model_id: str, version: str) -> bool:
    items = _read(_MODELS)
    before = len(items)
    items = [
        m for m in items
        if not (m.get("model_id") == model_id and m.get("version") == version)
    ]
    if len(items) < before:
        _write(_MODELS, items)
        return True
    return False
