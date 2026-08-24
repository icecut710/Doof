"""Deterministic multi-node compute simulation.

Simulates Machine A (requester) and Machine B (worker) without real hardware.
Real cross-machine testing on separate networks remains required before
claiming production readiness.
"""
from __future__ import annotations

import time
import unittest
from typing import Any

from doof.compute.jobs import validate_payload
from doof.compute.scheduler import select_node, is_stale, score_node


def _node(
    nid: str,
    *,
    accepting: bool = True,
    vram: float = 0,
    cuda: bool = False,
    last_seen: float | None = None,
    max_jobs: int = 1,
    job_count: int = 0,
    is_local: bool = False,
    low_end: bool = False,
) -> dict[str, Any]:
    return {
        "id": nid,
        "name": nid,
        "status": "online",
        "last_seen": last_seen if last_seen is not None else time.time(),
        "accepting_jobs": accepting,
        "vram_gb": vram,
        "cuda_available": cuda,
        "max_jobs": max_jobs,
        "job_count": job_count,
        "is_local": is_local,
        "low_end": low_end,
        "cpu_count": 2 if low_end else 8,
        "accept_gpu": True,
        "accept_cpu": True,
    }


class MultiNodeSimTests(unittest.TestCase):
    def test_a_routes_to_stronger_b(self):
        a = _node("A", accepting=False, is_local=True, low_end=True)
        b = _node("B", accepting=True, vram=12, cuda=True)
        chosen = select_node([a, b], "inference", local_id="A")
        self.assertEqual(chosen["id"], "B")

    def test_b_opt_out_falls_back_to_a(self):
        a = _node("A", accepting=False, is_local=True)
        b = _node("B", accepting=False, vram=24, cuda=True)
        chosen = select_node([a, b], "inference", local_id="A")
        self.assertEqual(chosen["id"], "A")

    def test_stale_b_not_used(self):
        a = _node("A", accepting=False, is_local=True)
        b = _node("B", accepting=True, vram=24, cuda=True, last_seen=time.time() - 600)
        self.assertTrue(is_stale(b))
        chosen = select_node([a, b], "inference", local_id="A")
        self.assertEqual(chosen["id"], "A")

    def test_b_at_capacity_skipped(self):
        a = _node("A", accepting=False, is_local=True)
        b = _node("B", accepting=True, vram=24, cuda=True, max_jobs=1, job_count=1)
        self.assertLess(score_node(b, "inference"), 0)
        chosen = select_node([a, b], "inference", local_id="A")
        self.assertEqual(chosen["id"], "A")

    def test_low_end_penalized(self):
        weak = _node("weak", accepting=True, low_end=True)
        strong = _node("strong", accepting=True, vram=8, cuda=True)
        chosen = select_node([weak, strong], "inference")
        self.assertEqual(chosen["id"], "strong")

    def test_job_payload_safe(self):
        p = validate_payload("inference", {"prompt": "hi from A"})
        self.assertEqual(p["prompt"], "hi from A")


if __name__ == "__main__":
    unittest.main()
