"""DOOF Database Abstraction — Supabase adapter.

Mirrors the exact interface of local.py but routes all reads/writes
through the Supabase REST API.  Requires environment variables:

    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (for server-side writes)
    SUPABASE_ANON_KEY      (for client reads)

Tables required in Supabase (see supabase/schema.sql):
    memories, feedback, nodes, brain_versions

This module is intentionally NOT imported unless Supabase is configured.
The API layer always uses get_db() from __init__.py which selects the
correct backend automatically.
"""
from __future__ import annotations

import json
import os
from dotenv import load_dotenv

load_dotenv()
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


# ---------------------------------------------------------------------------
# Brain versions
# ---------------------------------------------------------------------------

def get_versions() -> list[dict[str, Any]]:
    return _get("brain_versions", "order=created_at.desc")


def insert_version(record: dict[str, Any]) -> dict[str, Any]:
    return _post("brain_versions", record)
