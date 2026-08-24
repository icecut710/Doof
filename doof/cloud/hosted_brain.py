"""DOOF-hosted cloud brain — project-controlled inference endpoint.

This is NOT xAI / OpenAI / Anthropic / Gemini.
Configure:
  DOOF_HOSTED_BRAIN_URL=https://brain.your-doof-domain/v1/generate
  DOOF_HOSTED_BRAIN_TOKEN=...   (optional bearer; prefer user session token)

The hosted brain is treated as another DOOF inference service with health,
latency, model version, and capacity reported to the control plane.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def hosted_config() -> dict[str, Any]:
    url = (os.environ.get("DOOF_HOSTED_BRAIN_URL") or "").rstrip("/")
    token = os.environ.get("DOOF_HOSTED_BRAIN_TOKEN") or ""
    return {
        "enabled": bool(url),
        "url": url or None,
        "has_token": bool(token),
    }


def hosted_health() -> dict[str, Any]:
    cfg = hosted_config()
    if not cfg["enabled"]:
        return {
            "available": False,
            "state": "not_configured",
            "label": "DOOF hosted brain not configured",
            "ms": None,
        }
    headers = {"Accept": "application/json", "User-Agent": "DOOF/0.3"}
    if cfg["has_token"]:
        headers["Authorization"] = f"Bearer {os.environ.get('DOOF_HOSTED_BRAIN_TOKEN')}"
    health_url = cfg["url"] + "/health"
    # Also accept generate-only endpoints: try /health then root
    t0 = time.perf_counter()
    for endpoint in (health_url, cfg["url"]):
        try:
            req = Request(endpoint, headers=headers, method="GET")
            with urlopen(req, timeout=6) as resp:
                ms = int((time.perf_counter() - t0) * 1000)
                body = {}
                try:
                    body = json.loads(resp.read().decode("utf-8"))
                except Exception:
                    body = {}
                return {
                    "available": 200 <= resp.status < 300,
                    "state": "healthy" if 200 <= resp.status < 300 else "degraded",
                    "label": body.get("label") or f"DOOF hosted brain · {ms}ms",
                    "ms": ms,
                    "model": body.get("model") or body.get("model_version"),
                    "capacity": body.get("capacity"),
                }
        except HTTPError as e:
            if e.code in (401, 403):
                return {
                    "available": False,
                    "state": "unauthorized",
                    "label": "DOOF hosted brain credentials rejected",
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
        except Exception:
            continue
    return {
        "available": False,
        "state": "unreachable",
        "label": "DOOF hosted brain unreachable",
        "ms": None,
    }


def hosted_generate(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    max_new_tokens: int = 120,
    user_token: str | None = None,
) -> dict[str, Any] | None:
    cfg = hosted_config()
    if not cfg["enabled"]:
        return None
    url = cfg["url"]
    if not url.endswith("/generate") and not url.endswith("/v1/generate"):
        # allow base URL pointing at service root
        gen_url = url + "/generate"
    else:
        gen_url = url
    token = user_token or os.environ.get("DOOF_HOSTED_BRAIN_TOKEN") or ""
    body = json.dumps(
        {
            "prompt": prompt,
            "system": system or "",
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "source": "doof-node",
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "DOOF/0.3",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.perf_counter()
    try:
        req = Request(gen_url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = (data.get("text") or data.get("content") or data.get("response") or "").strip()
        if not text:
            return None
        ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": True,
            "text": text,
            "provider": "doof_hosted",
            "model": data.get("model") or data.get("model_version"),
            "ms": ms,
        }
    except Exception:
        return None
