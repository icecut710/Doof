"""DOOF Intelligence — Memory Store.

Backed by data/memories.json.  Every item in the store is a structured
memory card that can be retrieved, searched, approved, and promoted into
training data.  Thread-safe via a per-store lock.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from doof.paths import user_data_dir
    DEFAULT_PATH = user_data_dir() / "memories.json"
except Exception:
    DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "memories.json"

IMPORTANCE_LEVELS = {"low", "medium", "high"}


class Store:
    """Persistent memory store for DOOF.

    Parameters
    ----------
    path:
        Absolute path to the backing JSON file.  Created on first write if
        it does not exist.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_PATH
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    self._items = {item["id"]: item for item in raw if "id" in item}
                elif isinstance(raw, dict):
                    self._items = raw
            except Exception:
                self._items = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(list(self._items.values()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def add(
        self,
        content: str,
        *,
        created_by: str = "system",
        importance: str = "medium",
        category: str = "general",
        tags: list[str] | None = None,
        approved: bool = True,
        training_status: str = "none",
    ) -> dict[str, Any]:
        """Add a new memory item.  Returns the created item."""
        importance = importance if importance in IMPORTANCE_LEVELS else "medium"
        item: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "content": content.strip(),
            "created_at": self._now(),
            "created_by": created_by,
            "importance": importance,
            "category": category,
            "tags": tags or [],
            "usage_count": 0,
            "approved": approved,
            "training_status": training_status,
        }
        with self._lock:
            self._items[item["id"]] = item
            self._save()
        return item

    def get(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._items[item_id]) if item_id in self._items else None

    def delete(self, item_id: str) -> bool:
        with self._lock:
            if item_id not in self._items:
                return False
            del self._items[item_id]
            self._save()
            return True

    def update(self, item_id: str, **fields: Any) -> dict[str, Any] | None:
        """Update allowed fields on an existing memory item."""
        allowed = {"content", "importance", "category", "tags", "approved", "training_status", "training_example_id"}
        with self._lock:
            if item_id not in self._items:
                return None
            item = self._items[item_id]
            for k, v in fields.items():
                if k in allowed:
                    item[k] = v
            self._save()
            return dict(item)

    def increment_usage(self, item_id: str) -> None:
        with self._lock:
            if item_id in self._items:
                self._items[item_id]["usage_count"] = (
                    self._items[item_id].get("usage_count", 0) + 1
                )
                self._save()

    def list_all(self, *, approved_only: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._items.values())
        if approved_only:
            items = [i for i in items if i.get("approved")]
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Simple case-insensitive substring search across content and tags."""
        q = query.lower().strip()
        if not q:
            return self.list_all()
        results: list[dict[str, Any]] = []
        with self._lock:
            for item in self._items.values():
                content_match = q in item.get("content", "").lower()
                tag_match = any(q in t.lower() for t in item.get("tags", []))
                category_match = q in item.get("category", "").lower()
                if content_match or tag_match or category_match:
                    results.append(dict(item))
        return sorted(results, key=lambda x: x.get("importance", "medium") == "high", reverse=True)[
            :limit
        ]

    def stats(self) -> dict[str, int]:
        with self._lock:
            all_items = list(self._items.values())
        return {
            "total": len(all_items),
            "approved": sum(1 for i in all_items if i.get("approved")),
            "pending": sum(1 for i in all_items if not i.get("approved")),
            "high_importance": sum(1 for i in all_items if i.get("importance") == "high"),
        }

    def clear(self) -> None:
        with self._lock:
            self._items = {}
            self._save()

    def export_training_lines(self) -> list[str]:
        """Return approved memory content as training corpus lines."""
        with self._lock:
            return [
                i["content"]
                for i in self._items.values()
                if i.get("approved") and i.get("content")
            ]


_store: Store | None = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store()
    return _store
