from __future__ import annotations

from pathlib import Path


class DOOFTokenizer:
    """Simple byte-level tokenizer for the first DOOF prototype."""

    PAD = 256
    BOS = 257
    EOS = 258
    VOCAB_SIZE = 259

    def encode(
        self,
        text: str,
        *,
        add_bos: bool = True,
        add_eos: bool = True,
    ) -> list[int]:
        tokens: list[int] = []

        if add_bos:
            tokens.append(self.BOS)

        tokens.extend(text.encode("utf-8"))

        if add_eos:
            tokens.append(self.EOS)

        return tokens

    def decode(self, tokens: list[int]) -> str:
        data = bytes(token for token in tokens if 0 <= token <= 255)
        return data.decode("utf-8", errors="replace")

    def encode_file(self, path: str | Path) -> list[int]:
        text = Path(path).read_text(encoding="utf-8")
        return self.encode(text)

    @property
    def vocab_size(self) -> int:
        return self.VOCAB_SIZE