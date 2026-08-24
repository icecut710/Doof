"""Helpers used by pool — kept separate to avoid rewriting entire pool.py."""
from __future__ import annotations

from typing import Any


def try_hosted_doof_brain(
    prompt: str,
    memories: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_new_tokens: int = 120,
) -> dict[str, Any] | None:
    try:
        from doof.brain import build_system_preamble
        from doof.cloud.hosted_brain import hosted_generate

        system = build_system_preamble(memories)
        return hosted_generate(
            prompt,
            system=system,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
        )
    except Exception:
        return None
