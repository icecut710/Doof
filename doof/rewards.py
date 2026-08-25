"""Naddaf compute rewards — internal off-chain ledger only.

On-chain token transfers are intentionally NOT implemented in the desktop client.
Treasury keys must never live in the EXE. When payouts are enabled later, a
server-side process marks ledger rows paid after a real transaction.

States: pending → approved → paid | reversed
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from doof.paths import user_data_dir


def _ledger_path() -> Path:
    d = user_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "reward_ledger.json"


def _load() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except Exception:
        return []


def _save(rows: list[dict[str, Any]]) -> None:
    path = _ledger_path()
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


_RATES = {
    "inference": 1.0,
    "embedding": 0.5,
    "train": 5.0,
}


def estimate_reward(job_type: str, *, device: str = "cpu", duration_s: float = 0.0) -> float:
    base = _RATES.get(job_type, 0.5)
    device_mult = 1.5 if str(device).lower() in ("cuda", "gpu") else 1.0
    time_mult = 1.0 + min(max(duration_s, 0.0) / 60.0, 10.0) * 0.1
    return round(base * device_mult * time_mult, 4)


def record_job_reward(
    *,
    user_id: str,
    node_id: str,
    job_id: str,
    job_type: str,
    device: str = "cpu",
    duration_s: float = 0.0,
    verified: bool = True,
) -> dict[str, Any] | None:
    """Server-side only. Reject unverified / duplicate jobs."""
    if not verified:
        return None
    if not user_id or not job_id:
        return None
    rows = _load()
    if any(r.get("job_id") == job_id and r.get("status") != "reversed" for r in rows):
        return None
    amount = estimate_reward(job_type, device=device, duration_s=duration_s)
    if amount <= 0:
        return None
    entry = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "node_id": node_id,
        "job_id": job_id,
        "job_type": job_type,
        "device": device,
        "duration_s": round(duration_s, 3),
        "amount": amount,
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "approved_at": None,
        "paid_at": None,
        "tx_signature": None,
        "note": "Internal Naddaf credit — not an on-chain transfer",
    }
    rows.append(entry)
    _save(rows)
    try:
        from database import get_db
        db = get_db()
        if hasattr(db, "insert_reward"):
            db.insert_reward(entry)
    except Exception:
        pass
    return entry


def approve_reward(reward_id: str, *, actor: str) -> bool:
    rows = _load()
    for r in rows:
        if r.get("id") == reward_id and r.get("status") == "pending":
            r["status"] = "approved"
            r["approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            r["approved_by"] = actor
            _save(rows)
            return True
    return False


def reverse_reward(reward_id: str, *, reason: str = "") -> bool:
    rows = _load()
    for r in rows:
        if r.get("id") == reward_id and r.get("status") in ("pending", "approved"):
            r["status"] = "reversed"
            r["note"] = (r.get("note") or "") + f" | reversed: {reason}"
            _save(rows)
            return True
    return False


def balances(user_id: str) -> dict[str, Any]:
    rows = [r for r in _load() if r.get("user_id") == user_id]
    def sum_status(st: str) -> float:
        return round(sum(float(r.get("amount") or 0) for r in rows if r.get("status") == st), 4)
    return {
        "user_id": user_id,
        "pending": sum_status("pending"),
        "approved": sum_status("approved"),
        "paid": sum_status("paid"),
        "reversed": sum_status("reversed"),
        "on_chain_payouts_enabled": False,
        "disclaimer": (
            "Balances are internal verified contribution credits. "
            "On-chain Naddaf token payouts are not enabled in this client."
        ),
        "history": sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)[:50],
    }


def payouts_status() -> dict[str, Any]:
    return {
        "enabled": False,
        "label": "On-chain payouts are not enabled yet",
        "detail": (
            "Your verified contribution rewards are tracked in the internal ledger. "
            "Treasury keys never ship with the desktop client."
        ),
    }
