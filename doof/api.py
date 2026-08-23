"""DOOF local HTTP API — v0.2 Alpha.

Endpoints
---------
GET  /api/health
GET  /api/hardware
GET  /api/model
GET  /api/checkpoints
GET  /api/models/versions
GET  /api/training
GET  /api/settings
GET  /api/cloud
GET  /api/memory
GET  /api/feedback
GET  /api/nodes
GET  /api/scheduler

POST /api/generate
POST /api/training/start
POST /api/training/stop
POST /api/training/build_dataset
POST /api/model/load
POST /api/reload
POST /api/settings
POST /api/knowledge          (legacy compat)
POST /api/memory
POST /api/memory/{id}/approve
POST /api/feedback
POST /api/nodes/register
POST /api/nodes/heartbeat
POST /api/models/promote

DELETE /api/memory/{id}
DELETE /api/nodes/{id}
"""
from __future__ import annotations

import json
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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
CKPT_DIR = ROOT / "checkpoints"
DATA_DIR = ROOT / "data"
TRAIN = DATA_DIR / "train.txt"
KNOW = DATA_DIR / "knowledge.json"
SETT = DATA_DIR / "settings.json"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
NODES_PATH = DATA_DIR / "nodes.json"
VERSIONS_PATH = DATA_DIR / "brain_versions.json"

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
    versions = _load_versions()
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
        # Version metadata
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
    if VERSIONS_PATH.exists():
        try:
            return json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_versions(versions: list[dict[str, Any]]) -> None:
    VERSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_PATH.write_text(
        json.dumps(versions, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def promote_checkpoint(
    checkpoint_name: str,
    label: str,
    promoted_by: str = "system",
) -> dict[str, Any]:
    """Mark a checkpoint as production, demoting any current production."""
    versions = _load_versions()
    # Demote current production
    for v in versions:
        if v.get("status") == "production":
            v["status"] = "archived"
    # Find or create entry
    for v in versions:
        if v.get("checkpoint_name") == checkpoint_name:
            v.update(
                {
                    "label": label,
                    "status": "production",
                    "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "promoted_by": promoted_by,
                }
            )
            break
    else:
        versions.append(
            {
                "id": str(uuid.uuid4()),
                "checkpoint_name": checkpoint_name,
                "label": label,
                "status": "production",
                "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "promoted_by": promoted_by,
            }
        )
    _save_versions(versions)
    return {"ok": True, "checkpoint": checkpoint_name, "label": label}


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
    if FEEDBACK_PATH.exists():
        try:
            data = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _save_feedback(items: list[dict[str, Any]]) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_PATH.write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add_feedback(
    prompt: str,
    response: str,
    rating: str,
    correction: str = "",
    created_by: str = "local",
    memories_used: list | None = None,
) -> dict[str, Any]:
    from doof.intelligence.quality import score_response
    items = _load_feedback()
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
    items.append(item)
    _save_feedback(items)
    return item


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _load_nodes() -> list[dict[str, Any]]:
    if NODES_PATH.exists():
        try:
            data = json.loads(NODES_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _save_nodes(nodes: list[dict[str, Any]]) -> None:
    NODES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NODES_PATH.write_text(
        json.dumps(nodes, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_nodes_with_local() -> list[dict[str, Any]]:
    """Return all nodes, auto-updating the local node entry from hardware()."""
    hw = hardware()
    nodes = _load_nodes()

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
        local_node.update(local_data)
    else:
        nodes.insert(0, local_data)

    _save_nodes(nodes)

    # Mark stale nodes as offline (no heartbeat for 60s)
    for node in nodes:
        if node.get("id") == local_id:
            continue
        last = node.get("last_seen", 0)
        if isinstance(last, (int, float)) and (now_ts - last) > 60:
            node["status"] = "offline"

    return nodes


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
        import torch
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
    except Exception as e:
        with _lock:
            _train.update(
                {
                    "running": False,
                    "message": f"error: {e}",
                    "error": traceback.format_exc(),
                }
            )


# ---------------------------------------------------------------------------
# Training stats helper
# ---------------------------------------------------------------------------


def training_stats() -> dict[str, Any]:
    """Return enriched training status."""
    feedback = _load_feedback()
    approved = [f for f in feedback if f.get("approved")]
    training_ready = [f for f in feedback if f.get("training_ready")]

    store = _get_store()
    mem_stats = store.stats()

    versions = _load_versions()
    production = next(
        (v for v in reversed(versions) if v.get("status") == "production"), None
    )

    with _lock:
        state = dict(_train)

    state["approved_examples"] = len(approved)
    state["training_ready_examples"] = len(training_ready)
    state["total_feedback"] = len(feedback)
    state["memory_count"] = mem_stats["approved"]
    state["brain_version"] = production.get("label") if production else "1.0.0"
    state["production_checkpoint"] = production.get("checkpoint_name") if production else None
    return state


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
                total_vram = sum(n.get("vram_gb", 0) for n in nodes if n.get("status") == "online")
                online = [n for n in nodes if n.get("status") == "online"]
                _json(
                    self,
                    200,
                    {
                        "nodes": nodes,
                        "nodes_online": len(online),
                        "total_vram_gb": round(total_vram, 1),
                        "training_active": any(n.get("training_active") for n in online),
                    },
                )

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

            # Node register
            elif path == "/api/nodes/register":
                name = (body.get("name") or platform.node() or "Unknown").strip()
                nodes = _load_nodes()
                # Check if already registered by name
                existing = next((n for n in nodes if n.get("name") == name), None)
                now = time.time()
                if existing:
                    existing.update({
                        "gpu": body.get("gpu", existing.get("gpu")),
                        "vram_gb": body.get("vram_gb", existing.get("vram_gb")),
                        "status": "online",
                        "last_seen": now,
                    })
                else:
                    node: dict[str, Any] = {
                        "id": str(uuid.uuid4()),
                        "name": name,
                        "gpu": body.get("gpu", "Unknown GPU"),
                        "vram_gb": float(body.get("vram_gb", 0)),
                        "device": body.get("device", "cpu"),
                        "status": "online",
                        "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "last_seen": now,
                        "is_local": False,
                        "training_active": False,
                    }
                    nodes.append(node)
                    existing = node
                _save_nodes(nodes)
                _json(self, 201, {"ok": True, "node": existing})

            # Node heartbeat
            elif path == "/api/nodes/heartbeat":
                node_id = body.get("id")
                nodes = _load_nodes()
                node = next((n for n in nodes if n.get("id") == node_id), None)
                if node:
                    node["last_seen"] = time.time()
                    node["status"] = "online"
                    node["training_active"] = body.get("training_active", False)
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
                # Reload inference with promoted checkpoint
                with _lock:
                    _inf = None
                    _loaded = None
                _json(self, 200, result)

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
                nodes = _load_nodes()
                original_len = len(nodes)
                nodes = [n for n in nodes if n.get("id") != node_id]
                if len(nodes) < original_len:
                    _save_nodes(nodes)
                    _json(self, 200, {"ok": True, "deleted": node_id})
                else:
                    _json(self, 404, {"error": "node not found"})
                return

            _json(self, 404, {"error": "not found"})

        except Exception as e:
            _json(self, 500, {"error": str(e)})


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

    s = ThreadingHTTPServer((host, port), Handler)
    print(f"DOOF API v0.2 listening on http://{host}:{port}")
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        s.shutdown()


if __name__ == "__main__":
    run_server()
