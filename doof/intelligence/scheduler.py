"""DOOF Intelligence — Job Scheduler.

Simple priority-queue-based scheduler for background intelligence jobs:
- build_dataset
- evaluate_checkpoint
- training runs

The scheduler assigns jobs to the best available compute node (highest VRAM).
It does NOT implement distributed gradient synchronization — each job runs
on exactly one worker.

For distributed training jobs, the scheduler creates a record in the
``training_jobs`` database table and assigns it to the strongest online
worker (most VRAM).  Workers poll the table for jobs assigned to them.
"""
from __future__ import annotations

import enum
import json
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from database import get_db

ROOT = Path(__file__).resolve().parents[2]
JOBS_PATH = ROOT / "data" / "jobs.json"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, enum.Enum):
    BUILD_DATASET = "build_dataset"
    EVALUATE = "evaluate"
    TRAIN = "train"
    PROMOTE = "promote"


class Job:
    def __init__(
        self,
        job_type: JobType | str,
        payload: dict[str, Any] | None = None,
        *,
        priority: int = 5,
        created_by: str = "system",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.type = JobType(job_type) if isinstance(job_type, str) else job_type
        self.payload = payload or {}
        self.priority = priority  # 1 = highest, 10 = lowest
        self.created_by = created_by
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.status = JobStatus.QUEUED
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.worker: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "payload": self.payload,
            "priority": self.priority,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "worker": self.worker,
        }

    # Allow priority queue ordering (lower number = higher priority)
    def __lt__(self, other: "Job") -> bool:
        return self.priority < other.priority


def select_strongest_worker() -> dict[str, Any] | None:
    """Find the strongest online worker (highest VRAM).

    Uses the database adapter so it works with both Supabase and local
    JSON backends.
    """
    db = get_db()
    try:
        online = db.get_online_nodes()
    except Exception:
        # Fallback: use the scheduler's own node tracking
        return _scheduler_local_best()
    if not online:
        return None
    return sorted(online, key=lambda n: n.get("vram_gb", 0), reverse=True)[0]


def _scheduler_local_best() -> dict[str, Any] | None:
    """Fallback worker selection using in-memory scheduler state."""
    if _scheduler is None:
        return None
    online = []
    for node_id in list(_scheduler._jobs.keys()):
        pass
    # Check local hardware
    try:
        from doof.api import hardware
        hw = hardware()
    except Exception:
        return None
    gpu = "CPU"
    vram = 0.0
    if hw.get("cuda_available") and hw.get("cuda_devices"):
        dev = hw["cuda_devices"][0]
        gpu = dev.get("name", "Unknown")
        vram = dev.get("total_memory_gb", 0.0)
    return {"id": "local", "name": "Local", "gpu": gpu, "vram_gb": vram,
            "status": "online"}


def assign_training_job(
    *,
    payload: dict[str, Any] | None = None,
    priority: int = 5,
    created_by: str = "system",
) -> dict[str, Any]:
    """Create a training job in the database and assign it to the strongest
    online worker.

    If no workers are online, the job stays queued with ``worker=None``
    and will be picked up when a worker comes online.
    """
    db = get_db()

    # Select the strongest online worker
    worker = select_strongest_worker()
    worker_id = worker["id"] if worker else None

    job_record: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": "train",
        "status": "queued",
        "priority": priority,
        "payload": payload or {},
        "created_by": created_by,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "worker": worker_id,
    }

    result = db.insert_training_job(job_record)
    if worker_id:
        result["assigned_to"] = worker["name"]
    else:
        result["assigned_to"] = None
    return result


class JobScheduler:
    """Single-worker, priority-queue-based job scheduler.

    The scheduler runs a background daemon thread.  Jobs are dispatched
    to registered handler functions when they reach the front of the queue.

    For distributed training jobs, :func:`assign_training_job` should be
    used instead — it writes to the database so remote workers can claim
    the job.
    """

    def __init__(self) -> None:
        self._queue: queue.PriorityQueue[tuple[int, Job]] = queue.PriorityQueue()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._handlers: dict[JobType, Callable[[Job], Any]] = {}
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._current_job: Job | None = None

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register(self, job_type: JobType, handler: Callable[[Job], Any]) -> None:
        """Register a handler function for a job type."""
        self._handlers[job_type] = handler

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def enqueue(self, job: Job) -> Job:
        """Add a job to the queue and persist state."""
        with self._lock:
            self._jobs[job.id] = job
            self._save()
        self._queue.put((job.priority, job))
        return job

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status not in (JobStatus.QUEUED,):
                return False
            job.status = JobStatus.CANCELLED
            self._save()
        return True

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def status(self) -> dict[str, Any]:
        with self._lock:
            jobs = list(self._jobs.values())
            current = self._current_job
        return {
            "queue_depth": self._queue.qsize(),
            "running": current.to_dict() if current else None,
            "total_jobs": len(jobs),
            "done": sum(1 for j in jobs if j.status == JobStatus.DONE),
            "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
        }

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background dispatcher thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._run, daemon=True, name="doof-scheduler"
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                _, job = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            # Skip cancelled jobs
            with self._lock:
                if job.status == JobStatus.CANCELLED:
                    continue
                job.status = JobStatus.RUNNING
                job.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._current_job = job
                self._save()

            handler = self._handlers.get(job.type)
            try:
                if handler:
                    result = handler(job)
                    with self._lock:
                        job.result = result if isinstance(result, dict) else {"output": str(result)}
                        job.status = JobStatus.DONE
                else:
                    with self._lock:
                        job.status = JobStatus.FAILED
                        job.error = f"No handler for job type: {job.type}"
            except Exception as exc:
                with self._lock:
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
            finally:
                with self._lock:
                    job.finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    self._current_job = None
                    self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [j.to_dict() for j in self._jobs.values()]
            JOBS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


# Module-level singleton
_scheduler: JobScheduler | None = None
_sched_lock = threading.Lock()


def get_scheduler() -> JobScheduler:
    global _scheduler
    with _sched_lock:
        if _scheduler is None:
            _scheduler = JobScheduler()
            _scheduler.start()
    return _scheduler
