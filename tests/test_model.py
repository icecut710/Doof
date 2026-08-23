import unittest
import torch
from doof.model import DOOFTransformer

class TestModel(unittest.TestCase):
    def test_forward(self):
        m = DOOFTransformer(vocab_size=259, max_seq_len=32, d_model=64, n_heads=4, n_layers=2)
        x = torch.randint(0, 259, (2, 16))
        y = m(x)
        self.assertEqual(y.shape, (2, 16, 259))

    def test_param_count_default(self):
        m = DOOFTransformer()
        n = sum(p.numel() for p in m.parameters())
        self.assertGreater(n, 1_000_000)

if __name__ == "__main__":
    unittest.main()
