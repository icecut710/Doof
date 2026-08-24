"""DOOF model management — registry metadata, local cache, checksums.

Models are NOT bundled inside DOOF.exe. They live under:
  %LOCALAPPDATA%\\DOOF\\models\\

Supabase holds metadata; object storage / CDN holds blobs.
"""
from __future__ import annotations

from doof.models.manager import (
    ModelInfo,
    cache_dir,
    ensure_model,
    list_cached,
    list_registry,
    local_path,
    model_compatible,
    resolve_active_model,
    verify_checksum,
)

__all__ = [
    "ModelInfo",
    "cache_dir",
    "ensure_model",
    "list_cached",
    "list_registry",
    "local_path",
    "model_compatible",
    "resolve_active_model",
    "verify_checksum",
]
