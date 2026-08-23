import unittest
from doof.tokenizer import DOOFTokenizer

class TestTokenizer(unittest.TestCase):
    def setUp(self):
        self.tok = DOOFTokenizer()

    def test_vocab_size(self):
        self.assertEqual(self.tok.vocab_size, 259)

    def test_roundtrip(self):
        text = "DOOF loves computers."
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertIn("DOOF", out)
        self.assertIn("computers", out)

    def test_bos_eos(self):
        ids = self.tok.encode("hi", add_bos=True, add_eos=True)
        self.assertEqual(ids[0], self.tok.BOS)
        self.assertEqual(ids[-1], self.tok.EOS)

    def test_no_bos(self):
        ids = self.tok.encode("hi", add_bos=False, add_eos=False)
        self.assertNotIn(self.tok.BOS, ids)
        self.assertNotIn(self.tok.EOS, ids)

if __name__ == "__main__":
    unittest.main()
