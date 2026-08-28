"""Chat must answer even when torch is missing. Never leak torchdistribute."""
from __future__ import annotations

import json
import os
import threading
import unittest
from http.client import HTTPConnection


class GenerateFallbackTests(unittest.TestCase):
    def setUp(self):
        os.environ["DOOF_DISABLE_TORCH"] = "1"
        # Reset the torch import cache so the env var takes effect
        import doof.runtime as _rt
        _rt._torch_tried = False
        _rt._torch_mod = None

    def tearDown(self):
        os.environ.pop("DOOF_DISABLE_TORCH", None)

    @classmethod
    def setUpClass(cls):
        from doof.api import run_server

        cls.port = 18765
        t = threading.Thread(
            target=run_server, kwargs={"host": "127.0.0.1", "port": cls.port}, daemon=True
        )
        t.start()
        import time
        for _ in range(40):
            try:
                c = HTTPConnection("127.0.0.1", cls.port, timeout=0.3)
                c.request("GET", "/api/health")
                if c.getresponse().status == 200:
                    return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("API did not start")

    def _post(self, path: str, body: dict):
        c = HTTPConnection("127.0.0.1", self.port, timeout=8)
        raw = json.dumps(body).encode()
        c.request("POST", path, body=raw, headers={"Content-Type": "application/json"})
        r = c.getresponse()
        return r.status, json.loads(r.read())

    def _get(self, path: str):
        c = HTTPConnection("127.0.0.1", self.port, timeout=8)
        c.request("GET", path)
        r = c.getresponse()
        return r.status, json.loads(r.read())

    def test_health(self):
        code, data = self._get("/api/health")
        self.assertEqual(code, 200)
        self.assertTrue(data.get("ok"))
        self.assertIn("label", data)

    def test_status_honest(self):
        code, data = self._get("/api/status")
        self.assertEqual(code, 200)
        self.assertIn(data.get("mode"), ("local", "connected", "offline", "degraded"))
        self.assertFalse(data["brain"]["torch_available"])
        self.assertTrue(any(p.get("kind") == "ai_down" for p in data.get("problems") or []))

    def test_chat_without_torch(self):
        code, data = self._post("/api/generate", {"prompt": "What do you remember?"})
        self.assertEqual(code, 200)
        self.assertTrue(data.get("text"))
        blob = json.dumps(data).lower()
        self.assertNotIn("torchdistribute", blob)
        self.assertNotIn("traceback", blob)
        self.assertNotIn("modulenotfounderror", blob)

    def test_rejects_arbitrary_code_job(self):
        code, data = self._post("/api/compute/execute", {"type": "shell", "payload": {"cmd": "id"}})
        self.assertIn(code, (400, 500))
        blob = json.dumps(data).lower()
        self.assertNotIn("traceback", blob)

    def test_auth_config_google_states(self):
        code, data = self._get("/api/auth/config")
        self.assertEqual(code, 200)
        self.assertEqual(data.get("google"), "not_configured")
        self.assertFalse(data.get("oauth"))