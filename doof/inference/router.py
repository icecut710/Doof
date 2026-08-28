"""InferenceRouter — deterministic fallback chain, never returns nothing.

Chain:
  1. LOCAL PRIMARY (torch GPU or CPU)
  2. LOCAL BACKUP (torch CPU if GPU failed)
  3. REMOTE COMPUTE (LAN or queue)
  4. HOSTED DOOF BRAIN (project endpoint)
  5. MEMORY / MATH (last resort — real data, not fake AI)

Every path returns real text. When neural generation fails, the response
is honestly labeled as memory-retrieval or math — never disguised as
AI-generated output.
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("doof.inference")


class InferenceResult:
    __slots__ = ("text", "provider", "device", "source_label", "latency_ms",
                 "memories_used", "notice", "fallback_of", "model_version",
                 "parameters_m", "d_model", "request_id", "tokens_generated",
                 "actual_generation")

    def __init__(
        self,
        text: str,
        provider: str = "unknown",
        device: str = "",
        source_label: str = "",
        latency_ms: int = 0,
        memories_used: list | None = None,
        notice: dict | None = None,
        fallback_of: str | None = None,
        model_version: str | None = None,
        parameters_m: float | None = None,
        d_model: int | None = None,
        request_id: str | None = None,
        tokens_generated: int = 0,
        actual_generation: bool = False,
    ):
        self.text = text
        self.provider = provider
        self.device = device
        self.source_label = source_label
        self.latency_ms = latency_ms
        self.memories_used = memories_used or []
        self.notice = notice
        self.fallback_of = fallback_of
        self.model_version = model_version
        self.parameters_m = parameters_m
        self.d_model = d_model
        self.request_id = request_id
        self.tokens_generated = tokens_generated
        self.actual_generation = actual_generation

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "text": self.text,
            "provider": self.provider,
            "device": self.device,
            "source_label": self.source_label,
            "elapsed_ms": self.latency_ms,
            "memories_used": self.memories_used,
            "actual_generation": self.actual_generation,
            "tokens_generated": self.tokens_generated,
        }
        if self.notice:
            d["notice"] = self.notice
        if self.fallback_of:
            d["fallback_of"] = self.fallback_of
        if self.model_version:
            d["model_version"] = self.model_version
        if self.parameters_m is not None:
            d["parameters_m"] = self.parameters_m
        if self.d_model is not None:
            d["d_model"] = self.d_model
        if self.request_id:
            d["request_id"] = self.request_id
        return d


def _looks_weak(text: str) -> bool:
    """Detect model parroting memorized fallback phrases from training data.
    
    Keep lenient: genuine model output (even if garbled) is better than
    silently replacing it with canned text. The model will improve with
    training.
    """
    t = (text or "").strip().lower()
    # Only reject if it's the exact memorized fallback phrases
    _PARROT_PATTERNS = [
        "i am here. i do not have enough context",
        "i am here. the primary model is still warming up",
        "i do not have enough context to give a useful answer",
        "i am online, but the full generative model",
        "the primary model is still warming up or unavailable",
        "try again after the brain finishes loading",
    ]
    if any(p in t for p in _PARROT_PATTERNS):
        return True
    # Accept all other output � garbled AI output is OK, model improves with training
    return False


def _try_local_primary(
    prompt: str, *, temperature: float, max_new_tokens: int, top_k: int
) -> InferenceResult | None:
    """Attempt inference with the local torch model (GPU preferred)."""
    from doof.runtime import import_torch, torch_error

    torch = import_torch()
    if torch is None:
        log.info("local primary skipped: torch unavailable (%s)", torch_error())
        return None

    try:
        from doof.api import get_inf
        import uuid as _uuid
        inf = get_inf()
        t0 = time.time()
        text = inf.generate(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
        )
        latency = int((time.time() - t0) * 1000)

        # Strip the prompt prefix if model echoes it back
        if text.startswith(prompt):
            text = text[len(prompt):].lstrip()

        # Count actual generated tokens
        tokens_gen = len(inf.tokenizer.encode(text, add_bos=False, add_eos=False))

        from doof.brain import postprocess_model_text
        cleaned, source = postprocess_model_text(text, prompt)

        device_label = getattr(inf, "device_label", "") or str(getattr(inf, "device", ""))
        n = sum(p.numel() for p in inf.model.parameters())

        if source == "model":
            return InferenceResult(
                text=cleaned,
                provider="local_model",
                device=device_label,
                source_label=_source_label(device_label),
                latency_ms=latency,
                model_version="v3.0",
                parameters_m=round(n / 1e6, 2) if n else None,
                d_model=getattr(inf.model, "d_model", None),
                request_id=_uuid.uuid4().hex[:12],
                tokens_generated=tokens_gen,
                actual_generation=True,
            )
        else:
            # Model ran but produced unusable output — return None so router tries next tier
            log.info("local primary: model ran but produced %s output (%d bytes)", source, tokens_gen)
            return None
    except Exception as e:
        log.warning("local primary failed: %s", e)
        return None


def _try_local_cpu(
    prompt: str, *, temperature: float, max_new_tokens: int, top_k: int
) -> InferenceResult | None:
    """Attempt inference with torch on CPU (fallback if GPU path failed)."""
    from doof.runtime import import_torch

    torch = import_torch()
    if torch is None:
        return None

    try:
        from doof.inference import DOOFInference
        from doof.paths import checkpoints_dir
        ckpt_dir = checkpoints_dir()
        # Find checkpoint
        ckpt = None
        for name in ("doof_v01.pt", "doof_v0.1.pt"):
            p = ckpt_dir / name
            if p.exists():
                ckpt = p
                break
        if ckpt is None:
            import glob
            steps = sorted(ckpt_dir.glob("doof_step_*.pt"))
            if steps:
                ckpt = steps[-1]
        if ckpt is None:
            return None

        # Force CPU device for this path
        from doof.model import DOOFTransformer
        from doof.tokenizer import DOOFTokenizer, LegacyTokenizer
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
        model_cfg = ck.get("model_config", {})
        ckpt_vocab_size = model_cfg.get("vocab_size", 1024)

        # Load tokenizer: prefer saved tokenizer.json, fall back to legacy
        saved_tok = DOOFTokenizer.load_from_checkpoint(ckpt.parent)
        if saved_tok is not None:
            tok = saved_tok
        elif ckpt_vocab_size == LegacyTokenizer.VOCAB_SIZE:
            tok = LegacyTokenizer()
        else:
            tok = DOOFTokenizer()

        model = DOOFTransformer(
            vocab_size=ckpt_vocab_size,
            max_seq_len=model_cfg.get("max_seq_len", 128),
            d_model=model_cfg.get("d_model", 256),
            n_heads=model_cfg.get("n_heads", 8),
            n_layers=model_cfg.get("n_layers", 6),
        ).to("cpu")
        model.load_state_dict(ck["model_state_dict"])
        model.eval()

        tokens = tok.encode(prompt, add_bos=True, add_eos=False)
        prompt_len = len(tokens)
        input_ids = torch.tensor([tokens], dtype=torch.long, device="cpu")

        t0 = time.time()
        with torch.no_grad():
            for _ in range(max_new_tokens):
                context = input_ids[:, -model.max_seq_len:]
                logits = model(context)
                next_token_logits = logits[:, -1, :] / max(float(temperature), 1e-5)
                if top_k and top_k > 0:
                    v, _ = torch.topk(next_token_logits, min(top_k, next_token_logits.size(-1)))
                    next_token_logits[next_token_logits < v[:, [-1]]] = float("-inf")
                probs = torch.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                input_ids = torch.cat([input_ids, next_token], dim=1)
                if next_token.item() == tok.EOS:
                    break
        latency = int((time.time() - t0) * 1000)
        generated = input_ids[0].tolist()[prompt_len:]
        text = tok.decode(generated).strip()

        from doof.brain import postprocess_model_text
        cleaned, source = postprocess_model_text(text, prompt)

        if source == "model":
            return InferenceResult(
                text=cleaned,
                provider="local_cpu",
                device="CPU",
                source_label="LOCAL CPU",
                latency_ms=latency,
                tokens_generated=len(generated),
                actual_generation=True,
            )
        else:
            log.info("local CPU: model ran but produced %s output", source)
            return None
    except Exception as e:
        log.warning("local CPU fallback failed: %s", e)
        return None


def _try_remote_compute(
    prompt: str, *, temperature: float, max_new_tokens: int, top_k: int,
    nodes: list[dict[str, Any]], local_id: str, token: str | None,
) -> InferenceResult | None:
    """Attempt inference via a remote compute node (LAN or queue)."""
    try:
        from doof.compute.pool import dispatch_inference
        t0 = time.time()
        result = dispatch_inference(
            prompt,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            top_k=top_k,
            nodes=nodes,
            local_id=local_id,
            token=token,
        )
        latency = int((time.time() - t0) * 1000)
        text = (result.get("text") or "").strip()
        if text and result.get("provider") != "lightweight":
            return InferenceResult(
                text=text,
                provider=result.get("provider") or "remote",
                device=result.get("device") or "",
                source_label=_remote_label(result),
                latency_ms=latency,
                memories_used=result.get("memories_used") or [],
                notice=result.get("notice"),
                fallback_of=result.get("fallback_of"),
                tokens_generated=result.get("tokens_generated", 0),
                actual_generation=result.get("actual_generation", False),
            )
    except Exception as e:
        log.warning("remote compute failed: %s", e)
    return None


def _try_hosted_brain(
    prompt: str, memories: list[dict[str, Any]]
) -> InferenceResult | None:
    """Attempt inference via the DOOF-hosted brain endpoint."""
    try:
        from doof.compute.cloud_inference import hosted_or_none
        t0 = time.time()
        result = hosted_or_none(prompt, memories)
        latency = int((time.time() - t0) * 1000)
        if result and result.get("ok") and result.get("text"):
            return InferenceResult(
                text=result["text"],
                provider="hosted_brain",
                device="hosted",
                source_label="HOSTED BRAIN",
                latency_ms=latency,
                memories_used=memories,
                actual_generation=True,
            )
    except Exception as e:
        log.warning("hosted brain failed: %s", e)
    return None


def _try_memory_math(
    prompt: str, memories: list[dict[str, Any]], fallback_reason: str | None = None
) -> InferenceResult:
    """Last resort: answer from memory or math. Always succeeds.

    This is NOT pretending to be AI — it honestly uses stored data and arithmetic.
    """
    from doof.brain import memory_answer, math_answer

    t0 = time.time()

    # Try math first (precise computation, not generation)
    math = math_answer(prompt)
    if math:
        latency = int((time.time() - t0) * 1000)
        return InferenceResult(
            text=math,
            provider="computed",
            device="none",
            source_label="COMPUTED",
            latency_ms=latency,
            memories_used=memories,
            fallback_of=fallback_reason,
        )

    # Try memory retrieval (real stored data, not generated)
    mem = memory_answer(prompt, memories)
    latency = int((time.time() - t0) * 1000)
    if mem:
        return InferenceResult(
            text=mem,
            provider="memory",
            device="none",
            source_label="FROM MEMORY",
            latency_ms=latency,
            memories_used=memories,
            fallback_of=fallback_reason,
        )

    # No neural generation succeeded and no memory/math matched
    # Return an honest response — not pretending to be AI
    return InferenceResult(
        text=(
            "The model could not generate a response for this. "
            "Try rephrasing, or add relevant information to Memory so DOOF can help."
        ),
        provider="none",
        device="none",
        source_label="NO GENERATION",
        latency_ms=latency,
        memories_used=memories,
        fallback_of=fallback_reason,
    )


def _source_label(device: str) -> str:
    d = (device or "").lower()
    if "cuda" in d or "nvidia" in d or "gpu" in d:
        return "LOCAL GPU"
    if "mps" in d or "apple" in d:
        return "LOCAL GPU"
    return "LOCAL CPU"


def _remote_label(result: dict) -> str:
    if result.get("routed_to"):
        return f"REMOTE: {result['routed_to']}"
    return "REMOTE NODE"


def route_inference(
    prompt: str,
    *,
    temperature: float = 0.7,
    max_new_tokens: int = 80,
    top_k: int = 50,
    memories: list[dict[str, Any]] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    local_id: str | None = None,
    token: str | None = None,
) -> InferenceResult:
    """Central inference router with deterministic fallback. Never returns None."""
    memories = memories or []
    nodes = nodes or []

    # Step 1: Local primary (GPU if available, else CPU)
    result = _try_local_primary(
        prompt, temperature=temperature, max_new_tokens=max_new_tokens, top_k=top_k
    )
    if result and not _looks_weak(result.text):
        result.memories_used = memories
        return result
    primary_err = f"local primary {'weak' if result else 'unavailable'}"

    # Step 2: Local CPU fallback (if primary failed or was weak)
    from doof.runtime import import_torch
    torch = import_torch()
    if torch is not None:
        cpu_result = _try_local_cpu(
            prompt, temperature=temperature, max_new_tokens=max_new_tokens, top_k=top_k
        )
        if cpu_result and not _looks_weak(cpu_result.text):
            cpu_result.memories_used = memories
            cpu_result.fallback_of = primary_err
            return cpu_result

    # Step 3: Remote compute
    if nodes and local_id:
        remote = _try_remote_compute(
            prompt, temperature=temperature, max_new_tokens=max_new_tokens,
            top_k=top_k, nodes=nodes, local_id=local_id, token=token,
        )
        if remote and not _looks_weak(remote.text):
            remote.memories_used = memories
            remote.fallback_of = primary_err
            return remote

    # Step 4: Hosted DOOF brain
    hosted = _try_hosted_brain(prompt, memories)
    if hosted and hosted.text.strip():
        hosted.fallback_of = primary_err
        return hosted

    # Step 5: Memory / Math (honest fallback — not pretending to be AI)
    return _try_memory_math(prompt, memories, fallback_reason=primary_err)
