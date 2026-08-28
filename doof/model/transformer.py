from __future__ import annotations

import json
import torch
import torch.nn as nn
import torch.nn.functional as F


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_f32 = x.to(torch.float32)
        rms = x_f32.pow(2).mean(-1, keepdim=True).add(self.eps).rsqrt()
        return (x_f32 * rms).to(x.dtype) * self.weight


class RotaryEmbedding:
    def __init__(self, dim: int, max_seq_len: int = 4096, base: int = 10000):
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base
        half = dim // 2
        self.inv_freq = 1.0 / (base ** (torch.arange(0, half, dtype=torch.float32) / max(dim, 1)))
        self._cached_seq_len = 0
        self._cached_cos = None
        self._cached_sin = None

    def _update_caches(self, seq_len: int, device: torch.device | None = None):
        device = device or torch.device("cpu")
        if seq_len == self._cached_seq_len and self._cached_cos is not None:
            if self._cached_cos.device == device:
                return
        t = torch.arange(seq_len, device="cpu", dtype=torch.float32)
        half = self.inv_freq.shape[0]
        freqs = (t[:, None] * self.inv_freq[None, :]).to(device)
        self._cached_cos = torch.cos(freqs)
        self._cached_sin = torch.sin(freqs)
        self._cached_seq_len = seq_len

    def apply_rotary(self, x: torch.Tensor, seq_len: int | None = None) -> torch.Tensor:
        if seq_len is None:
            seq_len = x.shape[1]
        device = x.device
        expected_seq = x.shape[1]
        self._update_caches(expected_seq, device=device)
        cos = self._cached_cos
        sin = self._cached_sin
        # cos/sin are (seq_len, head_dim) — match x's last dim
        d = x.shape[-1]
        if cos.shape[-1] < d:
            extra = d - cos.shape[-1]
            cos = torch.cat([cos, torch.ones_like(cos[:, :1]).expand(-1, extra)], dim=-1)
            sin = torch.cat([sin, torch.zeros_like(sin[:, :1]).expand(-1, extra)], dim=-1)
        elif cos.shape[-1] > d:
            cos = cos[:, :d]
            sin = sin[:, :d]
        if x.dim() == 3:
            if x.shape[-1] % 2 != 0:
                x = torch.nn.functional.pad(x, (0, 1), mode="constant", value=0.0)
            pair_dim = x.shape[-1] // 2
            x_ = x.reshape(*x.shape[:-1], pair_dim, 2)
            x1 = x_[..., 0]
            x2 = x_[..., 1]
            cos_p = cos[..., :pair_dim]
            sin_p = sin[..., :pair_dim]
            new_x1 = x1 * cos_p - x2 * sin_p
            new_x2 = x1 * sin_p + x2 * cos_p
            x_ = torch.stack([new_x1, new_x2], dim=-1).reshape(*x.shape[:-1], -1)
            return x_
        raise ValueError("Unsupported x dims: expected 3D (B, S, D).")


def swiglu(x: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.silu(x) * x


class FeedForward(nn.Module):
    def __init__(self, d_model: int, d_ff: int | None = None, dropout: float = 0.1):
        super().__init__()
        if d_ff is None:
            d_ff = int(d_model * 4)
        self.d_model = d_model
        self.d_ff = d_ff
        self.gate_proj = nn.Linear(d_model, d_ff, bias=False)
        self.value_proj = nn.Linear(d_model, d_ff, bias=False)
        self.down_proj = nn.Linear(d_ff, d_model, bias=False)
        self.norm = RMSNorm(d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate = swiglu(self.gate_proj(x))
        value = self.value_proj(x)
        output = gate * value
        output = self.down_proj(output)
        output = self.norm(output)
        output = self.dropout(output)
        return output


class CausalSelfAttention(nn.Module):
    def __init__(self, d_model: int, n_heads: int, dropout: float = 0.1, qkv_bias: bool = False):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        assert d_model % n_heads == 0, "d_model must be divisible by n_heads"
        self.q_proj = nn.Linear(d_model, d_model, bias=qkv_bias)
        self.k_proj = nn.Linear(d_model, d_model, bias=qkv_bias)
        self.v_proj = nn.Linear(d_model, d_model, bias=qkv_bias)
        self.rope = RotaryEmbedding(dim=self.head_dim)
        self.attn_dropout = nn.Dropout(dropout)
        self.proj_dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, _ = x.shape
        q = self.q_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch_size, seq_len, self.n_heads, self.head_dim).transpose(1, 2)
        q_flat = q.reshape(-1, seq_len, self.head_dim)
        k_flat = k.reshape(-1, seq_len, self.head_dim)
        with torch.no_grad():
            q_rot = self.rope.apply_rotary(q_flat, seq_len=seq_len)
            k_rot = self.rope.apply_rotary(k_flat, seq_len=seq_len)
        q = q_rot.reshape(batch_size, self.n_heads, seq_len, self.head_dim)
        k = k_rot.reshape(batch_size, self.n_heads, seq_len, self.head_dim)
        scale = float(self.head_dim) ** -0.5
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * scale
        mask = torch.triu(torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool), diagonal=1)
        attn_scores = attn_scores.masked_fill(mask, float("-inf"))
        attn_weights = torch.softmax(attn_scores, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)
        attn_output = torch.matmul(attn_weights, v)
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        return self.proj_dropout(attn_output)


class DOOFTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int = 1024,
        max_seq_len: int = 512,
        d_model: int = 256,
        n_heads: int = 8,
        n_layers: int = 6,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.max_seq_len = max_seq_len
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.dropout = dropout
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        blocks = []
        for _ in range(n_layers):
            block = nn.Sequential(
                RMSNorm(d_model),
                CausalSelfAttention(d_model, n_heads, dropout=dropout),
                RMSNorm(d_model),
                FeedForward(d_model),
                nn.Dropout(dropout),
            )
            blocks.append(block)
        self.blocks = nn.ModuleList(blocks)
        self.norm = RMSNorm(d_model)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)
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
            raise ValueError(f"Sequence length {seq_len} exceeds maximum {self.max_seq_len}.")
        x = self.token_embedding(input_ids)
        for block in self.blocks:
            normed = block[0](x)
            attended = block[1](normed)
            x = x + attended
            normed2 = block[2](x)
            ff_output = block[3](normed2)
            x = x + ff_output
            x = block[4](x)
        x = self.norm(x)
        return self.lm_head(x)

    @property
    def checksum(self) -> str:
        data = {
            "vocab_size": self.vocab_size,
            "max_seq_len": self.max_seq_len,
            "d_model": self.d_model,
            "n_heads": self.n_heads,
            "n_layers": self.n_layers,
            "dropout": self.dropout,
        }
        raw = json.dumps(data, sort_keys=True).encode()
        return __import__("hashlib").sha256(raw).hexdigest()

    @staticmethod
    def estimate_params(vocab_size: int, d_model: int, n_heads: int, n_layers: int) -> int:
        params = vocab_size * d_model
        d_ff = int(d_model * 4)
        params += n_layers * (4 * d_model * d_model + 2 * d_model * d_ff + d_ff + 2 * d_model)
        return int(params)


LegacyDOOFTransformer = DOOFTransformer

if __name__ == "__main__":
    import sys
    m = DOOFTransformer(vocab_size=1024, max_seq_len=128, d_model=256, n_heads=8, n_layers=6)
    p = sum(p.numel() for p in m.parameters())
    print(f"DOOFTransformer params: {p:,} (expected ~5.0M)")
    m.eval()
    ids = torch.randint(0, 1024, (2, 8), dtype=torch.long)
    with torch.no_grad():
        logits = m(ids)
    print(f"Forward pass OK: logits shape {logits.shape}")