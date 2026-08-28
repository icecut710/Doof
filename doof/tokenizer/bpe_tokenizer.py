"""Lightweight BPE tokenizer for DOOF.

Design goals:
- Byte-fallback BPE: any byte (0-255) is always representable.
- Uses latin-1 as the byte↔string mapping (bidirectional for all 256 byte values).
- Special tokens at the low end (PAD=0, UNK=1, BOS=2, EOS=3).
- Byte values 0-255 occupy token IDs 4-259.
- BPE merges occupy IDs 260+.
- Vocabulary size is configurable (default 1024).
- Deterministic: same corpus + settings → same merges.
- Pure Python, no external dependencies.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


TOKENIZER_VERSION = "bpe-1.0"

# Special token IDs — these are fixed and never change.
PAD = 0
UNK = 1
BOS = 2
EOS = 3

# Byte values start at offset 4.
_BYTE_OFFSET = 4
_BYTE_VOCAB = 256  # IDs 4..259


def _byte_to_str(b: int) -> str:
    """Convert a byte value (0-255) to a reversible string using latin-1."""
    return chr(b)


def _str_to_byte(s: str) -> int | None:
    """Convert a single latin-1 character back to its byte value. Returns None if not a single byte."""
    if len(s) != 1:
        return None
    code = ord(s)
    if 0 <= code <= 255:
        return code
    return None


class DOOFTokenizer:
    """Byte-level BPE tokenizer for DOOF.

    Vocabulary layout:
        0       PAD
        1       UNK
        2       BOS
        3       EOS
        4..259  Raw byte values (0x00..0xFF) via latin-1
        260+    Learned BPE merge tokens
    """

    PAD = PAD
    UNK = UNK
    BOS = BOS
    EOS = EOS

    def __init__(
        self,
        vocab_size: int = 1024,
        merges: list[tuple[str, str]] | None = None,
    ):
        self._target_vocab_size = vocab_size
        # vocab: token_id (int) → token_string (str, latin-1 encoded)
        self._vocab: dict[int, str] = {}
        # reverse: token_string → token_id
        self._vocab_rev: dict[str, int] = {}
        # ordered merge list: [(left, right), ...]
        self._merges: list[tuple[str, str]] = []
        # merge_rank: (left, right) → priority (lower = merge earlier)
        self._merge_rank: dict[tuple[str, str], int] = {}

        self._build_base_vocab()
        if merges:
            self._merges = list(merges)
            self._merge_rank = {m: i for i, m in enumerate(self._merges)}
            self._apply_merges_to_vocab()

    # ------------------------------------------------------------------
    # Base vocabulary (special tokens + byte values)
    # ------------------------------------------------------------------

    def _build_base_vocab(self) -> None:
        self._vocab = {
            PAD: "<pad>",
            UNK: "<unk>",
            BOS: "<bos>",
            EOS: "<eos>",
        }
        for b in range(_BYTE_VOCAB):
            tid = _BYTE_OFFSET + b
            self._vocab[tid] = _byte_to_str(b)
        self._vocab_rev = {v: k for k, v in self._vocab.items()}

    def _apply_merges_to_vocab(self) -> None:
        """Rebuild vocab_rev after loading merges, and assign IDs to merge tokens."""
        self._vocab_rev = {v: k for k, v in self._vocab.items()}
        next_id = _BYTE_OFFSET + _BYTE_VOCAB
        for left, right in self._merges:
            merged = left + right
            if merged not in self._vocab_rev:
                if next_id < self._target_vocab_size:
                    self._vocab[next_id] = merged
                    self._vocab_rev[merged] = next_id
                    next_id += 1

    # ------------------------------------------------------------------
    # Vocabulary properties
    # ------------------------------------------------------------------

    @property
    def vocab_size(self) -> int:
        return self._target_vocab_size

    @property
    def target_vocab_size(self) -> int:
        return self._target_vocab_size

    def get_token(self, token_id: int) -> str:
        return self._vocab.get(token_id, "<unk>")

    def get_id(self, token: str) -> int:
        return self._vocab_rev.get(token, UNK)

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def encode(
        self,
        text: str,
        *,
        add_bos: bool = True,
        add_eos: bool = True,
    ) -> list[int]:
        tokens: list[int] = []
        if add_bos:
            tokens.append(BOS)
        tokens.extend(self._encode_text(text))
        if add_eos:
            tokens.append(EOS)
        return tokens

    def _encode_text(self, text: str) -> list[int]:
        """Encode a string into token IDs using byte-fallback BPE."""
        # Convert to bytes, then to latin-1 strings for each byte
        raw = text.encode("utf-8")

        # Each byte becomes its latin-1 character representation
        symbols = [_byte_to_str(b) for b in raw]

        # Apply BPE merges
        merged = self._apply_merges(symbols)

        # Convert token strings to IDs
        return [self._vocab_rev.get(t, UNK) for t in merged]

    def _apply_merges(self, tokens: list[str]) -> list[str]:
        """Apply learned BPE merges to a token string list."""
        if not self._merges or len(tokens) < 2:
            return tokens

        working = list(tokens)

        for left, right in self._merges:
            if len(working) < 2:
                break
            new_work: list[str] = []
            i = 0
            while i < len(working):
                if (
                    i < len(working) - 1
                    and working[i] == left
                    and working[i + 1] == right
                ):
                    new_work.append(left + right)
                    i += 2
                else:
                    new_work.append(working[i])
                    i += 1
            working = new_work

        return working

    # ------------------------------------------------------------------
    # Decoding
    # ------------------------------------------------------------------

    def decode(self, tokens: list[int]) -> str:
        """Decode token IDs back to a string.

        Token strings are latin-1 encoded, so we collect raw bytes
        and decode as UTF-8 at the end.
        """
        raw_bytes = bytearray()
        for tid in tokens:
            if tid in (PAD, BOS, EOS):
                continue
            token_str = self._vocab.get(tid, "")
            if not token_str:
                continue
            # Each token string is a sequence of latin-1 characters
            # Encode to latin-1 to get the raw bytes
            try:
                raw_bytes.extend(token_str.encode("latin-1"))
            except (UnicodeDecodeError, UnicodeEncodeError):
                # Fallback: skip malformed tokens
                continue

        return raw_bytes.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # File encoding
    # ------------------------------------------------------------------

    def encode_file(self, path: str | Path) -> list[int]:
        text = Path(path).read_text(encoding="utf-8")
        return self.encode(text)

    # ------------------------------------------------------------------
    # Attention mask
    # ------------------------------------------------------------------

    def attention_mask(self, tokens: list[int], pad_to: int | None = None) -> list[int]:
        """Create an attention mask: 1 for real tokens, 0 for PAD.

        If pad_to is given, pads the mask (and tokens) to that length.
        """
        mask = [1 if t != PAD else 0 for t in tokens]
        if pad_to and len(mask) < pad_to:
            mask.extend([0] * (pad_to - len(mask)))
        return mask

    # ------------------------------------------------------------------
    # Batch encoding
    # ------------------------------------------------------------------

    def encode_batch(
        self,
        texts: list[str],
        *,
        add_bos: bool = True,
        add_eos: bool = True,
        pad_to: int | None = None,
    ) -> tuple[list[list[int]], list[list[int]]]:
        """Encode a batch of texts. Returns (token_ids, attention_masks).

        If pad_to is given, sequences are padded to that length.
        Otherwise, sequences are padded to the length of the longest.
        """
        all_tokens = [self.encode(t, add_bos=add_bos, add_eos=add_eos) for t in texts]
        max_len = pad_to or (max(len(t) for t in all_tokens) if all_tokens else 0)

        padded_tokens: list[list[int]] = []
        masks: list[list[int]] = []
        for tokens in all_tokens:
            padded = tokens + [PAD] * (max_len - len(tokens))
            mask = self.attention_mask(padded)
            padded_tokens.append(padded)
            masks.append(mask)

        return padded_tokens, masks

    # ------------------------------------------------------------------
    # Vocabulary building (BPE training)
    # ------------------------------------------------------------------

    @classmethod
    def build_from_text(
        cls,
        text: str,
        vocab_size: int = 1024,
    ) -> DOOFTokenizer:
        """Build a BPE tokenizer from training text.

        Deterministic: same text + vocab_size always produces the same merges.
        """
        tok = cls(vocab_size=vocab_size)

        # Convert text to byte sequence, then to latin-1 symbols
        raw = text.encode("utf-8")
        symbols: list[str] = [_byte_to_str(b) for b in raw]

        # We already have 256 byte tokens + 4 specials = 260 base tokens.
        max_merges = max(0, vocab_size - (_BYTE_OFFSET + _BYTE_VOCAB))

        merges: list[tuple[str, str]] = []

        for _ in range(max_merges):
            if len(symbols) < 2:
                break

            # Count all adjacent pairs
            pair_counts: Counter[tuple[str, str]] = Counter()
            for i in range(len(symbols) - 1):
                pair_counts[(symbols[i], symbols[i + 1])] += 1

            if not pair_counts:
                break

            # Pick the most frequent pair (ties broken by first occurrence)
            best_pair = max(
                pair_counts,
                key=lambda p: (
                    pair_counts[p],
                    -merges.index(p) if p in merges else -len(merges),
                ),
            )
            best_count = pair_counts[best_pair]

            if best_count < 2:
                break

            merges.append(best_pair)

            left, right = best_pair
            merged = left + right
            new_symbols: list[str] = []
            i = 0
            while i < len(symbols):
                if (
                    i < len(symbols) - 1
                    and symbols[i] == left
                    and symbols[i + 1] == right
                ):
                    new_symbols.append(merged)
                    i += 2
                else:
                    new_symbols.append(symbols[i])
                    i += 1
            symbols = new_symbols

        tok._merges = merges
        tok._merge_rank = {m: i for i, m in enumerate(merges)}
        tok._apply_merges_to_vocab()
        return tok

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Save tokenizer to a JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Encode vocab strings as latin-1 hex for JSON safety
        vocab_hex = {}
        for k, v in self._vocab.items():
            try:
                raw = v.encode("latin-1")
                vocab_hex[str(k)] = raw.hex()
            except (UnicodeEncodeError, UnicodeDecodeError):
                vocab_hex[str(k)] = v

        data = {
            "tokenizer_version": TOKENIZER_VERSION,
            "vocab_size_target": self._target_vocab_size,
            "special_tokens": {
                "PAD": PAD,
                "UNK": UNK,
                "BOS": BOS,
                "EOS": EOS,
            },
            "vocab_hex": vocab_hex,
            "merges": [list(m) for m in self._merges],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> DOOFTokenizer:
        """Load a tokenizer from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))

        vocab_size = data.get("vocab_size_target", 1024)
        merges = [tuple(m) for m in data.get("merges", [])]

        tok = cls(vocab_size=vocab_size, merges=merges)
        return tok

    def save_for_checkpoint(self, checkpoint_dir: str | Path) -> Path:
        """Save tokenizer alongside a checkpoint directory."""
        path = Path(checkpoint_dir) / "tokenizer.json"
        self.save(path)
        return path

    @classmethod
    def load_from_checkpoint(cls, checkpoint_dir: str | Path) -> DOOFTokenizer | None:
        """Try to load a tokenizer from a checkpoint directory.

        Returns None if no tokenizer.json exists.
        """
        path = Path(checkpoint_dir) / "tokenizer.json"
        if path.exists():
            return cls.load(path)
        return None

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------

    def checksum(self) -> str:
        """Return a SHA-256 hash of the tokenizer configuration.

        Two tokenizers with the same checksum produce identical encodings.
        """
        data = {
            "version": TOKENIZER_VERSION,
            "vocab_size_target": self._target_vocab_size,
            "merges": [list(m) for m in self._merges],
        }
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def is_compatible_with(self, other: DOOFTokenizer) -> bool:
        """Check if two tokenizers produce identical encodings."""
        return self.checksum() == other.checksum()

    @staticmethod
    def legacy_vocab_size() -> int:
        """Return the vocab size of the legacy byte-only tokenizer."""
        return 259
