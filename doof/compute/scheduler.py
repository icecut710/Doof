"""Deterministic node selection. Never random. Never send work to a corpse."""
from __future__ import annotations

import time
from typing import Any

STALE_SECONDS = 60


def _as_epoch(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        # Heuristic: ms vs s vs already-epoch
        if value > 1e12:
            return value / 1000.0
        return float(value)
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return 0.0
        try:
            return float(txt)
        except ValueError:
            pass
        try:
            from datetime import datetime, timezone

            if txt.endswith("Z"):
                txt = txt[:-1] + "+00:00"
            dt = datetime.fromisoformat(txt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


def is_stale(node: dict[str, Any], *, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    last = _as_epoch(node.get("last_seen") or node.get("last_heartbeat"))
    if last <= 0:
        return node.get("status") != "online"
    return (now - last) > STALE_SECONDS


def node_state(node: dict[str, Any], *, now: float | None = None) -> str:
    """visible | registered | reachable | connected | available_for_work

    These are not the same thing. The UI must not collapse them.
    """
    if is_stale(node, now=now) or node.get("status") == "offline":
        return "registered" if node.get("id") else "visible"
    if node.get("reachable") or node.get("is_local"):
        if node.get("accepting_jobs") and int(node.get("job_count") or 0) < int(
            node.get("max_jobs") or 1
        ):
            return "available_for_work"
        return "connected"
    if node.get("status") == "online":
        return "connected"
    return "visible"


def score_node(node: dict[str, Any], job_type: str, *, now: float | None = None) -> float:
    if is_stale(node, now=now):
        return -1.0
    if node.get("status") != "online":
        return -1.0
    if not node.get("accepting_jobs") and not node.get("is_local"):
        return -1.0
    jobs = int(node.get("job_count") or 0)
    max_jobs = max(1, int(node.get("max_jobs") or 1))
    if jobs >= max_jobs:
        return -1.0

    caps = node.get("capabilities") or {}
    gpu = bool(node.get("cuda_available") or (node.get("gpu") not in (None, "", "CPU")))
    vram = float(node.get("vram_gb") or 0)
    ram = float(node.get("ram_gb") or 0)
    cpu_n = float(node.get("cpu_count") or 2)
    load = float(node.get("cpu_load") or 0)
    accept_gpu = node.get("accept_gpu", True)
    accept_cpu = node.get("accept_cpu", True)

    if job_type in ("inference", "embedding", "train", "evaluate"):
        if gpu and not accept_gpu and not accept_cpu:
            return -1.0
        if not gpu and not accept_cpu:
            return -1.0
        if job_type == "train" and not gpu and ram < 8:
            # Weak CPU boxes should not eat a training job if anyone else exists.
            pass

    score = 1.0
    if job_type in ("inference", "train", "evaluate"):
        if gpu and accept_gpu:
            score += 100.0 + vram * 4.0
        elif accept_cpu:
            score += 10.0 + cpu_n
        if caps.get("large_model_inference"):
            score += 20.0
        if caps.get("small_model_inference") or caps.get("cpu_inference"):
            score += 5.0
    score += ram * 0.5
    score -= load * 30.0
    score -= jobs * 15.0
    if node.get("low_end") or (caps.get("low_end")):
        score -= 25.0
    if node.get("is_local"):
        # Prefer a stronger remote node when one exists; local is the fallback.
        score -= 8.0
    return score


def select_node(
    nodes: list[dict[str, Any]],
    job_type: str,
    *,
    prefer_remote: bool = True,
    local_id: str | None = None,
) -> dict[str, Any] | None:
    now = time.time()
    ranked: list[tuple[float, dict[str, Any]]] = []
    for n in nodes:
        s = score_node(n, job_type, now=now)
        if s < 0:
            continue
        ranked.append((s, n))
    if not ranked:
        # Local fallback even if not accepting remote jobs.
        if local_id:
            for n in nodes:
                if str(n.get("id")) == str(local_id) and not is_stale(n, now=now):
                    return n
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    best = ranked[0][1]
    if not prefer_remote and local_id:
        for s, n in ranked:
            if str(n.get("id")) == str(local_id):
                return n
    return best
