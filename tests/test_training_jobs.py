"""Tests for DOOF v0.2 Training System.

Covers:
  - Database adapter: training_jobs, approved_examples, nodes, feedback
  - Scheduler: strongest-worker selection, training job assignment
  - API helper functions (training_stats, create_training_job, etc.)
  - Safety rules:
      * Never train on raw conversations
      * Only train approved feedback/examples
      * Never auto-promote without evaluation
"""
from __future__ import annotations

import os
import time
import unittest
from unittest import mock

# Force local backend BEFORE any database imports
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_SERVICE_KEY", None)
os.environ.pop("SUPABASE_ANON_KEY", None)
os.environ["SUPABASE_URL"] = ""

from database import get_db, local as local_db
from doof.api import (
    training_stats,
    create_training_job,
    cancel_training_job,
    get_training_jobs_api,
    add_approved_example,
    get_approved_examples_api,
    delete_approved_example_api,
    approve_feedback,
    add_feedback,
    get_nodes_with_local,
)
from doof.intelligence.scheduler import (
    assign_training_job,
    select_strongest_worker,
    JobScheduler,
    Job,
    JobType,
    JobStatus,
)

# Patch get_db everywhere to return the local adapter
_get_db_patch = mock.patch("database.get_db", return_value=local_db)
_get_db_patch.start()


def _db():
    return local_db


def _reset_files():
    """Reset all JSON data files to empty lists."""
    for f in [local_db._JOBS, local_db._NODES, local_db._EXAMPLES,
              local_db._FEEDBACK, local_db._VERSIONS, local_db._MEMORIES,
              local_db._COMPUTE, local_db._REWARDS, local_db._MODELS]:
        local_db._write(f, [])


class _DBTestCase(unittest.TestCase):
    """Base test case that resets data files and provides self.db."""

    def setUp(self) -> None:
        _reset_files()
        self.db = local_db


class TestTrainingJobsDB(_DBTestCase):
    """Test the training_jobs table through the local JSON adapter."""

    def test_insert_and_get_training_job(self):
        job = self.db.insert_training_job({
            "type": "train",
            "payload": {"epochs": 3},
            "created_by": "test",
            "priority": 5,
        })
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["type"], "train")
        self.assertIn("id", job)
        self.assertIn("created_at", job)

        jobs = self.db.get_training_jobs(status="queued")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], job["id"])

    def test_update_training_job(self) -> None:
        job = self.db.insert_training_job({"type": "train"})
        updated = self.db.update_training_job(job["id"], status="running")
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "running")
        self.assertIn("started_at", updated)

    def test_claim_training_job_atomic(self):
        job = self.db.insert_training_job({"type": "train"})
        claimed = self.db.claim_training_job(job["id"], "worker-1")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["worker"], "worker-1")

        claimed_again = self.db.claim_training_job(job["id"], "worker-2")
        self.assertIsNone(claimed_again)

    def test_claim_nonexistent_job(self):
        result = self.db.claim_training_job("nonexistent-id", "worker-1")
        self.assertIsNone(result)

    def test_delete_training_job(self):
        job = self.db.insert_training_job({"type": "train"})
        ok = self.db.delete_training_job(job["id"])
        self.assertTrue(ok)
        jobs = self.db.get_training_jobs()
        self.assertEqual(len(jobs), 0)

    def test_delete_training_job_nonexistent(self):
        ok = self.db.delete_training_job("nonexistent-id")
        self.assertFalse(ok)

    def test_get_training_jobs_by_worker(self):
        j1 = self.db.insert_training_job({"type": "train", "worker": "w1"})
        j2 = self.db.insert_training_job({"type": "train", "worker": "w2"})
        by_w1 = self.db.get_training_jobs(worker_id="w1")
        self.assertEqual(len(by_w1), 1)
        self.assertEqual(by_w1[0]["id"], j1["id"])

    def test_training_job_default_status(self):
        job = self.db.insert_training_job({"type": "train"})
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["priority"], 5)


class TestApprovedExamplesDB(_DBTestCase):
    """Test the approved_examples table."""

    def test_insert_and_get_example(self):
        ex = self.db.insert_approved_example({
            "prompt": "What is 2+2?",
            "response": "4",
            "rating": "good",
        })
        self.assertEqual(ex["approved"], True)
        self.assertEqual(ex["training_ready"], True)
        self.assertIn("id", ex)
        self.assertIn("created_at", ex)

        examples = self.db.get_approved_examples()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["prompt"], "What is 2+2?")

    def test_get_approved_examples_filter(self):
        self.db.insert_approved_example({"prompt": "Q1", "response": "A1", "approved": True})
        self.db.insert_approved_example({"prompt": "Q2", "response": "A2", "approved": False})
        approved = self.db.get_approved_examples(approved_only=True)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["prompt"], "Q1")

    def test_count_approved_examples(self):
        self.db.insert_approved_example({"prompt": "Q1", "response": "A1"})
        self.db.insert_approved_example({"prompt": "Q2", "response": "A2"})
        counts = self.db.count_approved_examples()
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["approved"], 2)
        self.assertEqual(counts["training_ready"], 2)

    def test_delete_approved_example(self):
        ex = self.db.insert_approved_example({"prompt": "Q", "response": "A"})
        ok = self.db.delete_approved_example(ex["id"])
        self.assertTrue(ok)
        examples = self.db.get_approved_examples()
        self.assertEqual(len(examples), 0)

    def test_delete_nonexistent_example(self):
        ok = self.db.delete_approved_example("nonexistent")
        self.assertFalse(ok)


class TestNodesAndWorkers(_DBTestCase):
    """Test node registration, heartbeat, and worker selection."""

    def test_upsert_node(self):
        node = self.db.upsert_node({
            "id": "test-node",
            "name": "TestNode",
            "gpu": "RTX 4090",
            "vram_gb": 24.0,
            "status": "online",
            "last_seen": time.time(),
        })
        self.assertEqual(node["id"], "test-node")
        nodes = self.db.get_nodes()
        self.assertEqual(len(nodes), 1)

    def test_upsert_node_update_existing(self):
        self.db.upsert_node({"id": "n1", "name": "Test", "gpu": "CPU", "vram_gb": 0, "status": "online", "last_seen": time.time()})
        self.db.upsert_node({"id": "n1", "name": "Test", "gpu": "RTX 4090", "vram_gb": 24.0, "status": "online", "last_seen": time.time()})
        nodes = self.db.get_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["gpu"], "RTX 4090")

    def test_update_node(self):
        self.db.upsert_node({"id": "n1", "name": "Test", "vram_gb": 0, "status": "online", "last_seen": time.time()})
        updated = self.db.update_node("n1", status="offline", vram_gb=16.0)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "offline")
        self.assertEqual(updated["vram_gb"], 16.0)

    def test_update_node_nonexistent(self):
        result = self.db.update_node("nonexistent", status="offline")
        self.assertIsNone(result)

    def test_get_online_nodes(self):
        now = time.time()
        self.db.upsert_node({"id": "online1", "name": "Online", "vram_gb": 24, "status": "online", "last_seen": now})
        self.db.upsert_node({"id": "offline1", "name": "Offline", "vram_gb": 0, "status": "offline", "last_seen": now - 3600, "is_local": False})
        online = self.db.get_online_nodes()
        self.assertEqual(len(online), 1)
        self.assertEqual(online[0]["id"], "online1")

    def test_get_strongest_online_worker(self):
        now = time.time()
        self.db.upsert_node({"id": "weak", "name": "Weak", "vram_gb": 8, "status": "online", "last_seen": now})
        self.db.upsert_node({"id": "strong", "name": "Strong", "vram_gb": 24, "status": "online", "last_seen": now})
        self.db.upsert_node({"id": "medium", "name": "Medium", "vram_gb": 16, "status": "online", "last_seen": now})
        strongest = self.db.get_strongest_online_worker()
        self.assertIsNotNone(strongest)
        self.assertEqual(strongest["id"], "strong")
        self.assertEqual(strongest["vram_gb"], 24)

    def test_strongest_worker_none_online(self):
        strongest = self.db.get_strongest_online_worker()
        self.assertIsNone(strongest)

    def test_delete_node(self):
        self.db.upsert_node({"id": "n1", "name": "Test", "vram_gb": 0, "status": "online", "last_seen": time.time()})
        ok = self.db.delete_node("n1")
        self.assertTrue(ok)
        nodes = self.db.get_nodes()
        self.assertEqual(len(nodes), 0)


class TestSchedulerWorkerSelection(_DBTestCase):
    """Test the scheduler's worker selection logic."""

    def test_assign_training_job_no_workers(self):
        result = assign_training_job(payload={"epochs": 1}, created_by="test")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(result["worker"])
        self.assertIsNone(result.get("assigned_to"))

    def test_assign_training_job_to_strongest(self):
        now = time.time()
        self.db.upsert_node({"id": "weak", "name": "Weak", "vram_gb": 8, "status": "online", "last_seen": now, "gpu": "RTX 3060"})
        self.db.upsert_node({"id": "strong", "name": "Strong", "vram_gb": 24, "status": "online", "last_seen": now, "gpu": "RTX 4090"})
        result = assign_training_job(payload={"epochs": 1}, created_by="test")
        self.assertIsNotNone(result)
        self.assertEqual(result["worker"], "strong")
        self.assertEqual(result["assigned_to"], "Strong")

    def test_assign_training_job_payload_preserved(self):
        payload = {"epochs": 5, "seq_len": 128, "learning_rate": 1e-4}
        result = assign_training_job(payload=payload, created_by="test")
        self.assertEqual(result["payload"], payload)
        self.assertEqual(result["created_by"], "test")
        self.assertEqual(result["type"], "train")


class TestSchedulerJobQueue(unittest.TestCase):
    """Test the JobScheduler in-process queue (for build_dataset, evaluate)."""

    def setUp(self) -> None:
        _reset_files()

    def test_enqueue_and_status(self):
        sched = JobScheduler()
        sched.start()
        try:
            job = Job(JobType.BUILD_DATASET, {"version": "test"})
            sched.enqueue(job)
            self.assertIn(job.id, sched._jobs)
            self.assertEqual(sched._jobs[job.id].status, JobStatus.QUEUED)
        finally:
            sched.stop()

    def test_cancel_queued_job(self):
        sched = JobScheduler()
        sched.start()
        try:
            job = Job(JobType.BUILD_DATASET, {"version": "test"})
            sched.enqueue(job)
            ok = sched.cancel(job.id)
            self.assertTrue(ok)
            self.assertEqual(sched._jobs[job.id].status, JobStatus.CANCELLED)
        finally:
            sched.stop()

    def test_cancel_non_queued_job_fails(self):
        sched = JobScheduler()
        sched.start()
        try:
            job = Job(JobType.BUILD_DATASET, {})
            sched.enqueue(job)
            time.sleep(0.3)
            ok = sched.cancel(job.id)
            self.assertFalse(ok)
        finally:
            sched.stop()


class TestTrainingStatsAPI(_DBTestCase):
    """Test the training_stats() helper that powers GET /api/training."""

    def test_training_stats_keys(self):
        stats = training_stats()
        expected_keys = {
            "running", "step", "loss", "epoch", "message", "history",
            "speed", "eta_seconds", "approved_examples", "training_ready_examples",
            "memory_count", "brain_version", "dataset_version", "examples_count",
            "total_feedback", "workers_online", "training_queue", "running_jobs",
            "online_nodes",
        }
        self.assertTrue(expected_keys.issubset(stats.keys()))

    def test_training_stats_examples_count(self):
        self.db.insert_approved_example({"prompt": "Q1", "response": "A1"})
        self.db.insert_approved_example({"prompt": "Q2", "response": "A2"})
        stats = training_stats()
        self.assertEqual(stats["examples_count"], 2)
        self.assertEqual(stats["approved_examples"], 2)

    def test_training_stats_workers_online(self):
        now = time.time()
        self.db.upsert_node({"id": "w1", "name": "W1", "vram_gb": 24, "status": "online", "last_seen": now, "gpu": "RTX 4090"})
        self.db.upsert_node({"id": "w2", "name": "W2", "vram_gb": 16, "status": "online", "last_seen": now, "gpu": "RTX 3060"})
        stats = training_stats()
        self.assertEqual(stats["workers_online"], 2)
        self.assertEqual(len(stats["online_nodes"]), 2)

    def test_training_stats_training_queue(self):
        self.db.insert_training_job({"type": "train", "status": "queued", "priority": 3, "payload": {"epochs": 1}, "worker": None})
        stats = training_stats()
        self.assertEqual(len(stats["training_queue"]), 1)
        self.assertEqual(stats["training_queue"][0]["priority"], 3)

    def test_training_stats_brain_version(self):
        stats = training_stats()
        self.assertEqual(stats["brain_version"], "1.0.0")

        self.db.insert_version({"checkpoint_name": "doof_v01.pt", "label": "v1.0.0", "status": "production"})
        stats = training_stats()
        self.assertEqual(stats["brain_version"], "v1.0.0")
        self.assertEqual(stats["production_checkpoint"], "doof_v01.pt")


class TestFeedbackApproval(_DBTestCase):
    """Test the feedback -> approved_examples promotion."""

    def test_approve_feedback_creates_example(self):
        fb = add_feedback("What is 2+2?", "4", "good")
        result = approve_feedback(fb["id"])
        self.assertIsNotNone(result)
        self.assertTrue(result["approved"])
        self.assertEqual(result["source"], "feedback")
        self.assertEqual(result["source_feedback_id"], fb["id"])
        self.assertEqual(result["prompt"], "What is 2+2?")
        self.assertEqual(result["response"], "4")

    def test_approve_feedback_nonexistent(self):
        result = approve_feedback("nonexistent-id")
        self.assertIsNone(result)

    def test_approve_correction_feedback(self):
        fb = add_feedback("What is 2+2?", "Five", "bad", correction="4")
        result = approve_feedback(fb["id"])
        self.assertIsNotNone(result)
        self.assertEqual(result["response"], "4")
        self.assertEqual(result["correction"], "4")
        self.assertTrue(result["approved"])

    def test_approved_example_count_increases(self):
        fb = add_feedback("Q", "A", "good")
        before = self.db.count_approved_examples()["total"]
        approve_feedback(fb["id"])
        after = self.db.count_approved_examples()["total"]
        self.assertEqual(after, before + 1)

    def test_only_approved_examples_returned(self):
        self.db.insert_approved_example({"prompt": "Q1", "response": "A1", "approved": True})
        self.db.insert_approved_example({"prompt": "Q2", "response": "A2", "approved": False})
        self.db.insert_approved_example({"prompt": "Q3", "response": "A3", "approved": True})
        examples = self.db.get_approved_examples(approved_only=True)
        self.assertEqual(len(examples), 2)
        for ex in examples:
            self.assertTrue(ex.get("approved", True))


class TestTrainingJobCreation(_DBTestCase):
    """Test the API-level training job creation and cancellation."""

    def test_create_training_job(self):
        job = create_training_job({"epochs": 3, "seq_len": 64})
        self.assertIsNotNone(job)
        self.assertEqual(job["type"], "train")
        self.assertEqual(job["status"], "queued")
        self.assertIsNotNone(job["payload"])
        self.assertEqual(job["payload"]["epochs"], 3)

    def test_cancel_training_job(self):
        job = create_training_job({"epochs": 1})
        ok = cancel_training_job(job["id"])
        self.assertTrue(ok)
        updated = self.db.get_training_jobs(status="cancelled")
        self.assertEqual(len(updated), 1)

    def test_cancel_nonexistent_job(self):
        ok = cancel_training_job("nonexistent-id")
        self.assertFalse(ok)

    def test_get_training_jobs_api(self):
        create_training_job({"epochs": 1})
        create_training_job({"epochs": 2})
        jobs = get_training_jobs_api(status="queued")
        self.assertEqual(len(jobs), 2)


class TestApprovedExamplesAPI(_DBTestCase):
    """Test the approved_examples API-level functions."""

    def test_add_approved_example(self):
        ex = add_approved_example({"prompt": "What is 2+2?", "response": "4", "rating": "good"})
        self.assertEqual(ex["prompt"], "What is 2+2?")
        self.assertEqual(ex["response"], "4")
        self.assertTrue(ex["approved"])

    def test_add_approved_example_missing_fields(self):
        with self.assertRaises(ValueError):
            add_approved_example({"prompt": "", "response": "A"})
        with self.assertRaises(ValueError):
            add_approved_example({"prompt": "Q", "response": ""})

    def test_get_approved_examples_api(self):
        add_approved_example({"prompt": "Q1", "response": "A1"})
        add_approved_example({"prompt": "Q2", "response": "A2"})
        examples = get_approved_examples_api()
        self.assertEqual(len(examples), 2)

    def test_delete_approved_example_api(self):
        ex = add_approved_example({"prompt": "Q", "response": "A"})
        ok = delete_approved_example_api(ex["id"])
        self.assertTrue(ok)
        examples = get_approved_examples_api()
        self.assertEqual(len(examples), 0)

    def test_delete_nonexistent_example(self):
        ok = delete_approved_example_api("nonexistent-id")
        self.assertFalse(ok)


class TestSafetyRules(_DBTestCase):
    """Verify the core safety rules of the training system."""

    def test_never_train_on_raw_conversations(self):
        """Raw feedback is NOT in the approved_examples table."""
        add_feedback("raw prompt", "raw response", "good")
        examples = self.db.get_approved_examples()
        self.assertEqual(len(examples), 0)

    def test_only_train_approved_examples(self):
        """Only approved + training_ready examples are returned for training."""
        self.db.insert_approved_example(
            {"prompt": "Q1", "response": "A1", "approved": True, "training_ready": True, "quality": 80}
        )
        self.db.insert_approved_example(
            {"prompt": "Q2", "response": "A2", "approved": True, "training_ready": False, "quality": 30}
        )
        self.db.insert_approved_example(
            {"prompt": "Q3", "response": "A3", "approved": False, "training_ready": True, "quality": 90}
        )
        training = self.db.get_approved_examples(approved_only=True, training_ready_only=True)
        self.assertEqual(len(training), 1)
        self.assertEqual(training[0]["prompt"], "Q1")

    def test_never_auto_promote_without_evaluation(self):
        """promote_checkpoint does not auto-promote without eval."""
        from doof.api import promote_checkpoint
        self.db.insert_version({"checkpoint_name": "doof_v01.pt", "label": "v1.0.0-candidate", "status": "candidate"})
        result = promote_checkpoint("doof_v01.pt", "v1.0.0")
        self.assertTrue(result["ok"])
        self.assertIsNone(result["eval_passed"])

    def test_auto_demote_previous_production(self):
        """When promoting a new production, the old one is demoted."""
        from doof.api import promote_checkpoint
        self.db.insert_version({"checkpoint_name": "old.pt", "label": "v1.0.0", "status": "production"})
        promote_checkpoint("new.pt", "v2.0.0")
        versions = self.db.get_versions()
        old = next(v for v in versions if v.get("checkpoint_name") == "old.pt")
        new = next(v for v in versions if v.get("checkpoint_name") == "new.pt")
        self.assertEqual(old["status"], "archived")
        self.assertEqual(new["status"], "production")


class TestNodeHeartbeat(_DBTestCase):
    """Test node registration and heartbeat flow."""

    def test_get_nodes_with_local_registers(self):
        nodes = get_nodes_with_local()
        self.assertTrue(len(nodes) >= 1)
        local_node = next((n for n in nodes if n.get("is_local")), None)
        self.assertIsNotNone(local_node)
        self.assertTrue(len(local_node.get("id", "")) > 0)
        self.assertEqual(local_node["status"], "online")

    def test_local_node_has_gpu_info(self):
        nodes = get_nodes_with_local()
        local_node = next((n for n in nodes if n.get("is_local")), None)
        self.assertIsNotNone(local_node)
        self.assertIn("gpu", local_node)
        self.assertIn("vram_gb", local_node)


class TestDatabaseAdapter(unittest.TestCase):
    """Verify both backends expose the same interface."""

    def test_local_adapter_has_all_methods(self):
        required = [
            "get_memories", "insert_memory", "delete_memory",
            "get_feedback", "insert_feedback", "update_feedback",
            "get_nodes", "upsert_node", "delete_node", "update_node",
            "get_versions", "insert_version", "update_version",
            "get_approved_examples", "insert_approved_example",
            "delete_approved_example", "count_approved_examples",
            "get_training_jobs", "insert_training_job", "update_training_job",
            "claim_training_job", "delete_training_job",
            "get_online_nodes", "get_strongest_online_worker",
        ]
        for name in required:
            self.assertTrue(hasattr(local_db, name), f"local.{name} missing")

    def test_supabase_adapter_has_all_methods(self):
        from database import supabase
        required = [
            "get_memories", "insert_memory", "delete_memory",
            "get_feedback", "insert_feedback", "update_feedback",
            "get_nodes", "upsert_node", "delete_node", "update_node",
            "get_versions", "insert_version", "update_version",
            "get_approved_examples", "insert_approved_example",
            "delete_approved_example", "count_approved_examples",
            "get_training_jobs", "insert_training_job", "update_training_job",
            "claim_training_job", "delete_training_job",
            "get_online_nodes", "get_strongest_online_worker",
        ]
        for name in required:
            self.assertTrue(hasattr(supabase, name), f"supabase.{name} missing")

    def test_get_db_returns_local_by_default(self):
        """Without SUPABASE_URL, local JSON backend is used."""
        with mock.patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": "", "SUPABASE_ANON_KEY": ""}):
            db = get_db()
            self.assertIs(db, local_db)


class TestAPIHelpers(_DBTestCase):
    """Test the API helper functions that wrap db operations."""

    def test_get_training_jobs_api_returns_list(self):
        jobs = get_training_jobs_api()
        self.assertIsInstance(jobs, list)

    def test_create_training_job_payload(self):
        body = {
            "epochs": 5,
            "seq_len": 128,
            "batch_size": 4,
            "learning_rate": 1e-4,
            "priority": 3,
        }
        job = create_training_job(body)
        self.assertEqual(job["payload"]["epochs"], 5)
        self.assertEqual(job["payload"]["seq_len"], 128)
        self.assertEqual(job["priority"], 3)

    def test_cancel_training_job_not_found(self):
        ok = cancel_training_job("does-not-exist")
        self.assertFalse(ok)

    def test_training_stats_returns_valid(self):
        stats = training_stats()
        self.assertIn("running", stats)
        self.assertIn("examples_count", stats)
        self.assertIn("workers_online", stats)
        self.assertIsInstance(stats["running"], bool)
        self.assertIsInstance(stats["examples_count"], int)


if __name__ == "__main__":
    unittest.main()
