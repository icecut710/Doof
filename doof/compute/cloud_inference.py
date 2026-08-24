"""Cloud / hosted inference helpers for the compute pool."""
from __future__ import annotations

from typing import Any


def hosted_or_none(
    prompt: str,
    memories: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_new_tokens: int = 120,
) -> dict[str, Any] | None:
    """DOOF-hosted generative brain only — no third-party providers."""
    try:
        from doof.brain import build_system_preamble
        from doof.cloud.hosted_brain import hosted_generate

        return hosted_generate(
            prompt,
            system=build_system_preamble(memories),
            temperature=temperature,
            max_new_tokens=max_new_tokens,
        )
    except Exception:
        return None
