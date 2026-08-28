from __future__ import annotations
import unittest

import json
import functools
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
import http.server
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CKPT_DIR = ROOT / "checkpoints"
TRAIN = DATA_DIR / "train.txt"

BASIC_AUTH = os.environ.get("DOOF_BASIC_AUTH", "")


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    candidates: list[Path] = []
    try:
        from doof.paths import is_frozen, user_data_dir
        if is_frozen():
            candidates.append(Path(sys.executable).resolve().parent / ".env")
            candidates.append(user_data_dir() / ".env")
    except Exception:
        pass
    candidates.append(Path.cwd() / ".env")
    for p in candidates:
        if p.is_file():
            load_dotenv(p)
            return
    load_dotenv()


try:
    _load_env()
except Exception:
    pass

from database import get_db


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

try:
    from doof.paths import bundle_root, user_data_dir, checkpoints_dir, is_frozen
    ROOT = bundle_root()
    DATA_DIR = user_data_dir()
    CKPT_DIR = checkpoints_dir()
    _FROZEN = is_frozen()
except Exception:
    ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = ROOT / "data"
    CKPT_DIR = ROOT / "checkpoints"
    _FROZEN = False

TRAIN = DATA_DIR / "train.txt"
KNOW = DATA_DIR / "knowledge.json"
SETT = DATA_DIR / "settings.json"
NODES_PATH = DATA_DIR / "nodes.json"
VERSIONS_PATH = DATA_DIR / "brain_versions.json"
PROFILES_PATH = DATA_DIR / "profiles.json"
SESSIONS_PATH = DATA_DIR / "sessions.json"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_inf = None
_loaded: str | None = None
# Boot-time checkpoint probe (architecture from disk, no model in memory)
_boot_probe: dict[str, Any] | None = None
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

# Local node identity (set on first registration / heartbeat)
_local_node_id: str | None = None


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_profiles() -> list[dict[str, Any]]:
    if not PROFILES_PATH.exists():
        return []
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_profiles(profiles: list[dict[str, Any]]) -> None:
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_PATH.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def _machine_id() -> str:
    global _local_node_id
    if _local_node_id is None:
        import hashlib
        _local_node_id = hashlib.sha256(
            os.environ.get("COMPUTERNAME", "unknown").encode()
        ).hexdigest()[:12]
    return _local_node_id


def _bearer_token(self) -> str | None:
    auth = _get_authorization(self)
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _get_authorization(self) -> str | None:
    authorization = self.headers.get("Authorization", "")
    return authorization[len("Basic "):] if authorization.startswith("Basic ") or authorization.startswith("Bearer ") else None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _http(base, method, path, body=None, timeout=30):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _request_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Server management
# ---------------------------------------------------------------------------

RUNNER = (
    "import os, sys;"
    "sys.path.insert(0, r'{root}');"
    "from doof.api_full import run_server;"
    "run_server('127.0.0.1', int(os.environ['DOOF_API_PORT']))"
).format(root=str(ROOT))


class TestE2EPipeline(unittest.TestCase):
    proc = None
    base = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        data_a = root / "A" / "data"
        ckpt_a = root / "A" / "checkpoints"
        data_a.mkdir(parents=True)
        corpus = ("Doof is a friendly ai assistant built by friends. "
                  "Naddaf approves every checkpoint before it ships. ") * 40
        with open(DATA_DIR / "train.txt", "w", encoding="utf-8") as f:
            f.write(corpus)
        cls.data_a, cls.ckpt_a = data_a, ckpt_a
        cls.proc, cls.base = cls._spawn(data_a, ckpt_a)

    @classmethod
    def _spawn(cls, data_dir, ckpt_dir):
        port = _free_port()
        env = dict(os.environ)
        env.pop("DOOF_DISABLE_TORCH", None)
        env.update({
            "DOOF_API_PORT": str(port),
            "DOOF_DATA_DIR": str(data_dir),
            "DOOF_CHECKPOINTS_DIR": str(ckpt_dir),
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_KEY": "",
            "SUPABASE_ANON_KEY": "",
            "PYTHONIOENCODING": "utf-8",
        })
        proc = subprocess.Popen(
            [sys.executable, "-c", RUNNER],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 120
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("Server process died during startup")
            try:
                code, _ = _http(base, "GET", "/api/health", timeout=5)
                if code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        return proc, base

    @classmethod
    def tearDownClass(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=10)
            except Exception:
                cls.proc.kill()
        if cls.tmp:
            cls.tmp.cleanup()

    def _post(self, path, body=None, timeout=60):
        return _http(self.base, "POST", path, body, timeout)

    def _get(self, path, timeout=30):
        return _http(self.base, "GET", path, timeout=timeout)

    # ---------------------------------------------------------------- tests

    def test_01_teach_promote_and_persist(self):
        # Teach DOOF a fact via memory, then promote it to an approved
        # training example.  test_04 verifies this survives a restart.
        fact = "Elias drives a Honda Civic to work every morning."
        code, mem_resp = self._post("/api/memory", {"content": fact})
        self.assertEqual(code, 201)
        self.assertTrue(mem_resp.get("ok"), mem_resp)
        mem = mem_resp["memory"]
        mem_id = mem["id"]

        code, promo = self._post(f"/api/memory/{mem_id}/promote", {
            "prompt": "What does Elias drive?",
            "created_by": "e2e-test",
        })
        self.assertEqual(code, 201)
        self.assertTrue(promo.get("ok"), promo)

        # Memory is visible
        code, mem_list = self._get("/api/memory")
        self.assertEqual(code, 200)
        blob = json.dumps(mem_list)
        self.assertIn("Honda Civic", blob, "memory not persisted")

        # Approved example is visible
        code, appr = self._get("/api/approved_examples")
        self.assertEqual(code, 200)
        blob2 = json.dumps(appr)
        self.assertIn("Honda Civic", blob2, "approved example not persisted")

    def test_02_train_checkpoint_promote_manifest(self):
        code, _ = _http(self.base, "POST", "/api/training/start", {"epochs": 1})
        self.assertEqual(code, 200)
        status = {}
        deadline = time.time() + 600
        while time.time() < deadline:
            _, status = self._get("/api/training")
            msg = str(status.get("message", ""))
            if not status.get("running"):
                break
            time.sleep(2)
        self.assertIn("complete", msg, str(status))
        self.assertGreater(status.get("step", 0), 0)

        ckpts = [p.name for p in self.ckpt_a.glob("*.pt")]
        self.assertIn("doof_v01.pt", ckpts)

        code, ev = _http(self.base, "POST", "/api/models/promote_with_eval",
                         {"checkpoint_name": "doof_v01.pt"}, timeout=300)
        print("[e2e] eval gate:", json.dumps(ev)[:300])
        # Verify eval ran against real checkpoint (not a path error)
        evaluation = ev.get("evaluation", {})
        self.assertIn(evaluation.get("status"), ("ok", "no_validation_data"),
                      f"eval should run, got: {ev}")
        self.assertIn("perplexity", evaluation,
                      "eval should return perplexity when validation data exists")
        code, prom = _http(self.base, "POST", "/api/models/promote",
                           {"checkpoint_name": "doof_v01.pt", "label": "friends-test-1"})
        self.assertEqual(code, 200)
        self.assertTrue(prom.get("ok"))

        _, manifest = self._get("/api/models/manifest")
        prod = next((v for v in manifest.get("versions", [])
                     if v.get("status") == "production"), None)
        self.assertIsNotNone(prod, manifest)
        # Manifest must expose sha256 and download_url for client sync
        self.assertIn("sha256", prod, "manifest version entry missing sha256")
        self.assertIn("download_url", prod, "manifest version entry missing download_url")
        self.assertEqual(prod.get("model_id"), "doof-base")

    def test_03_client_b_download_verify_load_generate(self):
        # Start server serving doof_v01.pt checkpoint
        ckpt_bytes = (self.ckpt_a / "doof_v01.pt").read_bytes()
        expected_sha = __import__("hashlib").sha256(ckpt_bytes).hexdigest()

        handler_cls = functools.partial(
            type("H", (http.server.BaseHTTPRequestHandler,), {
                "payload": ckpt_bytes,
                "do_GET": lambda s: (
                    s.send_response(200),
                    s.send_header("Content-Length", str(len(s.payload))),
                    s.end_headers(),
                    s.wfile.write(s.payload),
                ),
                "log_message": lambda *a: None,
            }),
        )
        srv = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            # Client B discovers + downloads + verifies + stages the model
            code, sync = _http(self.base, "POST", "/api/models/sync",
                               {"model_id": "doof-base", "version": "9.9.9-e2e",
                                "download_url": f"http://127.0.0.1:{port}/ckpt.pt",
                                "sha256": expected_sha}, timeout=180)
            self.assertEqual(code, 200)
            self.assertTrue(sync.get("ok"), sync)

            # Model load + real neural generation on this client
            code, loaded = _http(self.base, "POST", "/api/model/load",
                                 {"checkpoint": str(self.ckpt_a / "doof_v01.pt")}, timeout=120)
            if code != 200:
                raise AssertionError(f"model/load {code}: {json.dumps(loaded)[:400]}")
            self.assertTrue(loaded.get("ok"), loaded)

            code, gen = _http(self.base, "POST", "/api/generate",
                              {"prompt": "What does Elias drive?", "max_new_tokens": 24}, timeout=120)
            self.assertEqual(code, 200)
            # Tiny test model occasionally emits an empty continuation and DOOF
            # honestly falls back — retry a few times before failing.
            for attempt in range(5):
                if gen.get("actual_generation") and str(gen.get("text", "")).strip():
                    break
                time.sleep(1)
                code, gen = _http(self.base, "POST", "/api/generate",
                                  {"prompt": f"What does Elias drive? ({attempt})",
                                   "max_new_tokens": 24}, timeout=120)
                self.assertEqual(code, 200)
            self.assertTrue(gen.get("actual_generation"), gen)
            self.assertGreater(len(str(gen.get("text", ""))), 0)
        finally:
            srv.shutdown()

    def test_04_persistence_across_restart(self):
        # Restart the server for real; memory + training data must survive.
        cls = type(self)
        old = cls.proc
        old.terminate()
        old.wait(timeout=15)
        cls.proc, cls.base = cls._spawn(cls.data_a, cls.ckpt_a)

        _, resp = self._get("/api/memory")
        blob = json.dumps(resp)
        self.assertIn("Honda Civic", blob, "memory lost across restart")

        _, resp2 = self._get("/api/approved_examples")
        blob2 = json.dumps(resp2)
        self.assertIn("Honda Civic", blob2, "training data lost across restart")
