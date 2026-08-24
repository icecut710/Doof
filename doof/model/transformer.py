from __future__ import annotations

import torch
import torch.nn as nn


class DOOFTransformer(nn.Module):
    """
    Small decoder-only Transformer for the first DOOF prototype.

    This is intentionally compact so it can train comfortably
    on an RTX 5060 8GB.
    """

    def __init__(
        self,
        vocab_size: int = 259,
        max_seq_len: int = 512,
        d_model: int = 256,
        n_heads: int = 8,
        n_layers: int = 6,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.max_seq_len = max_seq_len
        self.d_model = d_model

        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Embedding(max_seq_len, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )

        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=n_layers,
            # norm_first=True disables the fast nested-tensor path anyway;
            # set it explicitly so construction doesn't warn on every load.
            enable_nested_tensor=False,
        )

        self.norm = nn.LayerNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

        # Weight tying reduces parameters and is common in language models.
        self.lm_head.weight = self.token_embedding.weight

        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module):
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)

        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len = input_ids.shape

        if seq_len > self.max_seq_len:
            raise ValueError(
                f"Sequence length {seq_len} exceeds "
                f"maximum {self.max_seq_len}."
            )

        positions = torch.arange(
            seq_len,
            device=input_ids.device,
        ).unsqueeze(0)

        x = (
            self.token_embedding(input_ids)
            + self.position_embedding(positions)
        )

        # Causal mask prevents tokens from seeing future tokens.
        causal_mask = torch.triu(
            torch.ones(
                seq_len,
                seq_len,
                device=input_ids.device,
                dtype=torch.bool,
            ),
            diagonal=1,
        )

        x = self.transformer(
            x,
            mask=causal_mask,
        )

        x = self.norm(x)

        return self.lm_head(x)