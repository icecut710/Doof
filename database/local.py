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


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

_NODES = DATA / "nodes.json"


def get_nodes() -> list[dict[str, Any]]:
    return _read(_NODES)


def upsert_node(node: dict[str, Any]) -> dict[str, Any]:
    nodes = _read(_NODES)
    existing = next((n for n in nodes if n.get("id") == node.get("id")), None)
    if existing:
        existing.update(node)
    else:
        node.setdefault("id", str(uuid.uuid4()))
        nodes.append(node)
    _write(_NODES, nodes)
    return node


def delete_node(node_id: str) -> bool:
    nodes = _read(_NODES)
    new = [n for n in nodes if n.get("id") != node_id]
    if len(new) == len(nodes):
        return False
    _write(_NODES, new)
    return True


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
