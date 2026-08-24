"""Applied at import via api_mount / pool to replace _cloud_inference."""
from __future__ import annotations


def install() -> None:
    try:
        from doof.compute import pool
        from doof.compute.cloud_inference import hosted_or_none

        def _cloud_inference(prompt, memories):
            return hosted_or_none(prompt, memories)

        pool._cloud_inference = _cloud_inference  # type: ignore[assignment]
        print("[pool_patch] cloud path → DOOF-hosted brain")
    except Exception as e:
        print(f"[pool_patch] skip: {e}")
