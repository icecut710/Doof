"""DOOF Intelligence — Quality Scoring.

Deterministic scoring for model responses and training examples.
Score range: 0–100.  Only approved, high-quality examples should enter
the training pipeline.

Dimensions
----------
1. Length appropriateness   (10 pts)  — not too short, not too long
2. Vocabulary richness      (20 pts)  — type-token ratio
3. Non-repetition           (20 pts)  — no repeated phrases/tokens
4. Coherence proxy          (20 pts)  — average word length, sentence structure
5. Factual grounding        (10 pts)  — if memories were used, bonus
6. User feedback            (20 pts)  — 👍 = full, 👎 = 0, not rated = 10
"""
from __future__ import annotations

import math
import re
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9']+", text.lower())


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 8]


# ---------------------------------------------------------------------------
# Sub-scores
# ---------------------------------------------------------------------------

def _score_length(response: str, *, ideal_min: int = 20, ideal_max: int = 300) -> float:
    """10 pts — penalise very short or very long responses."""
    n = len(response.strip())
    if n < 5:
        return 0.0
    if n < ideal_min:
        return 10.0 * (n / ideal_min)
    if n > ideal_max * 2:
        return 5.0
    if n > ideal_max:
        overshoot = (n - ideal_max) / ideal_max
        return max(10.0 - overshoot * 5.0, 5.0)
    return 10.0


def _score_vocabulary(tokens: list[str]) -> float:
    """20 pts — type-token ratio (lexical diversity)."""
    if not tokens:
        return 0.0
    ttr = len(set(tokens)) / len(tokens)
    return min(ttr * 25.0, 20.0)


def _score_repetition(tokens: list[str], text: str) -> float:
    """20 pts — penalise repeated bigrams and repeated phrases."""
    if len(tokens) < 4:
        return 10.0

    bigrams = [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]
    bigram_counts: dict[tuple[str, str], int] = {}
    for bg in bigrams:
        bigram_counts[bg] = bigram_counts.get(bg, 0) + 1

    max_repeat = max(bigram_counts.values()) if bigram_counts else 1
    repeat_penalty = max(0.0, (max_repeat - 2) * 4.0)

    score = 20.0 - repeat_penalty
    return max(score, 0.0)


def _score_coherence(text: str, tokens: list[str]) -> float:
    """20 pts — proxy via avg word length and sentence count."""
    if not tokens:
        return 0.0
    avg_word_len = sum(len(t) for t in tokens) / len(tokens)
    # Sweet spot: words 4–8 chars
    word_score = 10.0 * max(0.0, 1.0 - abs(avg_word_len - 5.5) / 5.5)

    sents = _sentences(text)
    sent_score = min(len(sents) * 2.0, 10.0)  # more sentences up to 5 = 10 pts

    return word_score + sent_score


def _score_memory_usage(memories_used: list[Any] | None) -> float:
    """10 pts — bonus when the answer was grounded in retrieved memories."""
    if not memories_used:
        return 5.0  # neutral
    return min(10.0, 5.0 + len(memories_used) * 2.5)


def _score_feedback(rating: str | None) -> float:
    """20 pts — based on explicit user feedback."""
    if rating == "good":
        return 20.0
    if rating == "bad":
        return 0.0
    return 10.0  # unrated → neutral


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_response(
    prompt: str,
    response: str,
    *,
    memories_used: list[Any] | None = None,
    rating: str | None = None,
) -> dict[str, float]:
    """Score a model response.

    Returns a dict with individual sub-scores and a ``total`` (0–100).
    """
    tokens = _tokenise(response)

    length = _score_length(response)
    vocab = _score_vocabulary(tokens)
    repetition = _score_repetition(tokens, response)
    coherence = _score_coherence(response, tokens)
    memory = _score_memory_usage(memories_used)
    feedback = _score_feedback(rating)

    total = length + vocab + repetition + coherence + memory + feedback

    return {
        "length": round(length, 2),
        "vocabulary": round(vocab, 2),
        "repetition": round(repetition, 2),
        "coherence": round(coherence, 2),
        "memory_usage": round(memory, 2),
        "feedback": round(feedback, 2),
        "total": round(total, 2),
        "quality_label": _label(total),
        "training_ready": total >= 55.0,
    }


def score_example(example: dict[str, Any]) -> dict[str, float]:
    """Score a stored training example dict (prompt/response/rating)."""
    return score_response(
        prompt=example.get("prompt", ""),
        response=example.get("response", ""),
        memories_used=example.get("memories_used"),
        rating=example.get("rating"),
    )


def _label(score: float) -> str:
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "acceptable"
    if score >= 35:
        return "poor"
    return "reject"
