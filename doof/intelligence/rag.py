"""DOOF Intelligence — Retrieval-Augmented Generation (RAG).

Current implementation: TF-IDF-style keyword matching against the memory
store.  The interface is designed so the retrieval backend can be swapped
to embedding-based search (e.g. sentence-transformers) without touching
calling code.

Usage::

    from doof.intelligence.rag import retrieve_memories
    from doof.intelligence.store import get_store

    results = retrieve_memories("What UI does Kaeden prefer?", get_store())
    for r in results:
        print(r["score"], r["content"])
"""
from __future__ import annotations

import math
import re
from typing import Any

from doof.intelligence.store import Store, get_store

# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will "
    "would could should may might shall can need dare ought to of in on at "
    "by for with about against between into through during before after "
    "above below up down out off over under again further then once here "
    "there when where why how all both each few more most other some such "
    "no nor not only own same so than too very s t just don don't should've "
    "i you he she it we they what which who this that these those am and or "
    "but if because as until while".split()
)


def _tokenise(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    total = len(tokens) or 1
    return {t: c / total for t, c in counts.items()}


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    avg_doc_len: float = 40.0,
) -> float:
    """Simplified BM25 score without IDF (single-document context)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf_map = _tf(doc_tokens)
    score = 0.0
    for term in query_tokens:
        tf_val = tf_map.get(term, 0.0) * dl  # raw count approximation
        numerator = tf_val * (k1 + 1)
        denominator = tf_val + k1 * (1 - b + b * dl / avg_doc_len)
        score += numerator / (denominator + 1e-9)
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_memories(
    query: str,
    store: Store | None = None,
    *,
    top_k: int = 5,
    min_score: float = 0.05,
    approved_only: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve the most relevant memories for *query*.

    Parameters
    ----------
    query:
        The user's message or search string.
    store:
        A :class:`Store` instance.  Falls back to the global singleton.
    top_k:
        Maximum number of results to return.
    min_score:
        Minimum BM25-like relevance score.  Items below this are excluded.
    approved_only:
        Only retrieve approved memories (default: True).

    Returns
    -------
    list of dicts with keys:
        ``id``, ``content``, ``score``, ``importance``, ``usage_count``,
        ``category``, ``created_by``, ``created_at``
    """
    if store is None:
        store = get_store()

    query_tokens = _tokenise(query)
    if not query_tokens:
        return []

    memories = store.list_all(approved_only=approved_only)
    if not memories:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for mem in memories:
        doc_tokens = _tokenise(mem.get("content", ""))
        raw_score = _bm25_score(query_tokens, doc_tokens)

        # Boost by importance
        importance = mem.get("importance", "medium")
        boost = {"high": 1.4, "medium": 1.0, "low": 0.7}.get(importance, 1.0)

        # Boost by usage (popular memories are probably more useful)
        usage_boost = 1.0 + min(math.log1p(mem.get("usage_count", 0)) * 0.05, 0.3)

        final_score = raw_score * boost * usage_boost
        if final_score >= min_score:
            scored.append((final_score, mem))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    results: list[dict[str, Any]] = []
    for score, mem in top:
        results.append(
            {
                "id": mem["id"],
                "content": mem["content"],
                "score": round(score, 4),
                "importance": mem.get("importance", "medium"),
                "usage_count": mem.get("usage_count", 0),
                "category": mem.get("category", "general"),
                "created_by": mem.get("created_by", "system"),
                "created_at": mem.get("created_at", ""),
            }
        )

    return results


def build_context(memories: list[dict[str, Any]]) -> str:
    """Format retrieved memories as a context prefix for the model prompt."""
    if not memories:
        return ""
    lines = ["[DOOF MEMORY]"]
    for m in memories:
        lines.append(f"• {m['content']}")
    lines.append("[/DOOF MEMORY]")
    return "\n".join(lines)
