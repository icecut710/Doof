"""Hosted brain config — no third-party by default."""
from __future__ import annotations

import os
import unittest


class HostedBrainTests(unittest.TestCase):
    def test_not_configured_by_default(self):
        os.environ.pop("DOOF_HOSTED_BRAIN_URL", None)
        from doof.cloud.hosted_brain import hosted_config, hosted_generate

        cfg = hosted_config()
        self.assertFalse(cfg["enabled"])
        self.assertIsNone(hosted_generate("hello"))


if __name__ == "__main__":
    unittest.main()
