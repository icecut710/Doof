"""Brain path must process language — not a FAQ table of user questions."""
from __future__ import annotations

import unittest

from doof.brain import memory_answer, math_answer, postprocess_model_text, build_prompt


class BrainTests(unittest.TestCase):
    def test_math_computation(self):
        text = math_answer("What is 12 × 8?")
        self.assertEqual(text.strip(), "96")

    def test_memory_used_when_relevant(self):
        mem = [{"content": "User favorite food is shawarma", "id": "1"}]
        text = memory_answer("What is my favorite food?", mem)
        self.assertIn("shawarma", text.lower())

    def test_memory_returns_empty_when_no_match(self):
        text = memory_answer("What is quantum physics?", [])
        self.assertEqual(text, "")

    def test_build_prompt_includes_user(self):
        p = build_prompt("Hello there", [])
        self.assertIn("Hello there", p)
        self.assertIn("DOOF:", p)

    def test_postprocess_keeps_good_text(self):
        good = "DOOF is a private AI that can use shared memory."
        cleaned, source = postprocess_model_text(good, "who are you")
        self.assertEqual(cleaned, good)
        self.assertEqual(source, "model")

    def test_postprocess_garbled_returns_empty(self):
        garbled = "!!!###$$$%%%" * 5
        cleaned, source = postprocess_model_text(garbled, "who are you")
        self.assertEqual(source, "empty")
        self.assertEqual(cleaned, "")

    def test_postprocess_empty_returns_empty(self):
        cleaned, source = postprocess_model_text("", "hello")
        self.assertEqual(source, "empty")
        self.assertEqual(cleaned, "")

    def test_postprocess_memory_fallback(self):
        mem = [{"content": "User prefers dark mode", "id": "m1"}]
        cleaned, source = postprocess_model_text("", "What is my favorite setting?", mem)
        self.assertEqual(source, "memory")
        self.assertIn("dark mode", cleaned.lower())


if __name__ == "__main__":
    unittest.main()
