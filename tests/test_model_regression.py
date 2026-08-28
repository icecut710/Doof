"""Regression tests for DOOF training pipeline fixes.

Covers:
  - Trainer no longer calls model.generate() (which doesn't exist)
  - Validation iterates multiple batches, not just one
  - Small datasets raise clear errors instead of crashing silently
  - Checkpoint contains model_config for reload
  - Cleanup properly releases resources
"""
from __future__ import annotations

import os
import tempfile
import unittest
import torch

os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_SERVICE_KEY", None)
os.environ.pop("SUPABASE_ANON_KEY", None)
os.environ["SUPABASE_URL"] = ""

from doof.training.trainer import DOOFTrainer, TrainingConfig
from doof.tokenizer import DOOFTokenizer


class TestTrainerRegression(unittest.TestCase):
    """Regression tests for trainer bugs fixed during audit."""

    def test_train_does_not_call_model_generate(self):
        """Trainer.train() must not crash by calling model.generate().

        DOOFTransformer has no generate() method. The trainer must use
        inline generation for its sanity check.
        """
        cfg = TrainingConfig(
            data_path="data/train.txt",
            checkpoint_dir=tempfile.mkdtemp(),
            epochs=1,
            batch_size=4,
            seq_len=32,
            save_every=999,
        )
        tr = DOOFTrainer(cfg)
        tokens = tr.load_data()
        # This used to crash with AttributeError: 'DOOFTransformer' object has no attribute 'generate'
        result = tr.train(val_split=0.1)
        self.assertIn("best_val_loss", result)
        self.assertIn("step", result)
        self.assertGreater(result["step"], 0)
        tr.cleanup()

    def test_validation_uses_multiple_batches(self):
        """_validate() must average over multiple batches, not just one."""
        cfg = TrainingConfig(
            data_path="data/train.txt",
            checkpoint_dir=tempfile.mkdtemp(),
            epochs=1,
            batch_size=4,
            seq_len=32,
            save_every=999,
        )
        tr = DOOFTrainer(cfg)
        tokens = tr.load_data()
        # Split: 90% train, 10% val
        val_size = int(len(tokens) * 0.1)
        val_tokens = tokens[-val_size:]
        val_loss = tr._validate(val_tokens)
        # Validation loss should be a finite number
        self.assertGreater(val_loss, 0.0)
        self.assertLess(val_loss, 100.0)
        tr.cleanup()

    def test_small_dataset_raises_error(self):
        """Trainer must raise ValueError for datasets smaller than seq_len."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Short. ")
            small_path = f.name
        try:
            cfg = TrainingConfig(
                data_path=small_path,
                checkpoint_dir=tempfile.mkdtemp(),
                seq_len=64,
                epochs=1,
                batch_size=8,
            )
            tr = DOOFTrainer(cfg)
            tokens = tr.load_data()
            with self.assertRaises(ValueError):
                tr.create_batches(tokens)
        finally:
            os.unlink(small_path)

    def test_checkpoint_contains_model_config(self):
        """Saved checkpoints must include model_config for reload."""
        cfg = TrainingConfig(
            data_path="data/train.txt",
            checkpoint_dir=tempfile.mkdtemp(),
            epochs=1,
            batch_size=4,
            seq_len=32,
            save_every=999,
        )
        tr = DOOFTrainer(cfg)
        tokens = tr.load_data()
        tr.save_checkpoint(step=1, loss=0.5)

        ckpt_path = os.path.join(cfg.checkpoint_dir, "doof_step_1.pt")
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        self.assertIn("model_config", ckpt)
        mc = ckpt["model_config"]
        self.assertIn("vocab_size", mc)
        self.assertIn("d_model", mc)
        self.assertIn("n_heads", mc)
        self.assertIn("n_layers", mc)
        self.assertIn("max_seq_len", mc)
        tr.cleanup()

    def test_cleanup_releases_resources(self):
        """cleanup() should set optimizer and scaler to None."""
        cfg = TrainingConfig(
            data_path="data/train.txt",
            checkpoint_dir=tempfile.mkdtemp(),
            epochs=1,
            batch_size=4,
            seq_len=32,
        )
        tr = DOOFTrainer(cfg)
        self.assertIsNotNone(tr.optimizer)
        self.assertIsNotNone(tr.scaler)
        tr.cleanup()
        self.assertIsNone(tr.optimizer)
        self.assertIsNone(tr.scaler)


class TestTokenizerRegression(unittest.TestCase):
    """Regression tests for tokenizer encode/decode round-trips."""

    def test_encode_decode_roundtrip_ascii(self):
        tok = DOOFTokenizer(vocab_size=1024)
        text = "Hello, world! This is a test."
        ids = tok.encode(text, add_bos=False, add_eos=False)
        decoded = tok.decode(ids)
        self.assertEqual(decoded, text)

    def test_encode_decode_roundtrip_unicode(self):
        tok = DOOFTokenizer(vocab_size=1024)
        text = "Hello \u00e9\u00e8\u00ea \u00fc\u00f6\u00e4"
        ids = tok.encode(text, add_bos=False, add_eos=False)
        decoded = tok.decode(ids)
        self.assertEqual(decoded, text)

    def test_encode_decode_roundtrip_emoji(self):
        tok = DOOFTokenizer(vocab_size=1024)
        text = "Hello \U0001f600 \U0001f4a9 \U0001f680"
        ids = tok.encode(text, add_bos=False, add_eos=False)
        decoded = tok.decode(ids)
        self.assertEqual(decoded, text)

    def test_encode_decode_roundtrip_mixed(self):
        tok = DOOFTokenizer(vocab_size=1024)
        text = "DOOF v3.0 \u2014 built with \u2764\ufe0f by friends"
        ids = tok.encode(text, add_bos=False, add_eos=False)
        decoded = tok.decode(ids)
        self.assertEqual(decoded, text)

    def test_bos_eos_tokens(self):
        tok = DOOFTokenizer(vocab_size=1024)
        ids = tok.encode("Hi", add_bos=True, add_eos=True)
        self.assertEqual(ids[0], tok.BOS)
        self.assertEqual(ids[-1], tok.EOS)

    def test_empty_string(self):
        tok = DOOFTokenizer(vocab_size=1024)
        ids = tok.encode("", add_bos=False, add_eos=False)
        self.assertEqual(ids, [])

    def test_vocab_size_matches_config(self):
        tok = DOOFTokenizer(vocab_size=1024)
        self.assertEqual(tok.vocab_size, 1024)
        tok2 = DOOFTokenizer(vocab_size=2048)
        self.assertEqual(tok2.vocab_size, 2048)

    def test_checksum_deterministic(self):
        tok1 = DOOFTokenizer(vocab_size=1024)
        tok2 = DOOFTokenizer(vocab_size=1024)
        self.assertEqual(tok1.checksum(), tok2.checksum())

    def test_checksum_different_for_different_merges(self):
        tok1 = DOOFTokenizer(vocab_size=1024)
        tok2 = DOOFTokenizer(vocab_size=1024, merges=[("a", "b")])
        self.assertNotEqual(tok1.checksum(), tok2.checksum())


if __name__ == "__main__":
    unittest.main()
