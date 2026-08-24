"""Auth + fresh-install regression tests (local fallback mode)."""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

import doof.api as api


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.profiles = Path(api.PROFILES_PATH)
        self.sessions = Path(api.SESSIONS_PATH)
        self._backup = []
        for p in (self.profiles, self.sessions):
            if p.exists():
                self._backup.append((p, p.read_text(encoding="utf-8")))
                p.unlink()

    def tearDown(self):
        for p, content in self._backup:
            p.write_text(content, encoding="utf-8")

    # -- signup validation -------------------------------------------------

    def test_weak_password_rejected(self):
        code, payload = api.auth_signup({"email": "a@b.co", "password": "short1"})
        self.assertEqual(code, 400)

    def test_password_needs_letter_and_number(self):
        code, _ = api.auth_signup({"email": "a@b.co", "password": "onlyletters"})
        self.assertEqual(code, 400)
        code, _ = api.auth_signup({"email": "a@b.co", "password": "12345678"})
        self.assertEqual(code, 400)

    def test_invalid_email_rejected(self):
        code, _ = api.auth_signup({"email": "not-an-email", "password": "goodpass1"})
        self.assertEqual(code, 400)

    def test_first_account_is_owner_second_is_trusted(self):
        c1, p1 = api.auth_signup({"email": "owner@doof.ai", "password": "goodpass1"})
        c2, p2 = api.auth_signup({"email": "friend@doof.ai", "password": "goodpass2"})
        self.assertEqual(c1, 200)
        self.assertEqual(c2, 200)
        self.assertEqual(p1["profile"]["role"], "owner")
        self.assertEqual(p2["profile"]["role"], "trusted")

    def test_duplicate_signup_rejected(self):
        api.auth_signup({"email": "x@y.z", "password": "goodpass1"})
        code, _ = api.auth_signup({"email": "x@y.z", "password": "goodpass2"})
        self.assertEqual(code, 409)

    # -- login --------------------------------------------------------------

    def test_login_success_and_wrong_password(self):
        api.auth_signup({"email": "l@doof.ai", "password": "goodpass1"})
        code, payload = api.auth_login({"email": "l@doof.ai", "password": "goodpass1"})
        self.assertEqual(code, 200)
        self.assertIn("token", payload)
        code, _ = api.auth_login({"email": "l@doof.ai", "password": "wrongpass9"})
        self.assertEqual(code, 401)
        code, _ = api.auth_login({"email": "ghost@doof.ai", "password": "whatever1"})
        self.assertEqual(code, 401)

    def test_no_plaintext_passwords_on_disk(self):
        api.auth_signup({"email": "sec@doof.ai", "password": "supersecret99"})
        raw = self.profiles.read_text(encoding="utf-8")
        self.assertNotIn("supersecret99", raw)
        self.assertIn("password_hash", raw)

    def test_expired_session_is_invalid(self):
        _, payload = api.auth_signup({"email": "exp@doof.ai", "password": "goodpass1"})
        token = payload["token"]
        sessions = json.loads(self.sessions.read_text(encoding="utf-8"))
        sessions[0]["expires_at"] = time.time() - 10
        self.sessions.write_text(json.dumps(sessions), encoding="utf-8")
        self.assertIsNone(api._profile_from_token(token))
        # valid session still resolves
        _, payload2 = api.auth_login({"email": "exp@doof.ai", "password": "goodpass1"})
        self.assertIsNotNone(api._profile_from_token(payload2["token"]))

    def test_logout_invalidates_session(self):
        _, payload = api.auth_signup({"email": "out@doof.ai", "password": "goodpass1"})
        token = payload["token"]
        sessions = json.loads(self.sessions.read_text(encoding="utf-8"))
        self.sessions.write_text(
            json.dumps([s for s in sessions if s["token"] != token]), encoding="utf-8"
        )
        self.assertIsNone(api._profile_from_token(token))

    def test_unverified_local_profile_blocked(self):
        api.auth_signup({"email": "v@doof.ai", "password": "goodpass1"})
        profiles = json.loads(self.profiles.read_text(encoding="utf-8"))
        profiles[0]["email_verified"] = False
        self.profiles.write_text(json.dumps(profiles), encoding="utf-8")
        code, payload = api.auth_login({"email": "v@doof.ai", "password": "goodpass1"})
        self.assertEqual(code, 403)
        self.assertEqual(payload.get("code"), "email_unverified")


class FreshInstallTests(unittest.TestCase):
    """Fresh install must never surface 'No checkpoint found'."""

    def test_bootstrap_creates_valid_checkpoint(self):
        import torch

        # Isolated "fresh install": empty checkpoint dir
        import tempfile

        from doof.inference import DOOFInference

        real_dir = api.CKPT_DIR
        with tempfile.TemporaryDirectory() as tmp:
            api.CKPT_DIR = Path(tmp)
            try:
                path = api._find_ckpt()
                self.assertTrue(path.exists())
                data = torch.load(path, map_location="cpu", weights_only=False)
                self.assertIn("model_state_dict", data)
                self.assertEqual(data.get("step"), 0)
                inf = DOOFInference(str(path))
                out = inf.generate("hello", max_new_tokens=8)
                self.assertIsInstance(out, str)
            finally:
                api.CKPT_DIR = real_dir


if __name__ == "__main__":
    unittest.main()
