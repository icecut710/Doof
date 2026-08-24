"""Map raw exceptions to user-facing copy. Never show a traceback by default."""
from __future__ import annotations

from typing import Any

from doof.personality import pick

# Substrings we treat as the infamous missing-module crash.
_TORCH_MISSING = (
    "torchdistribute",
    "torch.distributed",
    "no module named 'torch'",
    "no module named torch",
    "modulenotfounderror: no module named 'torch",
)


def _hay(err: BaseException | str) -> str:
    if isinstance(err, BaseException):
        parts = [type(err).__name__, str(err)]
        cause = err.__cause__ or err.__context__
        if cause is not None:
            parts.append(str(cause))
        return " ".join(parts).lower()
    return str(err).lower()


def classify(err: BaseException | str) -> str:
    h = _hay(err)
    if any(s in h for s in _TORCH_MISSING):
        return "ai_down"
    if "cuda" in h or "cublas" in h or "cudnn" in h:
        return "gpu_none"
    if "connection" in h or "urlerror" in h or "timed out" in h or "unreachable" in h:
        return "offline"
    if "supabase" in h:
        return "cloud_offline"
    return "errors"


def user_message(err: BaseException | str, *, fallback_used: str | None = None) -> dict[str, Any]:
    """Return a structured, UI-safe error.

    Fields:
      title, body, action, fallback, technical, kind
    """
    kind = classify(err)
    title, detail = pick(kind)
    technical = err if isinstance(err, str) else f"{type(err).__name__}: {err}"
    action = "You do not need to do anything. DOOF stayed open."
    fallback = fallback_used
    if kind == "ai_down":
        title = "The local brain failed to start."
        if fallback_used == "memory":
            body = "DOOF switched to its backup brain (shared memory)."
        elif fallback_used == "cloud":
            body = "DOOF switched to its backup brain (cloud)."
        elif fallback_used == "remote":
            body = "DOOF sent the order to another grill on the network."
        else:
            body = "DOOF could not load a model. Chat used a safe fallback."
        action = "If this keeps happening, a friend with a stronger PC can share compute."
    elif kind == "offline":
        body = detail
        action = "Check that this machine can see the brain, or work locally."
    elif kind == "cloud_offline":
        body = "Cloud sync did not complete. Local data is still here."
        action = "You can keep using DOOF offline."
    else:
        body = detail
    return {
        "ok": False,
        "kind": kind,
        "title": title,
        "body": body,
        "action": action,
        "fallback": fallback,
        "technical": technical,
        "error": title,  # legacy field used by older UI
    }


def public_error(err: BaseException | str, *, fallback_used: str | None = None) -> dict[str, Any]:
    """API payload: never includes a traceback."""
    return user_message(err, fallback_used=fallback_used)
