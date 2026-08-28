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

import logging
import re
from typing import Any

log = logging.getLogger("doof.brain")


def build_system_preamble(memories: list[dict[str, Any]] | None = None) -> str:
    lines = [
        "You are DOOF, a private collaborative AI.",
        "Be concise, useful, and slightly dry. Occasional shawarma or Lebanon references are fine if natural — never force jokes.",
        "Use shared memory ONLY when it is clearly relevant to the user's question. Do not mention unrelated memories.",
        "You can answer general questions without requiring the user to teach you first.",
        "If asked about identity, answer about DOOF. If asked about preferences, check if any relevant preference memories exist. Do not volunteer irrelevant personal details.",
    ]
    facts = [str(m.get("content") or "").strip() for m in (memories or []) if m.get("content")]
    facts = [f for f in facts if f]
    if facts:
        lines.append("Relevant shared memory (use only if directly related to the question):")
        for f in facts[:8]:
            lines.append(f"- {f}")
    return "\n".join(lines)


def build_prompt(user_text: str, memories: list[dict[str, Any]] | None = None) -> str:
    preamble = build_system_preamble(memories)
    return f"{preamble}\n\nUser: {user_text.strip()}\nDOOF:"


def _looks_garbled(text: str) -> bool:
    """Detect obviously broken model output. Keep minimal to avoid false positives."""
    t = (text or "").strip()
    if not t:
        return True
    if len(t) < 4:
        return True
    letters = sum(ch.isalpha() for ch in t)
    if len(t) > 6 and letters < max(3, int(len(t) * 0.2)):
        return True
    low = t.lower()
    # Catch training data parroting (any variant of known training phrases)
    _TRAINING_PATTERNS = (
        "kaeden", "futuristic dark interface", "futuristic dark",
        "i am here", "warming up", "brain path",
    )
    if any(p in low for p in _TRAINING_PATTERNS):
        return True
    if t.count("\n") > 12 and len(set(t.split())) < 12:
        return True
    # Repetition check
    words = [w for w in t.split() if any(c.isalnum() for c in w)]
    if len(words) > 5:
        from collections import Counter
        counts = Counter(w.lower() for w in words)
        most_common_count = counts.most_common(1)[0][1]
        if most_common_count > len(words) * 0.4:
            return True
    # Nonsense word density: if most words don't look like real English
    if len(words) >= 4:
        _REAL_ENGLISH = {
            "the","a","an","i","is","are","was","you","my","me","to",
            "of","in","for","with","on","at","by","it","this","that",
            "have","has","do","does","can","will","not","but","or",
            "and","if","so","no","yes","am","be","we","he","she",
            "they","what","how","when","where","who","why","all",
            "your","its","our","about","from","into","just","like",
            "also","still","more","most","than","then","very",
            "hello","hi","hey","thanks","please","sure","well",
            "here","there","now","then","after","before","over",
            "under","between","through","before","during","since",
        }
        real_words = sum(1 for w in words if w.lower().rstrip(".,!?;:'\"-") in _REAL_ENGLISH)
        if real_words < max(2, len(words) * 0.15):
            return True
    return False


def memory_answer(prompt: str, memories: list[dict[str, Any]] | None = None) -> str:
    """Answer from stored memory. Returns "" if no memory matches.

    This is NOT neural generation — it retrieves real user-provided data.
    """
    q = (prompt or "").strip()
    ql = q.lower()
    memories = memories or []
    facts = [str(m.get("content") or "").strip() for m in memories if m.get("content")]
    facts = [f for f in facts if f]

    # Direct memory query — user is asking what they told DOOF
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

    # Topic-specific memory match — word overlap with memory content
    if facts:
        import string as _string
        # Strip punctuation and lowercase query words
        query_words = set(w.strip(_string.punctuation) for w in ql.split())

        def _stem(word: str) -> str:
            """Minimal suffix strip for matching: likes→like, running→run"""
            if word.endswith("ing") and len(word) > 5:
                return word[:-3]
            if word.endswith("ies") and len(word) > 4:
                return word[:-3] + "y"
            # Check single 's' before 'es' to handle likes→like correctly
            if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
                return word[:-1]
            if word.endswith("es") and len(word) > 5:
                return word[:-2]
            return word

        query_stems = set(_stem(w) for w in query_words if len(w) > 2)

        for f in facts:
            fl = f.lower()
            # Direct substring match
            if fl in ql or ql in fl:
                return f
            # Word overlap using stems
            f_words = set(fl.split())
            f_stems = set(_stem(w.strip(_string.punctuation)) for w in f_words if len(w.strip(_string.punctuation)) > 2)
            overlap = query_stems & f_stems
            if overlap:
                return f

    return ""


def math_answer(prompt: str) -> str:
    """Compute arithmetic. Returns "" if not a math expression."""
    q = (prompt or "").strip().lower()
    m = re.search(r"(\d+)\s*(?:[×x*]|times)\s*(\d+)", q)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return str(a * b)
    m = re.search(r"(\d+)\s*([+\-])\s*(\d+)", q)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        return str(a + b if op == "+" else a - b)
    return ""


def postprocess_model_text(text: str, prompt: str, memories: list[dict[str, Any]] | None = None) -> tuple[str, str]:
    """Validate model output. Returns (text, source).

    Returns:
        (cleaned_text, source) where source is:
          "model" — text is genuine model output
          "memory" — model output was unusable, used memory instead
          "empty" — model produced nothing usable

    Never returns canned identity/personality text.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        log.debug("model produced empty output for prompt: %s", prompt[:80])
        # Try memory-based answer for the prompt
        mem = memory_answer(prompt, memories)
        if mem:
            return mem, "memory"
        return "", "empty"

    if not _looks_garbled(cleaned):
        return cleaned, "model"

    # Model produced garbled output — try memory as honest alternative
    log.debug("model produced garbled output (%d chars), prompt: %s", len(cleaned), prompt[:80])
    mem = memory_answer(prompt, memories)
    if mem:
        return mem, "memory"

    return "", "empty"
