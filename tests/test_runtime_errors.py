"""Runtime guards: missing torch must never crash chat-shaped helpers."""
from __future__ import annotations

import os
import unittest


class RuntimeGuards(unittest.TestCase):
    def setUp(self):
        os.environ["DOOF_DISABLE_TORCH"] = "1"

    def tearDown(self):
        os.environ.pop("DOOF_DISABLE_TORCH", None)

    def test_import_torch_returns_none(self):
        import doof.runtime as rt

        rt._torch_tried = False
        rt._torch_mod = None
        self.assertIsNone(rt.import_torch())
        self.assertFalse(rt.torch_available())

    def test_hardware_without_torch(self):
        import doof.runtime as rt

        rt._torch_tried = False
        rt._hw_cache = None
        hw = rt.probe_hardware(force=True)
        self.assertEqual(hw["device"], "cpu")
        self.assertFalse(hw["cuda_available"])

    def test_torchdistribute_error_is_human(self):
        from doof.errors import public_error

        err = public_error(ModuleNotFoundError("No module named torchdistribute"))
        self.assertIn("brain", err["title"].lower())
        self.assertNotIn("Traceback", err["title"])
        self.assertNotIn("torchdistribute", err["title"].lower())

    def test_distributed_error_is_human(self):
        from doof.errors import public_error

        err = public_error(ModuleNotFoundError("No module named 'torch.distributed'"))
        self.assertEqual(err["kind"], "ai_down")

    def test_personality_stable_meaning(self):
        from doof.personality import pick

        a = pick("healthy")
        self.assertTrue(a[0])
        self.assertTrue(a[1])
        self.assertNotEqual(a[0], a[1])
