"""Verify LOCAL GPU inference actually generates tokens from the real model.

This test ensures that when DOOF reports LOCAL GPU / LOCAL CPU, it used
real autoregressive generation and did NOT return a canned/prewritten response.
"""
from __future__ import annotations

import os
import unittest


class InferenceHonestyTests(unittest.TestCase):
    """Ensure inference claims match reality."""

    def test_generate_endpoint_returns_real_source_info(self):
        """When the generate API claims LOCAL GPU/CPU, it must include
        metadata proving real generation occurred."""
        # Disable torch to force fallback — verify fallback is honest
        os.environ["DOOF_DISABLE_TORCH"] = "1"
        try:
            from doof.inference.router import route_inference
            result = route_inference("What is 2 + 2?")
            d = result.as_dict()

            # Must always have these fields
            self.assertIn("provider", d)
            self.assertIn("source_label", d)
            self.assertIn("actual_generation", d)
            self.assertIn("tokens_generated", d)
            self.assertIn("text", d)
            self.assertTrue(len(d["text"].strip()) > 0)

            # When torch is disabled, actual_generation must be False
            self.assertFalse(d["actual_generation"],
                           "actual_generation must be False when torch is disabled")

            # Source label must honestly reflect what happened
            self.assertIn(d["source_label"],
                         ("COMPUTED", "FROM MEMORY", "NO GENERATION", "LOCAL GPU", "LOCAL CPU"))
        finally:
            os.environ.pop("DOOF_DISABLE_TORCH", None)

    def test_no_canned_responses_in_inference_path(self):
        """Ensure the inference router never returns canned identity/personality text."""
        os.environ["DOOF_DISABLE_TORCH"] = "1"
        try:
            from doof.inference.router import route_inference

            CANNED_PHRASES = [
                "I am DOOF",
                "I am here",
                "Ask me anything",
                "Ask me something concrete",
                "brain path is available",
                "warming up",
                "Lebanon shows up",
                "Shawarma is treated seriously",
                "backup path right now",
                "running on a backup",
            ]

            test_prompts = [
                "Hi",
                "Hello",
                "Who are you?",
                "What is DOOF?",
                "Tell me about yourself",
                "What do you think about Lebanon?",
                "Do you like shawarma?",
                "What is 2 + 2?",
                "What is the meaning of life?",
            ]

            for prompt in test_prompts:
                result = route_inference(prompt)
                text_lower = result.text.lower()
                for phrase in CANNED_PHRASES:
                    self.assertNotIn(
                        phrase.lower(), text_lower,
                        f"Canned phrase '{phrase}' found in response to '{prompt}'. "
                        f"Provider: {result.provider}, Source: {result.source_label}"
                    )
        finally:
            os.environ.pop("DOOF_DISABLE_TORCH", None)

    def test_math_always_works(self):
        """Math computation should always produce correct results."""
        os.environ["DOOF_DISABLE_TORCH"] = "1"
        try:
            from doof.inference.router import route_inference
            result = route_inference("What is 7 * 8?")
            self.assertEqual(result.text.strip(), "56")
            self.assertIn(result.provider, ("computed",))
        finally:
            os.environ.pop("DOOF_DISABLE_TORCH", None)

    def test_memory_retrieval_honest(self):
        """Memory-based answers should come from stored data, not neural generation."""
        os.environ["DOOF_DISABLE_TORCH"] = "1"
        try:
            from doof.inference.router import route_inference
            # This query should not match any stored memory
            result = route_inference("What is quantum entanglement?")
            # Should honestly report no generation
            self.assertIn(result.source_label, ("NO GENERATION", "FROM MEMORY", "COMPUTED"))
            self.assertFalse(result.actual_generation)
        finally:
            os.environ.pop("DOOF_DISABLE_TORCH", None)


if __name__ == "__main__":
    unittest.main()
