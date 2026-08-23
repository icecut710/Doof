"""DOOF Intelligence — Dataset Builder.

Assembles a training dataset from:
1. Approved user corrections (highest priority)
2. Approved examples with good quality scores
3. Important memories formatted as Q&A pairs

Output format: JSONL with ``prompt`` + ``response`` fields.
Also writes a plain-text ``train.txt`` (one response per line) for the
existing PyTorch trainer.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATASETS_DIR = ROOT / "datasets"
FEEDBACK_PATH = DATA_DIR / "feedback.json"
TRAIN_TXT = DATA_DIR / "train.txt"


def _load_feedback() -> list[dict[str, Any]]:
    if not FEEDBACK_PATH.exists():
        return []
    try:
        items = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _memory_to_example(mem: dict[str, Any]) -> dict[str, Any]:
    """Convert a memory card into a minimal training example."""
    content = mem.get("content", "")
    return {
        "prompt": f"What do you know about this?",
        "response": content,
        "source": "memory",
        "memory_id": mem.get("id"),
    }


def build_dataset(
    store: Any | None = None,
    *,
    version: str | None = None,
    min_quality: float = 55.0,
    max_examples: int = 5000,
    val_split: float = 0.1,
) -> dict[str, Any]:
    """Build training + validation datasets.

    Parameters
    ----------
    store:
        Memory :class:`Store` instance.  If None, the global singleton is used.
    version:
        Dataset version label.  Auto-generated from timestamp if None.
    min_quality:
        Minimum quality score for an example to be included.
    max_examples:
        Hard cap on dataset size.
    val_split:
        Fraction of examples reserved for validation.

    Returns
    -------
    dict with keys: ``train_path``, ``val_path``, ``train_count``,
    ``val_count``, ``total_tokens``, ``version``.
    """
    from doof.intelligence.quality import score_example  # avoid circular at module level
    from doof.intelligence.store import get_store

    if store is None:
        store = get_store()

    if version is None:
        version = time.strftime("v%Y%m%d_%H%M%S")

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)

    examples: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # 1. Approved corrections (highest priority)
    # ------------------------------------------------------------------ #
    feedback_items = _load_feedback()
    for item in feedback_items:
        if not item.get("approved", True):
            continue
        correction = (item.get("correction") or "").strip()
        if not correction:
            continue
        ex = {
            "prompt": item.get("prompt", ""),
            "response": correction,
            "source": "correction",
            "rating": "good",
        }
        q = score_example(ex)
        if q["total"] >= min_quality:
            ex["quality"] = q["total"]
            examples.append(ex)

    # ------------------------------------------------------------------ #
    # 2. Good-rated examples without corrections
    # ------------------------------------------------------------------ #
    for item in feedback_items:
        if not item.get("approved", True):
            continue
        if item.get("rating") != "good":
            continue
        response = (item.get("response") or "").strip()
        if not response:
            continue
        ex = {
            "prompt": item.get("prompt", ""),
            "response": response,
            "source": "feedback",
            "rating": "good",
        }
        q = score_example(ex)
        if q["total"] >= min_quality:
            ex["quality"] = q["total"]
            examples.append(ex)

    # ------------------------------------------------------------------ #
    # 3. Important memories
    # ------------------------------------------------------------------ #
    memories = store.list_all(approved_only=True)
    for mem in memories:
        if mem.get("importance") in ("high", "medium"):
            ex = _memory_to_example(mem)
            ex["quality"] = 60.0  # baseline for approved memories
            examples.append(ex)

    # Deduplicate by response content
    seen_responses: set[str] = set()
    unique_examples: list[dict[str, Any]] = []
    for ex in examples:
        key = ex["response"][:120]
        if key not in seen_responses:
            seen_responses.add(key)
            unique_examples.append(ex)

    # Sort by quality descending, cap
    unique_examples.sort(key=lambda x: x.get("quality", 0.0), reverse=True)
    unique_examples = unique_examples[:max_examples]

    # Shuffle before split
    random.shuffle(unique_examples)

    n_val = max(1, int(len(unique_examples) * val_split)) if unique_examples else 0
    val_examples = unique_examples[:n_val]
    train_examples = unique_examples[n_val:]

    # Write JSONL
    train_path = DATASETS_DIR / f"train_{version}.jsonl"
    val_path = DATASETS_DIR / f"validation_{version}.jsonl"

    train_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in train_examples),
        encoding="utf-8",
    )
    val_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in val_examples),
        encoding="utf-8",
    )

    # Also update the plain train.txt used by the existing trainer
    train_lines = [e["response"] for e in train_examples if e.get("response")]
    # Supplement with approved memory content
    train_lines += store.export_training_lines()
    TRAIN_TXT.parent.mkdir(parents=True, exist_ok=True)
    TRAIN_TXT.write_text("\n".join(train_lines) + "\n", encoding="utf-8")

    total_tokens = sum(len(e.get("response", "").split()) for e in unique_examples)

    return {
        "version": version,
        "train_path": str(train_path),
        "val_path": str(val_path),
        "train_count": len(train_examples),
        "val_count": len(val_examples),
        "total_tokens": total_tokens,
        "sources": {
            "corrections": sum(1 for e in train_examples if e.get("source") == "correction"),
            "feedback": sum(1 for e in train_examples if e.get("source") == "feedback"),
            "memories": sum(1 for e in train_examples if e.get("source") == "memory"),
        },
    }
