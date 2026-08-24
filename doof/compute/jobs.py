"""Typed compute jobs. No arbitrary code execution. Ever."""
from __future__ import annotations

from typing import Any

ALLOWED_JOB_TYPES = frozenset(
    {"inference", "embedding", "train", "evaluate", "build_dataset"}
)

_MAX_PROMPT = 8000
_MAX_TOKENS = 256


class JobRejected(ValueError):
    pass


def validate_payload(job_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if job_type not in ALLOWED_JOB_TYPES:
        raise JobRejected(f"unsupported job type: {job_type}")
    data = dict(payload or {})
    if job_type == "inference":
        prompt = str(data.get("prompt") or "").strip()
        if not prompt:
            raise JobRejected("inference requires a prompt")
        if len(prompt) > _MAX_PROMPT:
            raise JobRejected("prompt too long")
        return {
            "prompt": prompt,
            "temperature": _clamp(float(data.get("temperature", 0.7)), 0.05, 2.0),
            "max_new_tokens": int(_clamp(int(data.get("max_new_tokens", 80)), 8, _MAX_TOKENS)),
            "top_k": int(_clamp(int(data.get("top_k", 50)), 1, 200)),
        }
    if job_type == "embedding":
        text = str(data.get("text") or data.get("prompt") or "").strip()
        if not text:
            raise JobRejected("embedding requires text")
        return {"text": text[:_MAX_PROMPT]}
    if job_type == "train":
        return {
            "epochs": int(_clamp(int(data.get("epochs", 3)), 1, 20)),
            "seq_len": int(_clamp(int(data.get("seq_len", 64)), 16, 256)),
            "batch_size": int(_clamp(int(data.get("batch_size", 8)), 1, 32)),
            "learning_rate": float(data.get("learning_rate", 3e-4)),
            "resume_from": data.get("resume_from"),
            "dataset_version": data.get("dataset_version"),
        }
    if job_type in ("evaluate", "build_dataset"):
        return dict(data)
    raise JobRejected(f"unsupported job type: {job_type}")


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
