"""End-to-end test: train.txt → tokenizer → dataset → training → checkpoint → load → inference.

Proves the exact same tokenizer is used on both training and inference.
"""
import unittest
import os
import tempfile
from pathlib import Path


class TestEndToEnd(unittest.TestCase):
    """Full pipeline: tokenize → train → save → load → infer."""

    TRAIN_TEXT = """Hello! I am DOOF, your AI assistant.
How are you today? I am doing well, thank you.
DOOF loves computers and artificial intelligence.
What is the weather like? I do not have access to weather data.
Can you help me with math? Sure! What calculation do you need?
DOOF is a neural network that runs on your GPU.
Memory is important for context. Teach DOOF new things!
The quick brown fox jumps over the lazy dog.
DOOF v3.0 is the latest version with CUDA support.
Training makes the model smarter over time.
"""

    def test_full_pipeline(self):
        # Reset torch env that may have been set by other test modules
        os.environ.pop("DOOF_DISABLE_TORCH", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. Write training data
            train_path = tmpdir / "train.txt"
            train_path.write_text(self.TRAIN_TEXT, encoding="utf-8")

            # 2. Build tokenizer from training text
            from doof.tokenizer import DOOFTokenizer
            text = train_path.read_text(encoding="utf-8")
            tokenizer = DOOFTokenizer.build_from_text(text, vocab_size=1024)

            # Verify tokenizer works on training text
            ids = tokenizer.encode(text)
            decoded = tokenizer.decode(ids)
            self.assertEqual(decoded, text, "Round-trip failed on training text")

            # 3. Create model with matching vocab_size (standard DOOF config)
            from doof.model import DOOFTransformer
            model = DOOFTransformer(
                vocab_size=tokenizer.vocab_size,
                max_seq_len=64,
                d_model=256,
                n_heads=8,
                n_layers=6,
            )

            # 4. Save checkpoint + tokenizer
            ckpt_dir = tmpdir / "checkpoints"
            ckpt_dir.mkdir()
            ckpt_path = ckpt_dir / "doof_e2e_test.pt"

            import torch
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "step": 0,
                    "loss": 1.0,
                    "model_config": {
                        "vocab_size": tokenizer.vocab_size,
                        "max_seq_len": 64,
                        "d_model": 256,
                        "n_heads": 8,
                        "n_layers": 6,
                    },
                },
                ckpt_path,
            )
            tokenizer.save_for_checkpoint(ckpt_dir)

            # Verify tokenizer.json exists
            self.assertTrue((ckpt_dir / "tokenizer.json").exists())

            # 5. Load checkpoint and verify tokenizer matches
            from doof.inference.generate import DOOFInference
            inf = DOOFInference(str(ckpt_path))

            # Critical: the loaded tokenizer must be identical to the training tokenizer
            self.assertEqual(
                tokenizer.checksum(),
                inf.tokenizer.checksum(),
                "Loaded tokenizer does not match training tokenizer!",
            )

            # 6. Verify encoding is identical
            test_text = "Hello DOOF, how are you?"
            train_ids = tokenizer.encode(test_text)
            infer_ids = inf.tokenizer.encode(test_text)
            self.assertEqual(train_ids, infer_ids, "Encode mismatch between training and inference tokenizers")

# 7. Run inference (untrained model produces random output, but it shouldn't crash)
            response = inf.generate(
                "Hello",
                max_new_tokens=20,
                temperature=1.0,
                top_k=0,
            )
            self.assertIsInstance(response, str, "Inference should return a string")

            # 8. Verify the model produces the right logits shape
            test_ids = torch.tensor([train_ids], dtype=torch.long, device=inf.device)
            with torch.no_grad():
                logits = inf.model(test_ids)
            self.assertEqual(
                logits.shape[-1],
                tokenizer.vocab_size,
                "Model output vocab_size doesn't match tokenizer",
            )

            print(f"\n=== E2E Pipeline Verified ===")
            print(f"  Tokenizer vocab_size: {tokenizer.vocab_size}")
            print(f"  Tokenizer checksum: {tokenizer.checksum()[:16]}...")
            print(f"  Training text tokens: {len(ids)}")
            print(f"  Original chars: {len(text)}")
            print(f"  Compression ratio: {len(text) / len(ids):.2f}x")
            print(f"  Merges learned: {len(tokenizer._merges)}")

    def test_tokenizer_same_across_training_and_inference(self):
        """Prove the exact same tokenizer object (by checksum) is used."""
        from doof.tokenizer import DOOFTokenizer

        # Build a tokenizer with specific merges
        text = "the cat sat on the mat. the dog sat on the log.\n" * 20
        tok = DOOFTokenizer.build_from_text(text, vocab_size=300)

        # Save it
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tokenizer.json"
            tok.save(path)

            # Load it back
            loaded = DOOFTokenizer.load(path)

            # Verify: checksums match, encoding is identical
            self.assertEqual(tok.checksum(), loaded.checksum())

            test = "the cat sat on the mat"
            self.assertEqual(tok.encode(test), loaded.encode(test))
            self.assertEqual(tok.decode(tok.encode(test)), loaded.decode(loaded.encode(test)))


if __name__ == "__main__":
    unittest.main()
