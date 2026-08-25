"""Torch must not be pre-stubbed into a circular init state."""
from __future__ import annotations

import sys
import types
import unittest


class TorchInitSafetyTests(unittest.TestCase):
    def test_rthook_does_not_seed_torch_distributed(self):
        # Simulate what the runtime hook is allowed to do
        if "torch.distributed" in sys.modules:
            # May exist if real torch imported in this process — skip strictness
            mod = sys.modules["torch.distributed"]
            if getattr(mod, "__file__", None):
                return
        # Ensure our package code does not leave an empty stub before import
        from pathlib import Path

        hook = Path(__file__).resolve().parents[1] / "packaging" / "rthooks" / "pyi_rth_doof_torch.py"
        text = hook.read_text(encoding="utf-8")
        code_lines = [
            ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        ]
        code = "\n".join(code_lines)
        self.assertNotIn('sys.modules["torch.distributed"]', code)
        self.assertNotIn("sys.modules['torch.distributed']", code)
        self.assertIn("torchdistribute", code)

    def test_runtime_soft_patch_only_after(self):
        from doof import runtime as rt

        src = Path_src = __import__("inspect").getsource(rt._soft_patch_distributed)
        self.assertIn("is_available", src)

    def test_device_preference_roundtrip(self):
        from doof.runtime import get_device_preference, set_device_preference

        prev = get_device_preference()
        try:
            self.assertEqual(set_device_preference("cpu"), "cpu")
            self.assertEqual(get_device_preference(), "cpu")
            self.assertEqual(set_device_preference("auto"), "auto")
        finally:
            set_device_preference(prev)


if __name__ == "__main__":
    unittest.main()
