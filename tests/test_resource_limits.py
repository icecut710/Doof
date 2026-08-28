"""Backend enforcement of resource presets — hard clamps, no UI-only limits."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp(prefix="doof_pool_")
os.environ["DOOF_DATA_DIR"] = _tmp

from doof.compute import pool  # noqa: E402


class TestPresetClamps(unittest.TestCase):
    def test_hard_clamps(self):
        s = pool.save_settings({"max_cpu_pct": 100, "max_gpu_pct": 200,
                                "max_jobs": 50, "max_vram_gb": -5})
        self.assertLessEqual(s["max_cpu_pct"], 95)
        self.assertLessEqual(s["max_gpu_pct"], 95)
        self.assertLessEqual(s["max_jobs"], 4)
        self.assertEqual(s["max_vram_gb"], None)

    def test_blunt_still_capped(self):
        s = pool.save_settings({"preset": "hit_moms_blunt", "max_jobs": 3,
                                "allow_train": True, "idle_only": False})
        self.assertEqual(s["max_jobs"], 3)
        self.assertLessEqual(s["max_cpu_pct"], 95, "Blunt removed CPU cap")
        self.assertLessEqual(s["max_gpu_pct"], 95, "Blunt removed GPU cap")

    def test_light_blocks_train_and_reads_clamped(self):
        pool.save_settings({"allow_train": False, "idle_only": True})
        s = pool._settings()
        self.assertFalse(s.get("allow_train"))
        self.assertFalse(pool.node_eligible_for_job("train"))

    def test_corrupt_file_cannot_unlock_unlimited(self):
        from doof.paths import user_data_dir
        p = user_data_dir() / "compute_settings.json"
        p.write_text('{"max_cpu_pct": 1000, "max_jobs": 999}', encoding="utf-8")
        s = pool._settings()
        self.assertLessEqual(s["max_cpu_pct"], 95)
        self.assertLessEqual(s["max_jobs"], 4)


if __name__ == "__main__":
    unittest.main()
