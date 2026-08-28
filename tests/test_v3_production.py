"""DOOF v3.0.0 production requirements — comprehensive test suite.

Covers: version constants, inference router, brain lightweight path,
memory store CRUD, compute job validation, update client, and API exports.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["DOOF_DISABLE_TORCH"] = "1"
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_ANON_KEY", None)
os.environ.pop("XAI_API_KEY", None)


# ---------------------------------------------------------------------------
# VERSION TESTS
# ---------------------------------------------------------------------------

class VersionTests(unittest.TestCase):
    def test_version_is_3_0_0(self):
        from doof import __version__
        self.assertEqual(__version__, "3.0.0")

    def test_version_display(self):
        from doof import DOOF_VERSION_DISPLAY
        self.assertEqual(DOOF_VERSION_DISPLAY, "DOOF v3.0")

    def test_protocol(self):
        from doof import __protocol__
        self.assertEqual(__protocol__, "1")


# ---------------------------------------------------------------------------
# INFERENCE ROUTER TESTS
# ---------------------------------------------------------------------------

class InferenceRouterTests(unittest.TestCase):
    def test_router_exists(self):
        from doof.inference.router import route_inference
        self.assertTrue(callable(route_inference))

    def test_router_always_returns_result(self):
        from doof.inference.router import route_inference, InferenceResult
        result = route_inference("hello")
        self.assertIsInstance(result, InferenceResult)

    def test_router_result_has_text(self):
        from doof.inference.router import route_inference
        result = route_inference("What is 2 + 2?")
        self.assertIsInstance(result.text, str)
        self.assertTrue(len(result.text.strip()) > 0, "InferenceResult.text must be non-empty")

    @patch.dict(os.environ, {"DOOF_DISABLE_TORCH": "1"})
    def test_router_lightweight_fallback(self):
        from doof.inference.router import route_inference
        result = route_inference("2 * 3")
        self.assertIn(result.provider, ("computed", "none"))
        self.assertEqual(result.text.strip(), "6")

    def test_router_provider_always_set(self):
        from doof.inference.router import route_inference
        result = route_inference("hello there")
        self.assertIsInstance(result.provider, str)
        self.assertTrue(len(result.provider) > 0, "provider must never be empty")


# ---------------------------------------------------------------------------
# BRAIN TESTS
# ---------------------------------------------------------------------------

class BrainTests(unittest.TestCase):
    def test_brain_math_computation(self):
        from doof.brain import math_answer
        result = math_answer("2 * 3")
        self.assertEqual(result.strip(), "6")

    def test_brain_math_addition(self):
        from doof.brain import math_answer
        result = math_answer("5 + 7")
        self.assertEqual(result.strip(), "12")

    def test_brain_memory_retrieval(self):
        from doof.brain import memory_answer
        memories = [
            {"content": "User prefers dark mode", "id": "m1"},
            {"content": "User lives in Ottawa", "id": "m2"},
        ]
        result = memory_answer("What is my favorite setting?", memories)
        result_lower = result.lower()
        self.assertTrue(
            "dark mode" in result_lower or "favorite" in result_lower or "shared" in result_lower,
            f"Expected memory context in response, got: {result}",
        )

    def test_memory_empty_when_no_match(self):
        from doof.brain import memory_answer
        result = memory_answer("What is quantum physics?", [])
        self.assertEqual(result, "")

    def test_postprocess_garbled_returns_empty(self):
        from doof.brain import postprocess_model_text
        garbled = "!!!###$$$%%%" * 5
        cleaned, source = postprocess_model_text(garbled, "who are you")
        self.assertEqual(source, "empty")
        self.assertEqual(cleaned, "")

    def test_postprocess_good_text(self):
        from doof.brain import postprocess_model_text
        good = "DOOF is a private AI that helps with tasks."
        cleaned, source = postprocess_model_text(good, "hello")
        self.assertEqual(cleaned, good)
        self.assertEqual(source, "model")


# ---------------------------------------------------------------------------
# MEMORY STORE TESTS
# ---------------------------------------------------------------------------

class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        from doof.intelligence.store import Store
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.write("[]")
        self._tmp.close()
        self.store = Store(path=self._tmp.name)

    def tearDown(self):
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_store_add_and_list(self):
        item = self.store.add("Test memory content", created_by="test")
        self.assertIn("id", item)
        self.assertEqual(item["content"], "Test memory content")
        items = self.store.list_all()
        self.assertTrue(any(i["id"] == item["id"] for i in items))

    def test_store_search(self):
        self.store.add("The capital of France is Paris", tags=["geography"])
        self.store.add("Python is a programming language", tags=["tech"])
        results = self.store.search("paris")
        self.assertTrue(len(results) >= 1)
        self.assertIn("Paris", results[0]["content"])

    def test_store_delete(self):
        item = self.store.add("Ephemeral memory")
        self.assertTrue(self.store.delete(item["id"]))
        self.assertIsNone(self.store.get(item["id"]))

    def test_store_stats(self):
        self.store.add("Memory A", approved=True, importance="high")
        self.store.add("Memory B", approved=False)
        stats = self.store.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["approved"], 1)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["high_importance"], 1)


# ---------------------------------------------------------------------------
# COMPUTE TESTS
# ---------------------------------------------------------------------------

class ComputeTests(unittest.TestCase):
    def test_job_types_valid(self):
        from doof.compute.jobs import validate_payload
        for jtype in ("inference", "embedding", "train", "evaluate", "build_dataset"):
            if jtype == "inference":
                result = validate_payload(jtype, {"prompt": "hello"})
                self.assertIn("prompt", result)
            elif jtype == "embedding":
                result = validate_payload(jtype, {"text": "hello"})
                self.assertIn("text", result)
            elif jtype == "train":
                result = validate_payload(jtype, {})
                self.assertIn("epochs", result)
            else:
                result = validate_payload(jtype, {})
                self.assertIsInstance(result, dict)

    def test_job_types_invalid(self):
        from doof.compute.jobs import validate_payload, JobRejected
        with self.assertRaises(JobRejected):
            validate_payload("shell", {"cmd": "rm -rf /"})
        with self.assertRaises(JobRejected):
            validate_payload("arbitrary_code", {})

    def test_settings_defaults(self):
        from doof.api_full import _settings
        self.assertIn("temperature", _settings)
        self.assertIn("max_new_tokens", _settings)
        self.assertIn("top_k", _settings)
        self.assertIn("context_length", _settings)
        self.assertIsInstance(_settings["temperature"], (int, float))
        self.assertIsInstance(_settings["max_new_tokens"], int)


# ---------------------------------------------------------------------------
# UPDATE CLIENT TESTS
# ---------------------------------------------------------------------------

class UpdateClientTests(unittest.TestCase):
    def test_parse_version(self):
        from doof.updates.client import _parse_ver
        self.assertEqual(_parse_ver("3.0.0")[:3], (3, 0, 0))
        self.assertEqual(_parse_ver("v0.3.1")[:3], (0, 3, 1))
        self.assertEqual(_parse_ver("1.2.3-beta")[:3], (1, 2, 3))

    def test_newer_detection(self):
        from doof.updates.client import _newer
        self.assertTrue(_newer("3.1.0", "3.0.0"))
        self.assertTrue(_newer("4.0.0", "3.9.9"))
        self.assertFalse(_newer("3.0.0", "3.0.0"))
        self.assertFalse(_newer("2.9.0", "3.0.0"))

    def test_current_version(self):
        from doof.updates.client import current_version
        v = current_version()
        self.assertEqual(v, "3.0.0")

    def test_update_settings_defaults(self):
        from doof.updates.client import get_update_settings
        settings = get_update_settings()
        self.assertEqual(settings["channel"], "stable")
        self.assertIsInstance(settings["check_on_start"], bool)
        self.assertIn("manifest_url", settings)


# ---------------------------------------------------------------------------
# API TESTS
# ---------------------------------------------------------------------------

class ApiTests(unittest.TestCase):
    def test_api_version_import(self):
        from doof.api_full import DOOF_API_VERSION
        self.assertEqual(DOOF_API_VERSION, "3.0.0")

    def test_api_imports(self):
        from doof.api import run_server, DOOF_API_VERSION, DOOF_PROTOCOL
        self.assertTrue(callable(run_server))
        self.assertEqual(DOOF_API_VERSION, "3.0.0")
        self.assertEqual(DOOF_PROTOCOL, "1")


if __name__ == "__main__":
    unittest.main()
