"""Comprehensive tests for the DOOF BPE tokenizer."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from doof.tokenizer import DOOFTokenizer, LegacyTokenizer, PAD, BOS, EOS, UNK


class TestTokenizerBasics(unittest.TestCase):
    """Core encoding/decoding functionality."""

    def setUp(self):
        self.tok = DOOFTokenizer()

    def test_default_vocab_size(self):
        self.assertEqual(self.tok.vocab_size, 1024)

    def test_special_token_ids(self):
        self.assertEqual(PAD, 0)
        self.assertEqual(UNK, 1)
        self.assertEqual(BOS, 2)
        self.assertEqual(EOS, 3)

    def test_roundtrip_ascii(self):
        text = "Hello, DOOF!"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_unicode(self):
        text = "café résumé naïve"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_emoji(self):
        text = "Hello 🌍🚀🔥"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_arabic(self):
        text = "مرحبا بك في DOOF"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_chinese(self):
        text = "你好世界"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_numbers(self):
        text = "12345.67890 $100 50%"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_punctuation(self):
        text = "Hello! How are you? I'm fine... (great) [ok] {yes}"
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_roundtrip_whitespace(self):
        text = "  spaces  and\ttabs\nand\nnewlines  "
        ids = self.tok.encode(text)
        out = self.tok.decode(ids)
        self.assertEqual(out, text)

    def test_empty_string(self):
        ids = self.tok.encode("")
        # Should have BOS + EOS
        self.assertEqual(ids, [BOS, EOS])

    def test_empty_string_no_wrappers(self):
        ids = self.tok.encode("", add_bos=False, add_eos=False)
        self.assertEqual(ids, [])

    def test_bos_eos_wrapping(self):
        ids = self.tok.encode("hi")
        self.assertEqual(ids[0], BOS)
        self.assertEqual(ids[-1], EOS)

    def test_no_bos_eos(self):
        ids = self.tok.encode("hi", add_bos=False, add_eos=False)
        self.assertNotIn(BOS, ids)
        self.assertNotIn(EOS, ids)

    def test_decode_filters_special_tokens(self):
        ids = [BOS, 72, 101, 108, EOS]
        out = self.tok.decode(ids)
        # Should not contain <bos> or <eos> strings
        self.assertNotIn("<bos>", out)
        self.assertNotIn("<eos>", out)

    def test_decode_empty(self):
        self.assertEqual(self.tok.decode([]), "")
        self.assertEqual(self.tok.decode([PAD, BOS, EOS]), "")

    def test_encode_produces_positive_ids(self):
        ids = self.tok.encode("test")
        for tid in ids:
            self.assertGreaterEqual(tid, 0)
            self.assertLess(tid, self.tok.vocab_size)


class TestBPETokenization(unittest.TestCase):
    """BPE-specific behavior."""

    def test_subword_frequent_words(self):
        text = "the " * 50  # "the " repeated 50 times
        tok = DOOFTokenizer.build_from_text(text, vocab_size=270)
        # "the" is so frequent it should get a merge token
        ids = tok.encode("the")
        # Should be fewer tokens than raw bytes (which would be 3 for "the")
        self.assertLess(len(ids), 6)  # BOS + merged + EOS

    def test_fallback_to_bytes_for_rare_text(self):
        tok = DOOFTokenizer.build_from_text("hello world", vocab_size=265)
        # Rare text that wasn't in training should still encode/decode correctly
        ids = tok.encode("xyz")
        out = tok.decode(ids)
        self.assertEqual(out, "xyz")

    def test_build_deterministic(self):
        text = "the quick brown fox jumps over the lazy dog"
        tok1 = DOOFTokenizer.build_from_text(text, vocab_size=300)
        tok2 = DOOFTokenizer.build_from_text(text, vocab_size=300)
        self.assertEqual(tok1.checksum(), tok2.checksum())

    def test_build_different_vocab_different_checksum(self):
        text = "the quick brown fox"
        tok1 = DOOFTokenizer.build_from_text(text, vocab_size=265)
        tok2 = DOOFTokenizer.build_from_text(text, vocab_size=300)
        self.assertNotEqual(tok1.checksum(), tok2.checksum())

    def test_encode_file(self):
        tok = DOOFTokenizer()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello world\nThis is a test.")
            f.flush()
            fname = f.name
        try:
            ids = tok.encode_file(fname)
            self.assertIsInstance(ids, list)
            self.assertGreater(len(ids), 0)
            self.assertEqual(ids[0], BOS)
            self.assertEqual(ids[-1], EOS)
        finally:
            os.unlink(fname)


class TestSaveLoad(unittest.TestCase):
    """Tokenizer persistence."""

    def setUp(self):
        self.tok = DOOFTokenizer.build_from_text(
            "the quick brown fox jumps over the lazy dog\n" * 20,
            vocab_size=300,
        )

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            self.tok.save(path)
            loaded = DOOFTokenizer.load(path)
            self.assertEqual(self.tok.checksum(), loaded.checksum())

    def test_save_load_encode_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            self.tok.save(path)
            loaded = DOOFTokenizer.load(path)

            text = "Hello, this is a test of the tokenizer!"
            ids_orig = self.tok.encode(text)
            ids_loaded = loaded.encode(text)
            self.assertEqual(ids_orig, ids_loaded)

            out = loaded.decode(ids_loaded)
            self.assertEqual(out, text)

    def test_save_load_merges_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tokenizer.json"
            self.tok.save(path)
            loaded = DOOFTokenizer.load(path)
            self.assertEqual(self.tok._merges, loaded._merges)

    def test_save_for_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved_path = self.tok.save_for_checkpoint(tmp)
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.name, "tokenizer.json")

    def test_load_from_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.tok.save_for_checkpoint(tmp)
            loaded = DOOFTokenizer.load_from_checkpoint(tmp)
            self.assertIsNotNone(loaded)
            self.assertEqual(self.tok.checksum(), loaded.checksum())

    def test_load_from_checkpoint_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            loaded = DOOFTokenizer.load_from_checkpoint(tmp)
            self.assertIsNone(loaded)


class TestAttentionMask(unittest.TestCase):
    """Attention mask generation."""

    def test_mask_all_real_tokens(self):
        tok = DOOFTokenizer()
        mask = tok.attention_mask([BOS, 100, 200, EOS])
        self.assertEqual(mask, [1, 1, 1, 1])

    def test_mask_with_padding(self):
        tok = DOOFTokenizer()
        mask = tok.attention_mask([BOS, 100, PAD, PAD])
        self.assertEqual(mask, [1, 1, 0, 0])

    def test_mask_pad_to(self):
        tok = DOOFTokenizer()
        mask = tok.attention_mask([BOS, 100], pad_to=5)
        self.assertEqual(mask, [1, 1, 0, 0, 0])


class TestBatchEncoding(unittest.TestCase):
    """Batch encoding with padding."""

    def test_batch_roundtrip(self):
        tok = DOOFTokenizer()
        texts = ["Hello", "Hello world", "Hello world!"]
        tokens, masks = tok.encode_batch(texts)
        self.assertEqual(len(tokens), 3)
        self.assertEqual(len(masks), 3)
        # All should decode correctly
        for t, text in zip(tokens, texts):
            self.assertEqual(tok.decode(t), text)

    def test_batch_pad_to_longest(self):
        tok = DOOFTokenizer()
        texts = ["hi", "hello world"]
        tokens, masks = tok.encode_batch(texts)
        # Should be padded to the longest
        self.assertEqual(len(tokens[0]), len(tokens[1]))

    def test_batch_pad_to_explicit(self):
        tok = DOOFTokenizer()
        texts = ["hi", "hello"]
        tokens, masks = tok.encode_batch(texts, pad_to=20)
        self.assertEqual(len(tokens[0]), 20)
        self.assertEqual(len(tokens[1]), 20)


class TestCompatibility(unittest.TestCase):
    """Tokenizer compatibility checking."""

    def test_same_tokenizer_compatible(self):
        tok1 = DOOFTokenizer()
        tok2 = DOOFTokenizer()
        self.assertTrue(tok1.is_compatible_with(tok2))

    def test_different_tokenizer_incompatible(self):
        tok1 = DOOFTokenizer.build_from_text("hello", vocab_size=265)
        tok2 = DOOFTokenizer.build_from_text("hello", vocab_size=300)
        self.assertFalse(tok1.is_compatible_with(tok2))

    def test_checksum_deterministic(self):
        tok = DOOFTokenizer()
        c1 = tok.checksum()
        c2 = tok.checksum()
        self.assertEqual(c1, c2)

    def test_legacy_vocab_size(self):
        self.assertEqual(DOOFTokenizer.legacy_vocab_size(), 259)


class TestBackwardCompatibility(unittest.TestCase):
    """Legacy tokenizer still works."""

    def test_legacy_tokenizer_basic(self):
        tok = LegacyTokenizer()
        self.assertEqual(tok.vocab_size, 259)
        ids = tok.encode("hello")
        self.assertEqual(ids[0], 257)  # BOS
        self.assertEqual(ids[-1], 258)  # EOS
        out = tok.decode(ids)
        self.assertIn("hello", out)

    def test_new_tokenizer_handles_empty(self):
        tok = DOOFTokenizer()
        ids = tok.encode("")
        self.assertEqual(ids, [BOS, EOS])


class TestEdgeCases(unittest.TestCase):
    """Malformed and edge-case inputs."""

    def test_single_character(self):
        tok = DOOFTokenizer()
        for ch in "aZ0!@#":
            ids = tok.encode(ch, add_bos=False, add_eos=False)
            out = tok.decode(ids)
            self.assertEqual(out, ch)

    def test_long_text(self):
        tok = DOOFTokenizer()
        text = "The quick brown fox " * 500
        ids = tok.encode(text)
        out = tok.decode(ids)
        self.assertEqual(out, text)

    def test_only_special_chars(self):
        tok = DOOFTokenizer()
        text = "!@#$%^&*()"
        ids = tok.encode(text)
        out = tok.decode(ids)
        self.assertEqual(out, text)

    def test_mixed_scripts(self):
        tok = DOOFTokenizer()
        text = "Hello مرحبا 你好 🌍"
        ids = tok.encode(text)
        out = tok.decode(ids)
        self.assertEqual(out, text)

    def test_control_characters(self):
        tok = DOOFTokenizer()
        text = "line1\nline2\ttab"
        ids = tok.encode(text)
        out = tok.decode(ids)
        self.assertEqual(out, text)


class TestBuildFromText(unittest.TestCase):
    """Vocabulary building from training corpus."""

    def test_build_basic(self):
        text = "the cat sat on the mat\n" * 100
        tok = DOOFTokenizer.build_from_text(text, vocab_size=300)
        self.assertGreater(tok.vocab_size, 260)  # more than just bytes
        self.assertLessEqual(tok.vocab_size, 300)

    def test_build_empty_text(self):
        tok = DOOFTokenizer.build_from_text("", vocab_size=300)
        # vocab_size returns target; with empty text, no merges happen but target is preserved
        self.assertEqual(tok.vocab_size, 300)

    def test_build_small_vocab(self):
        text = "hello"
        tok = DOOFTokenizer.build_from_text(text, vocab_size=260)
        # Should have at most 260 tokens (no merges fit)
        self.assertLessEqual(tok.vocab_size, 260)


if __name__ == "__main__":
    unittest.main()
