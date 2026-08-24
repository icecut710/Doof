"""DOOF Training Worker — distributed training node.

A worker registers itself with the compute pool, sends periodic heartbeats,
claims training jobs assigned by the scheduler, pulls the approved-examples
dataset from Supabase (or local fallback), runs the PyTorch trainer, and
uploads the resulting checkpoint + brain version back to the database.

Usage::

    from doof.training.worker import TrainingWorker
    worker = TrainingWorker(node_name="my-gpu-box")
    worker.run()          # blocks, polling for jobs

Or via CLI::

    python -m doof.train          # built-in 'train' command runs the worker
    python scripts/worker.py       # standalone script
"""
from __future__ import annotations

import json
import os
import platform
import signal
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from doof import __version__

try:
    from doof.paths import bundle_root, user_data_dir
    ROOT = bundle_root()
    DATA_DIR = user_data_dir()
except Exception:
    ROOT = Path(__file__).resolve().parents[2]
    DATA_DIR = ROOT / "data"
CKPT_DIR = ROOT / "checkpoints"


def _hardware_summary() -> dict[str, Any]:
    """Gather GPU/VRAM/device metadata the same way api.py does."""
    hw: dict[str, Any] = {
        "platform": platform.system(),
        "python": platform.python_version(),
        "device": "cpu",
        "cuda_available": False,
        "cuda_device_count": 0,
        "cuda_version": None,
        "mps_available": False,
        "gpu": "CPU",
        "vram_gb": 0.0,
        "cpu_count": os.cpu_count(),
        "torch_version": None,
    }
    try:
        import torch
        hw["torch_version"] = torch.__version__
        if torch.cuda.is_available():
            hw["cuda_available"] = True
            hw["device"] = "cuda"
            hw["cuda_device_count"] = torch.cuda.device_count()
            hw["cuda_version"] = getattr(torch.version, "cuda", None)
            props = torch.cuda.get_device_properties(0)
            hw["gpu"] = props.name
            hw["vram_gb"] = round(props.total_memory / (1024 ** 3), 2)
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            hw["mps_available"] = True
            hw["device"] = "mps"
            hw["gpu"] = "Apple MPS"
    except Exception as e:
        hw["error"] = str(e)
    return hw


class TrainingWorker:
    """A self-contained training worker that integrates with the DOOF
    scheduler / job queue.

    Parameters
    ----------
    node_name:
        Human-readable name for this worker (defaults to hostname).
    api_base:
        Base URL of the DOOF API server.  When set, heartbeats are sent via
        HTTP.  When *None*, the worker uses the database adapter directly.
    """

    HEARTBEAT_INTERVAL = 30  # seconds
    POLL_INTERVAL = 10       # seconds between job polls
    STALE_THRESHOLD = 60     # seconds before a node is considered offline

    def __init__(
        self,
        node_name: str | None = None,
        api_base: str | None = None,
    ):
        from database import get_db

        self.db = get_db()
        self.api_base = api_base
        self.node_name = node_name or platform.node() or "unknown-worker"
        self.hw = _hardware_summary()
        self.node_id: str | None = None
        self._stop_event = threading.Event()
        self._current_job: str | None = None

    # ------------------------------------------------------------------
    # Node registration & heartbeat
    # ------------------------------------------------------------------

    def register(self) -> dict[str, Any]:
        """Register this worker as a compute node."""
        node_data: dict[str, Any] = {
            "name": self.node_name,
            "gpu": self.hw.get("gpu", "CPU"),
            "vram_gb": self.hw.get("vram_gb", 0.0),
            "device": self.hw.get("device", "cpu"),
            "cuda_available": self.hw.get("cuda_available", False),
            "platform": self.hw.get("platform", ""),
            "torch_version": self.hw.get("torch_version"),
            "status": "online",
            "last_seen": time.time(),
            "is_local": self.api_base is None,
            "training_active": False,
            "current_checkpoint": None,
            "brain_version": None,
        }

        # Check if a node with this name already exists
        for n in self.db.get_nodes():
            if n.get("name") == self.node_name:
                node_data["id"] = n["id"]
                break

        node_data = self.db.upsert_node(node_data)
        self.node_id = node_data["id"]
        self.node_name = node_data.get("name", self.node_name)
        return node_data

    def send_heartbeat(self, *, training_active: bool = False) -> None:
        """Update the node's last_seen timestamp and status."""
        if not self.node_id:
            self.register()
        self.db.update_node(self.node_id, last_seen=time.time(),
                            status="online", training_active=training_active)

    # ------------------------------------------------------------------
    # Job claiming & execution
    # ------------------------------------------------------------------

    def _poll_jobs(self) -> list[dict[str, Any]]:
        """Return jobs assigned to this worker that are queued or running."""
        if not self.node_id:
            return []
        jobs = self.db.get_training_jobs()
        return [
            j for j in jobs
            if j.get("worker") == self.node_id
            and j.get("status") in ("queued", "running")
        ]

    def _pull_dataset(self, dataset_version: str | None = None) -> str:
        """Pull approved examples from the DB and write a local train.txt.

        **Never** trains on raw conversations — only ``approved`` and
        ``training_ready`` examples from the ``approved_examples`` table.
        """
        examples = self.db.get_approved_examples(
            approved_only=True,
            training_ready_only=True,
            limit=5000,
        )

        if not examples:
            # Fall back to the existing train.txt so the worker can still
            # boot in a fresh local installation.
            fallback = DATA_DIR / "train.txt"
            if fallback.exists():
                return str(fallback)
            raise RuntimeError(
                "No approved examples found in the database and no local "
                "train.txt fallback exists. Cannot build dataset."
            )

        # Write a versioned train.txt so the existing DOOFTrainer can consume it
        ds_version = dataset_version or time.strftime("v%Y%m%d_%H%M%S")
        out_path = DATA_DIR / f"train_{ds_version}.txt"
        lines: list[str] = []
        for ex in examples:
            response = (ex.get("response") or "").strip()
            if response:
                lines.append(response)
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(out_path)

    def _run_training(self, job: dict[str, Any]) -> dict[str, Any]:
        """Execute a training job: build dataset, train, save checkpoint."""
        from doof.training import DOOFTrainer, TrainingConfig

        payload = job.get("payload") or {}
        epochs = int(payload.get("epochs", 3))
        seq_len = int(payload.get("seq_len", 64))
        batch_size = int(payload.get("batch_size", 8))
        lr = float(payload.get("learning_rate", 3e-4))
        dataset_version = payload.get("dataset_version")
        resume_from = payload.get("resume_from")

        # Pull dataset from Supabase / local DB
        train_path = self._pull_dataset(dataset_version)

        # Update job: dataset pulled
        self.db.update_training_job(
            job["id"], dataset_version=dataset_version or "local"
        )

        cfg = TrainingConfig(
            data_path=train_path,
            checkpoint_dir=str(CKPT_DIR),
            epochs=epochs,
            batch_size=batch_size,
            seq_len=seq_len,
            learning_rate=lr,
            save_every=50,
        )

        tr = DOOFTrainer(cfg)

        # Resume from existing checkpoint if requested
        if resume_from:
            from pathlib import Path as P
            ckpt = P(resume_from)
            if not ckpt.is_absolute():
                ckpt = ROOT / resume_from
            if ckpt.exists():
                import torch
                state = torch.load(ckpt, map_location=tr.device, weights_only=False)
                tr.model.load_state_dict(state["model_state_dict"])
                epochs_done = state.get("step", 0)
                # Adjust total epochs accounting for resume
                tr.config = tr.config

        tokens = tr.load_data()

        # Update job to running with epoch info
        self.db.update_training_job(
            job["id"],
            status="running",
            total_epochs=epochs,
            epoch=0,
        )
        self._current_job = job["id"]

        import torch
        import torch.nn.functional as F
        from torch.amp import autocast
        from tqdm import tqdm

        step = 0
        loss_val = 0.0
        total_steps = epochs * 100

        for epoch in range(epochs):
            if self._stop_event.is_set():
                break

            for batch_i in tqdm(range(100), desc=f"Epoch {epoch + 1}/{epochs}"):
                if self._stop_event.is_set():
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
                        logits.reshape(-1, logits.size(-1)),
                        y.reshape(-1),
                    )

                tr.scaler.scale(loss).backward()
                tr.scaler.unscale_(tr.optimizer)
                torch.nn.utils.clip_grad_norm_(tr.model.parameters(), 1.0)
                tr.scaler.step(tr.optimizer)
                tr.scaler.update()

                step += 1
                loss_val = float(loss.item())

                # Update job progress via DB
                if step % 10 == 0:
                    self.db.update_training_job(
                        job["id"],
                        step=step,
                        epoch=epoch + 1,
                        loss=round(loss_val, 4),
                    )

            tr.save_checkpoint(step, loss_val)

        # Final checkpoint
        ckpt_name = f"doof_v{__version__}_job_{job['id'][:8]}.pt"
        final_path = CKPT_DIR / ckpt_name
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
                "config": cfg.__dict__,
            },
            final_path,
        )

        # ------------------------------------------------------------------
        # Upload checkpoint + brain version to Supabase (or local)
        # ------------------------------------------------------------------
        self._upload_brain_version(ckpt_name, step, loss_val, dataset_version)

        # Mark job as done
        self.db.update_training_job(
            job["id"],
            status="done",
            step=step,
            epoch=epochs,
            loss=round(loss_val, 4),
            checkpoint_name=ckpt_name,
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        self._current_job = None

        return {
            "checkpoint_name": ckpt_name,
            "step": step,
            "loss": loss_val,
            "epochs": epochs,
            "total_steps": total_steps,
        }

    def _upload_brain_version(
        self,
        checkpoint_name: str,
        step: int,
        loss: float,
        dataset_version: str | None,
    ) -> dict[str, Any]:
        """Record a candidate brain version in the database.

        The version is stored as ``candidate`` — it must be explicitly
        evaluated and promoted before going to production.
        """
        versions = self.db.get_versions() if hasattr(self.db, "get_versions") else []
        # Count existing candidates to assign the next label
        candidates = [v for v in versions if v.get("status") == "candidate"]
        label = f"v{len(candidates) + 1}.0.0-candidate"

        record = {
            "checkpoint_name": checkpoint_name,
            "label": label,
            "status": "candidate",
            "promoted_by": self.node_name,
            "perplexity": None,
            "eval_passed": None,
        }

        result = self.db.insert_version(record)
        return result

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _heartbeat_loop(self) -> None:
        """Background thread: register and send periodic heartbeats."""
        try:
            self.register()
        except Exception:
            pass

        while not self._stop_event.is_set():
            try:
                self.send_heartbeat(
                    training_active=self._current_job is not None
                )
            except Exception:
                pass
            self._stop_event.wait(self.HEARTBEAT_INTERVAL)

    def run(self) -> None:
        """Main worker loop — blocks until stopped."""
        # Register + start heartbeat thread
        try:
            self.register()
        except Exception as e:
            print(f"[worker] Failed to register: {e}")

        hb_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="doof-heartbeat"
        )
        hb_thread.start()

        print(f"[worker] {self.node_name} online — polling for jobs...")

        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        while not self._stop_event.is_set():
            try:
                jobs = self._poll_jobs()
                for job in jobs:
                    if job["status"] == "queued":
                        # Try to claim it
                        claimed = self.db.claim_training_job(
                            job["id"], self.node_id
                        )
                        if claimed:
                            print(f"[worker] Claimed training job {job['id']}")
                            try:
                                self._run_training(job)
                            except Exception as e:
                                print(f"[worker] Job failed: {e}")
                                traceback.print_exc()
                                self.db.update_training_job(
                                    job["id"],
                                    status="failed",
                                    error=str(e),
                                )
                            finally:
                                self._current_job = None
                        else:
                            # Another worker grabbed it, or status changed
                            continue
                    elif job["status"] == "running":
                        # This job is already assigned to us but running
                        # (e.g. after a restart). Pick up where it left off
                        # if possible, or mark as failed.
                        print(f"[worker] Resuming job {job['id']}")
                        try:
                            self._run_training(job)
                        except Exception as e:
                            self.db.update_training_job(
                                job["id"], status="failed", error=str(e)
                            )
                        finally:
                            self._current_job = None
            except Exception as e:
                print(f"[worker] Poll error: {e}")

            self._stop_event.wait(self.POLL_INTERVAL)

        print(f"[worker] {self.node_name} shutting down.")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        print(f"\n[worker] Signal {signum} received, shutting down...")
        self._stop_event.set()


# Module-level convenience
def run_worker(node_name: str | None = None, api_base: str | None = None) -> None:
    worker = TrainingWorker(node_name=node_name, api_base=api_base)
    worker.run()
