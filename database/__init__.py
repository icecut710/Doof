"""DOOF Database — Adapter selector.

Usage::

    from database import get_db
    db = get_db()
    memories = db.get_memories()

If SUPABASE_URL and a key are set in the environment, the Supabase adapter
is used automatically.  Otherwise falls back to local JSON files.
"""
from __future__ import annotations

import os
from types import ModuleType


def get_db() -> ModuleType:
    """Return the active database adapter module."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    if url and key:
        from database import supabase as _db  # type: ignore
    else:
        from database import local as _db  # type: ignore
    return _db


__all__ = ["get_db"]
