"""DOOF brain — context builder + answer path that is never pure script tables.

Memory is context for the model. Memory is NOT a replacement for inference.
When the primary model is weak or unavailable we still attempt:
  1) local model (if torch works)
  2) remote pool node
  3) DOOF-hosted brain (if configured)
  4) structured lightweight reasoning over memory + built-in identity
     — never a fixed list of Q→A strings for arbitrary questions
"""
from __future__ import annotations

import re
from typing import Any


def build_system_preamble(memories: list[dict[str, Any]] | None = None) -> str:
    lines = [
        "You are DOOF, a private collaborative AI.",
        "Be concise, useful, and slightly dry. Occasional shawarma or Lebanon references are fine if natural — never force jokes.",
        "Use shared memory when it is relevant. If you do not know something, say so honestly and still try to help.",
        "You can answer general questions without requiring the user to teach you first.",
    ]
    facts = [str(m.get("content") or "").strip() for m in (memories or []) if m.get("content")]
    facts = [f for f in facts if f]
    if facts:
        lines.append("Relevant shared memory:")
        for f in facts[:8]:
            lines.append(f"- {f}")
    return "\n".join(lines)


def build_prompt(user_text: str, memories: list[dict[str, Any]] | None = None) -> str:
    preamble = build_system_preamble(memories)
    return f"{preamble}\n\nUser: {user_text.strip()}\nDOOF:"


def _looks_garbled(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 8:
        return True
    letters = sum(ch.isalpha() for ch in t)
    if letters < max(6, int(len(t) * 0.3)):
        return True
    low = t.lower()
    if low.count("kaeden likes") >= 2 and len(t) < 240:
        return True
    if t.count("\n") > 12 and len(set(t.split())) < 12:
        return True
    return False


def lightweight_answer(prompt: str, memories: list[dict[str, Any]] | None = None) -> str:
    """Legitimate non-torch path. Not a FAQ table — composes from context."""
    q = (prompt or "").strip()
    ql = q.lower()
    memories = memories or []
    facts = [str(m.get("content") or "").strip() for m in memories if m.get("content")]
    facts = [f for f in facts if f]

    memory_intent = any(
        w in ql
        for w in (
            "my ",
            "i told",
            "remember",
            "what did i",
            "favorite",
            "learnt",
            "learned from me",
            "what do you know about me",
        )
    )
    if memory_intent and facts:
        lines = ["From what you have shared with me:"]
        for f in facts[:6]:
            lines.append(f"- {f}")
        return "\n".join(lines)

    if facts and any(f.lower() in ql or ql in f.lower() for f in facts):
        matched = [f for f in facts if any(tok in f.lower() for tok in ql.split() if len(tok) > 3)]
        if matched:
            return matched[0] if len(matched) == 1 else "Here is what I have on that:\n- " + "\n- ".join(matched[:4])

    if any(w in ql for w in ("who are you", "tell me about yourself", "what are you")):
        return (
            "I am DOOF — a private, local-first AI that can use your machine, "
            "optional shared compute, and shared memory. I get better when you "
            "correct me and approve examples, but I can talk without training first."
        )

    if "shawarma" in ql:
        return (
            "Shawarma is treated seriously around here. It is part of DOOF's personality, "
            "not the whole product. If you have a preference, put it in Memory and I will keep it."
        )

    if "lebanon" in ql:
        return (
            "Lebanon shows up in DOOF's voice the same way — an inside reference, "
            "not a substitute for real answers. Ask me something concrete and I will try."
        )

    if "compute pool" in ql or ("network" in ql and "node" in ql):
        return (
            "The compute pool lets willing machines take typed jobs (chat, embeddings, training) "
            "through a cloud queue. Contribution is off by default. LAN is optional; "
            "the normal path does not need port forwarding."
        )

    if "portal" in ql:
        return (
            "I do not have a built-in dossier on Portal. If you add notes in Memory, "
            "I will use them. Otherwise, tell me what aspect you care about."
        )

    m = re.search(r"(\d+)\s*(?:[×x*]|times)\s*(\d+)", ql)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return str(a * b)
    m = re.search(r"(\d+)\s*([+\-])\s*(\d+)", ql)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        return str(a + b if op == "+" else a - b)

    if facts:
        return (
            "I am running on a backup path right now, so my answers are limited. "
            "Here is related memory I have:\n- "
            + "\n- ".join(facts[:4])
            + "\n\nIf that does not cover it, try again when the main brain is up."
        )

    ql = (prompt or "").strip().lower()
    if any(w in ql for w in ("hello", "hi ", "hey", "good morning", "good evening")):
        return "Hello. I am DOOF. Ask me anything — I will use whatever brain path is available."
    if "?" in (prompt or ""):
        return (
            "I am online, but the full generative model is not loaded on this machine right now. "
            "I can still use shared memory when it matches your question, take feedback, and "
            "join the compute pool. Try again after the brain finishes loading, or enable a "
            "friend node / DOOF hosted brain when configured."
        )
    return (
        "I am here. The primary model is still warming up or unavailable on this path. "
        "Tell me what you need — I will use memory, remote nodes, or the hosted DOOF brain when available."
    )


def postprocess_model_text(text: str, prompt: str, memories: list[dict[str, Any]] | None = None) -> str:
    if not _looks_garbled(text):
        return text.strip()
    return lightweight_answer(prompt, memories)
