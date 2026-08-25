"""Compute pool: dispatch, LAN execute, Supabase job queue, local fallback.

Supabase is the control plane (presence, job state). Payloads are small JSON
(prompt/result text) — never model tensors.

NAT: nodes poll outbound for assigned jobs. Same-LAN peers may also be hit
directly at ``lan_url`` when reachable.
LAN is an optimization, NOT a requirement.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from doof.compute.jobs import JobRejected, validate_payload
from doof.compute.scheduler import select_node
from doof.errors import public_error
from doof.personality import pick
from doof.runtime import import_torch, torch_error

_worker_started = False
_worker_lock = threading.Lock()
_local_jobs = 0
_jobs_lock = threading.Lock()


def _db():
    from database import get_db

    return get_db()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _settings() -> dict[str, Any]:
    defaults = {
        "accepting_jobs": False,
        "accept_cpu": True,
        "accept_gpu": True,
        "max_jobs": 1,
        "max_cpu_pct": 80,
        "max_gpu_pct": 90,
        "max_vram_gb": None,
        "pause_on_battery": True,
        "pause_when_gaming": True,
        "idle_only": False,
        "only_while_open": True,
        "allow_train": False,
        "allow_inference": True,
        "allow_embedding": True,
    }
    try:
        from doof.paths import user_data_dir

        path = user_data_dir() / "compute_settings.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            defaults.update({k: data[k] for k in defaults if k in data})
    except Exception:
        pass
    return defaults


def save_settings(update: dict[str, Any]) -> dict[str, Any]:
    cur = _settings()
    for k in list(cur):
        if k in update:
            cur[k] = update[k]
    try:
        from doof.paths import user_data_dir

        path = user_data_dir() / "compute_settings.json"
        path.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    except Exception:
        pass
    return cur


def execute_local(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = _settings()
    if job_type == "train" and not settings.get("allow_train", False):
        raise JobRejected("training contribution is disabled on this node")
    if job_type == "inference" and not settings.get("allow_inference", True):
        raise JobRejected("inference contribution is disabled on this node")
    if job_type == "embedding" and not settings.get("allow_embedding", True):
        raise JobRejected("embedding contribution is disabled on this node")

    data = validate_payload(job_type, payload)
    if job_type == "inference":
        return _local_inference(data)
    if job_type == "embedding":
        return {"ok": True, "provider": "hash", "vector": _hash_embed(data["text"])}
    if job_type == "build_dataset":
        from doof.intelligence.dataset import build_dataset

        return {"ok": True, "result": build_dataset()}
    if job_type == "evaluate":
        from doof.intelligence.evaluate import evaluate_checkpoint

        name = str(data.get("checkpoint_name") or "doof_v01.pt")
        return {"ok": True, "result": evaluate_checkpoint(name)}
    if job_type == "train":
        raise JobRejected("train jobs must go through /api/training/start")
    raise JobRejected(job_type)


def _hash_embed(text: str) -> list[float]:
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in digest[:32]]


def _local_inference(data: dict[str, Any]) -> dict[str, Any]:
    """Actual AI path: memory is context, model is the brain."""
    from doof.brain import build_prompt, lightweight_answer, postprocess_model_text

    prompt = data["prompt"]
    memories: list[dict[str, Any]] = []
    try:
        from doof.intelligence.rag import retrieve_memories

        memories = retrieve_memories(prompt, top_k=5)
        try:
            from doof.intelligence.store import get_store

            store = get_store()
            for mem in memories:
                store.increment_usage(mem["id"])
        except Exception:
            pass
    except Exception:
        memories = []

    augmented = build_prompt(prompt, memories)
    torch = import_torch()
    torch_fail: BaseException | None = None

    if torch is not None:
        try:
            from doof.api import get_inf

            inf = get_inf()
            text = inf.generate(
                augmented,
                max_new_tokens=data["max_new_tokens"],
                temperature=data["temperature"],
                top_k=data["top_k"],
            )
            if text.startswith(augmented):
                text = text[len(augmented) :].lstrip()
            text = postprocess_model_text(text, prompt, memories)
            return {
                "ok": True,
                "text": text,
                "provider": "local_model",
                "device": getattr(inf, "device_label", None) or str(getattr(inf, "device", "")),
                "memories_used": memories,
            }
        except Exception as e:
            torch_fail = e

    cloud = _cloud_inference(prompt, memories)
    if cloud is not None:
        cloud["memories_used"] = memories
        if torch_fail:
            cloud["fallback_of"] = str(torch_fail)
        return cloud

    label, detail = pick("ai_fallback")
    return {
        "ok": True,
        "text": lightweight_answer(prompt, memories),
        "provider": "lightweight",
        "memories_used": memories,
        "notice": {"title": label, "detail": detail},
        "fallback_of": str(torch_fail or torch_error() or "model unavailable"),
    }


def _cloud_inference(prompt: str, memories: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Project-owned DOOF hosted brain only — never third-party providers."""
    try:
        from doof.compute.cloud_inference import hosted_or_none
        return hosted_or_none(prompt, memories)
    except Exception:
        return None


def _lan_execute(url: str, job_type: str, payload: dict[str, Any], token: str | None) -> dict[str, Any] | None:
    body = json.dumps({"type": job_type, "payload": payload}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url.rstrip("/") + "/api/compute/execute", data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
        if data.get("ok") and data.get("text"):
            return data
    except (URLError, TimeoutError, OSError, ValueError):
        return None
    return None


def dispatch_inference(
    prompt: str,
    *,
    temperature: float = 0.7,
    max_new_tokens: int = 80,
    top_k: int = 50,
    nodes: list[dict[str, Any]] | None = None,
    local_id: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    try:
        from doof.admin import pool_paused

        if pool_paused():
            nodes = [n for n in (nodes or []) if n.get("is_local")]
    except Exception:
        pass

    payload = validate_payload(
        "inference",
        {
            "prompt": prompt,
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "top_k": top_k,
        },
    )
    nodes = nodes or []
    target = select_node(nodes, "inference", prefer_remote=True, local_id=local_id)
    used_remote = False
    if (
        target
        and local_id
        and str(target.get("id")) != str(local_id)
        and target.get("accepting_jobs")
    ):
        lan = target.get("lan_url")
        if lan:
            remote = _lan_execute(str(lan), "inference", payload, token)
            if remote:
                remote["routed_to"] = target.get("name")
                remote["provider"] = remote.get("provider") or "remote"
                used_remote = True
                return remote
        queued = _enqueue("inference", payload, worker=str(target.get("id")), requester=local_id)
        if queued:
            result = _wait_job(queued.get("id"), timeout=40)
            if result and result.get("status") == "done" and result.get("result"):
                out = dict(result["result"])
                out["routed_to"] = target.get("name")
                out["provider"] = out.get("provider") or "remote"
                used_remote = True
                return out

    local = execute_local("inference", payload)
    if not used_remote:
        label, detail = pick("job_local")
        local.setdefault("notice", {"title": label, "detail": detail})
        if not nodes or not any(
            n.get("accepting_jobs") and str(n.get("id")) != str(local_id) for n in nodes
        ):
            empty_l, empty_d = pick("network_empty")
            local.setdefault("pool", {"title": empty_l, "detail": empty_d})
    return local


def _enqueue(job_type: str, payload: dict[str, Any], *, worker: str | None, requester: str | None) -> dict[str, Any] | None:
    record = {
        "id": str(uuid.uuid4()),
        "type": job_type,
        "status": "queued",
        "priority": 3 if job_type == "inference" else 5,
        "payload": payload,
        "worker_node": worker,
        "requester_node": requester,
        "created_by": requester or "local",
        "created_at": _now(),
        "attempts": 0,
        "max_attempts": 3,
    }
    try:
        db = _db()
        if hasattr(db, "insert_compute_job"):
            return db.insert_compute_job(record)
        if hasattr(db, "insert_training_job"):
            record2 = dict(record)
            record2["worker"] = worker
            return db.insert_training_job(record2)
    except Exception:
        return None
    return None


def _wait_job(job_id: str | None, timeout: float) -> dict[str, Any] | None:
    if not job_id:
        return None
    deadline = time.time() + timeout
    db = _db()
    while time.time() < deadline:
        try:
            jobs = []
            if hasattr(db, "get_compute_jobs"):
                jobs = db.get_compute_jobs(limit=50)
            elif hasattr(db, "get_training_jobs"):
                jobs = db.get_training_jobs(limit=50)
            hit = next((j for j in jobs if str(j.get("id")) == str(job_id)), None)
            if hit and hit.get("status") in ("done", "failed", "cancelled"):
                return hit
        except Exception:
            return None
        time.sleep(0.4)
    return None


def start_worker_loop(local_id_fn, execute_fn=None) -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    def loop() -> None:
        while True:
            try:
                _poll_once(local_id_fn, execute_fn or execute_local)
            except Exception:
                pass
            time.sleep(2.5)

    threading.Thread(target=loop, daemon=True, name="doof-compute-worker").start()


def _poll_once(local_id_fn, execute_fn) -> None:
    try:
        from doof.admin import pool_paused

        if pool_paused():
            return
    except Exception:
        pass
    settings = _settings()
    if not settings.get("accepting_jobs"):
        return
    try:
        local_id = local_id_fn()
    except Exception:
        return
    if not local_id:
        return
    db = _db()
    jobs: list[dict[str, Any]] = []
    try:
        if hasattr(db, "get_compute_jobs"):
            jobs = db.get_compute_jobs(status="queued", limit=10)
        elif hasattr(db, "get_training_jobs"):
            jobs = [
                j
                for j in db.get_training_jobs(status="queued", limit=10)
                if j.get("type") in ("inference", "embedding")
            ]
    except Exception:
        return
    mine = [
        j
        for j in jobs
        if str(j.get("worker_node") or j.get("worker") or "") == str(local_id)
        or not (j.get("worker_node") or j.get("worker"))
    ]
    if not mine:
        return
    job = mine[0]
    jtype = job.get("type") or "inference"
    if jtype == "train" and not settings.get("allow_train"):
        return
    if jtype == "inference" and not settings.get("allow_inference", True):
        return
    if jtype == "embedding" and not settings.get("allow_embedding", True):
        return
    jid = job.get("id")
    claimed = None
    try:
        if hasattr(db, "claim_compute_job"):
            claimed = db.claim_compute_job(jid, local_id)
        elif hasattr(db, "claim_training_job"):
            claimed = db.claim_training_job(jid, local_id)
    except Exception:
        claimed = None
    if not claimed:
        return
    global _local_jobs
    with _jobs_lock:
        if _local_jobs >= int(settings.get("max_jobs") or 1):
            return
        _local_jobs += 1
    try:
        result = execute_fn(claimed.get("type") or "inference", claimed.get("payload") or {})
        if hasattr(db, "update_compute_job"):
            db.update_compute_job(jid, status="done", result=result, finished_at=_now())
            try:
                from doof.rewards import record_job_reward
                record_job_reward(
                    user_id=str(claimed.get("created_by") or claimed.get("requester_node") or "local"),
                    node_id=str(claimed.get("worker_node") or "local"),
                    job_id=str(jid),
                    job_type=str(claimed.get("type") or "inference"),
                    device=str((result or {}).get("device") or "cpu"),
                    duration_s=0.0,
                    verified=True,
                )
            except Exception:
                pass
        elif hasattr(db, "update_training_job"):
            db.update_training_job(jid, status="done", result=result, finished_at=_now())
    except Exception as e:
        err = public_error(e)
        try:
            if hasattr(db, "update_compute_job"):
                db.update_compute_job(jid, status="failed", error=err["title"], finished_at=_now())
            elif hasattr(db, "update_training_job"):
                db.update_training_job(jid, status="failed", error=err["title"], finished_at=_now())
        except Exception:
            pass
    finally:
        with _jobs_lock:
            _local_jobs = max(0, _local_jobs - 1)


def current_job_count() -> int:
    with _jobs_lock:
        return _local_jobs
