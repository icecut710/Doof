from __future__ import annotations

import json
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalisation.

    Stores ``self.weight`` (no bias).  Forward computes
    ``x * rms(x) * weight`` where ``rms(x) = weight * sqrt(mean(x**2))``.
    """

    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_f32 = x.to(torch.float32)
        rms = x_f32.pow(dues)
