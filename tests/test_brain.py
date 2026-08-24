"""Brain path must process language — not a FAQ table of user questions."""
from __future__ import annotations

import unittest

from doof.brain import lightweight_answer, postprocess_model_text, build_prompt


class BrainTests(unittest.TestCase):
    def test_not_universal_memory_refusal(self):
        text = lightweight_answer("What is 12 × 8?")
        self.assertEqual(text.strip(), "96")
        self.assertNotIn("I do not have that in memory yet", text)

    def test_identity_is_compositional(self):
        a = lightweight_answer("Tell me about yourself.")
        b = lightweight_answer("Who are you?")
        self.assertIn("DOOF", a)
        self.assertIn("DOOF", b)
        # Must not be the old universal memory refusal
        self.assertNotIn("Add it in Memory, then train", a)

    def test_memory_used_when_relevant(self):
        mem = [{"content": "User favorite food is shawarma", "id": "1"}]
        text = lightweight_answer("What is my favorite food?", mem)
        self.assertIn("shawarma", text.lower())

    def test_build_prompt_includes_user(self):
        p = build_prompt("Hello there", [])
        self.assertIn("Hello there", p)
        self.assertIn("DOOF:", p)

    def test_postprocess_keeps_good_text(self):
        good = "DOOF is a private AI that can use shared memory."
        self.assertEqual(postprocess_model_text(good, "who are you"), good)


if __name__ == "__main__":
    unittest.main()
