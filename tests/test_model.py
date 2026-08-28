import unittest
import torch
from doof.model import DOOFTransformer
from doof.model.transformer import RotaryEmbedding


class TestModel(unittest.TestCase):
    def test_forward_legacy_vocab(self):
        m = DOOFTransformer(vocab_size=259, max_seq_len=32, d_model=64, n_heads=4, n_layers=2)
        x = torch.randint(0, 259, (2, 16))
        y = m(x)
        self.assertEqual(y.shape, (2, 16, 259))

    def test_forward_default_vocab(self):
        m = DOOFTransformer(max_seq_len=32, d_model=64, n_heads=4, n_layers=2)
        x = torch.randint(0, 1024, (2, 16))
        y = m(x)
        self.assertEqual(y.shape, (2, 16, 1024))

    def test_param_count_default(self):
        m = DOOFTransformer()
        n = sum(p.numel() for p in m.parameters())
        self.assertGreater(n, 1_000_000)

    def test_rotary_cos_sin_different(self):
        """Regression: cos and sin caches must be different tensors."""
        rope = RotaryEmbedding(dim=32)
        rope._update_caches(16, torch.device("cpu"))
        self.assertIsNot(rope._cached_cos, rope._cached_sin)
        self.assertFalse(torch.allclose(rope._cached_cos, rope._cached_sin))

    def test_rotary_applies_rotation(self):
        """Regression: rotary embedding must change the input."""
        rope = RotaryEmbedding(dim=32)
        x = torch.randn(2, 16, 32)
        rotated = rope.apply_rotary(x, seq_len=16)
        self.assertEqual(rotated.shape, x.shape)
        self.assertFalse(torch.allclose(x, rotated))

    def test_rotary_cache_device_match(self):
        """Regression: cache device must match requested device exactly."""
        rope = RotaryEmbedding(dim=32)
        rope._update_caches(8, torch.device("cpu"))
        self.assertEqual(rope._cached_cos.device, torch.device("cpu"))
        # Simulate different device request
        rope._update_caches(16, torch.device("cpu"))
        self.assertEqual(rope._cached_cos.shape[0], 16)

    def test_state_dict_round_trip(self):
        """Regression: loading state_dict must produce identical outputs."""
        m = DOOFTransformer(vocab_size=1024, max_seq_len=32, d_model=64, n_heads=4, n_layers=2)
        x = torch.randint(0, 1024, (1, 8))
        m.eval()
        with torch.no_grad():
            logits1 = m(x)
        sd = m.state_dict()
        m2 = DOOFTransformer(vocab_size=1024, max_seq_len=32, d_model=64, n_heads=4, n_layers=2)
        m2.load_state_dict(sd)
        m2.eval()
        with torch.no_grad():
            logits2 = m2(x)
        self.assertTrue(torch.allclose(logits1, logits2, atol=1e-5))

    def test_model_config_in_state_dict(self):
        """Regression: model config must be recoverable from checkpoint."""
        m = DOOFTransformer(vocab_size=512, max_seq_len=64, d_model=128, n_heads=4, n_layers=3)
        config = {
            "vocab_size": m.vocab_size,
            "max_seq_len": m.max_seq_len,
            "d_model": m.d_model,
            "n_heads": m.n_heads,
            "n_layers": m.n_layers,
        }
        m2 = DOOFTransformer(**{k: v for k, v in config.items()})
        self.assertEqual(m2.vocab_size, 512)
        self.assertEqual(m2.d_model, 128)
        self.assertEqual(m2.n_heads, 4)
        self.assertEqual(m2.n_layers, 3)


if __name__ == "__main__":
    unittest.main()
