"""Model registry and checksum helpers."""
from __future__ import annotations

import unittest
from pathlib import Path


class ModelManagerTests(unittest.TestCase):
    def test_list_registry_has_doof_base(self):
        from doof.models import list_registry

        models = list_registry()
        ids = {m.model_id for m in models}
        self.assertIn("doof-base", ids)

    def test_cache_dir_exists(self):
        from doof.models import cache_dir

        d = cache_dir()
        self.assertTrue(d.exists())

    def test_verify_missing_false(self):
        from doof.models import verify_checksum

        self.assertFalse(verify_checksum(Path("/nonexistent/file.pt"), "abc"))


if __name__ == "__main__":
    unittest.main()
