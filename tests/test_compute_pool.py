"""Compute pool: typed jobs, scheduler honesty, no arbitrary code."""
from __future__ import annotations

import time
import unittest

from doof.compute.jobs import JobRejected, validate_payload
from doof.compute.scheduler import is_stale, score_node, select_node, node_state


class JobSchemaTests(unittest.TestCase):
    def test_rejects_unknown_type(self):
        with self.assertRaises(JobRejected):
            validate_payload("rm_rf", {"cmd": "rm -rf /"})

    def test_inference_requires_prompt(self):
        with self.assertRaises(JobRejected):
            validate_payload("inference", {})
        p = validate_payload("inference", {"prompt": "hello", "max_new_tokens": 9999})
        self.assertEqual(p["prompt"], "hello")
        self.assertLessEqual(p["max_new_tokens"], 256)


class SchedulerTests(unittest.TestCase):
    def test_stale_node_not_selected(self):
        dead = {
            "id": "dead",
            "status": "online",
            "last_seen": time.time() - 600,
            "accepting_jobs": True,
            "vram_gb": 24,
            "cuda_available": True,
            "max_jobs": 2,
            "job_count": 0,
        }
        live = {
            "id": "live",
            "status": "online",
            "last_seen": time.time(),
            "accepting_jobs": True,
            "vram_gb": 8,
            "cuda_available": True,
            "max_jobs": 2,
            "job_count": 0,
        }
        self.assertTrue(is_stale(dead))
        self.assertLess(score_node(dead, "inference"), 0)
        chosen = select_node([dead, live], "inference")
        self.assertEqual(chosen["id"], "live")

    def test_does_not_use_unwilling_remote(self):
        remote = {
            "id": "k",
            "status": "online",
            "last_seen": time.time(),
            "accepting_jobs": False,
            "vram_gb": 24,
            "cuda_available": True,
            "max_jobs": 2,
            "job_count": 0,
        }
        local = {
            "id": "me",
            "is_local": True,
            "status": "online",
            "last_seen": time.time(),
            "accepting_jobs": False,
            "vram_gb": 0,
            "max_jobs": 1,
            "job_count": 0,
        }
        chosen = select_node([remote, local], "inference", local_id="me")
        self.assertEqual(chosen["id"], "me")

    def test_prefers_gpu_when_accepting(self):
        cpu = {
            "id": "potato",
            "status": "online",
            "last_seen": time.time(),
            "accepting_jobs": True,
            "vram_gb": 0,
            "cuda_available": False,
            "max_jobs": 1,
            "job_count": 0,
            "cpu_count": 4,
        }
        gpu = {
            "id": "grill",
            "status": "online",
            "last_seen": time.time(),
            "accepting_jobs": True,
            "vram_gb": 12,
            "cuda_available": True,
            "accept_gpu": True,
            "max_jobs": 2,
            "job_count": 0,
        }
        chosen = select_node([cpu, gpu], "inference")
        self.assertEqual(chosen["id"], "grill")

    def test_states_are_distinct(self):
        n = {
            "id": "x",
            "status": "offline",
            "last_seen": time.time() - 400,
        }
        self.assertIn(node_state(n), ("registered", "visible"))
