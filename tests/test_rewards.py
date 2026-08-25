"""Internal Naddaf reward ledger tests — never claim on-chain."""
from __future__ import annotations

import uuid
import unittest

from doof import rewards


class RewardLedgerTests(unittest.TestCase):
    def test_duplicate_job_not_rewarded_twice(self):
        jid = f"job-{uuid.uuid4()}"
        e1 = rewards.record_job_reward(
            user_id="u1",
            node_id="n1",
            job_id=jid,
            job_type="inference",
            device="cpu",
            verified=True,
        )
        self.assertIsNotNone(e1)
        e2 = rewards.record_job_reward(
            user_id="u1",
            node_id="n1",
            job_id=jid,
            job_type="inference",
            device="cpu",
            verified=True,
        )
        self.assertIsNone(e2)

    def test_unverified_rejected(self):
        e = rewards.record_job_reward(
            user_id="u1",
            node_id="n1",
            job_id=f"job-{uuid.uuid4()}",
            job_type="inference",
            verified=False,
        )
        self.assertIsNone(e)

    def test_balances_structure(self):
        b = rewards.balances("u1")
        self.assertIn("pending", b)
        self.assertIn("approved", b)
        self.assertIn("paid", b)
        self.assertFalse(b.get("on_chain_payouts_enabled"))
        self.assertIn("internal", (b.get("disclaimer") or "").lower())

    def test_payouts_honest(self):
        p = rewards.payouts_status()
        self.assertFalse(p["enabled"])
        self.assertIn("not enabled", p["label"].lower())


class MemoryRefusalRegression(unittest.TestCase):
    def test_api_source_has_no_universal_refusal(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "doof" / "api.py"
        text = src.read_text(encoding="utf-8")
        self.assertNotIn("I do not have that in memory yet. Add it in Memory, then train", text)

    def test_lightweight_not_memory_gate(self):
        from doof.brain import lightweight_answer
        a = lightweight_answer("What is 7 times 8?")
        self.assertEqual(a.strip(), "56")
        b = lightweight_answer("Who are you?")
        self.assertIn("DOOF", b)
        self.assertNotIn("Add it in Memory, then train", b)


if __name__ == "__main__":
    unittest.main()
