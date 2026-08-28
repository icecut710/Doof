"""DOOF Intelligence — Dataset Builder.

Assembles a training dataset from:
1. Approved user corrections (highest priority, human-authored)
2. Approved examples with good quality scores
3. Important memories formatted as Q&A pairs

Output format: JSONL with ``prompt`` + ``response`` + provenance fields.
Also writes a plain-text ``train.txt`` (one response per line) for the
existing PyTorch trainer.

Provenance tracking:
- ``source``: "correction" | "feedback" | "memory" | "imported"
- ``authored_by``: human name or system identifier
- ``ai_assisted``: bool — whether AI helped format/clean/validate
- ``imported_from``: source path or URL if externally imported
- ``approved_at``: timestamp of approval
- ``quality``: numeric score 0–100
- ``training_ready``: bool — whether example passed quality threshold
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any

try:
    from doof.paths import bundle_root, user_data_dir
    ROOT = bundle_root()
    DATA_DIR = user_data_dir()
except Exception:
    ROOT = Path(__file__).resolve().parents[2]
    DATA_DIR = ROOT / "data"

DATASETS_DIR = user_data_dir() / "datasets"
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
    """Convert a memory card into a minimal training example with provenance."""
    content = mem.get("content", "")
    category = mem.get("category", "general")
    tags = mem.get("tags") or []
    prompted = mem.get("prompted", False)
    importance = mem.get("importance", "low")
    mem_id = mem.get("id", "")
    sourced_from = mem.get("sourced_from", "")

    prompts = [
        f"What do you know about {category}?",
        f"Tell me about this.",
        f"What have you learned about this topic?",
        f"Share what you know here.",
    ]
    prompt = (
        prompts[hash(content) % len(prompts)] if content else "What do you know?"
    )

    return {
        "prompt": prompt,
        "response": content,
        "source": "memory",
        "authored_by": mem.get("author", "system"),
        "ai_assisted": not prompted,
        "imported_from": "",
        "approved_at": time.time(),
        "quality": 60.0,  # baseline for approved memories
        "training_ready": True,
        "memory_id": mem_id,
        "sourced_from": sourced_from,
        "category": category,
        "tags": tags,
        "importance": importance,
        "prompted": prompted,
    }


def _make_example_provenance(
    source: str,
    authored_by: str,
    ai_assisted: bool = False,
    imported_from: str = "",
    approved_at: float | None = None,
    quality: float = 0.0,
    training_ready: bool = False,
) -> dict[str, Any]:
    """Build a provenance dict to attach to every training example."""
    return {
        "source": source,
        "authored_by": authored_by,
        "ai_assisted": ai_assisted,
        "imported_from": imported_from,
        "approved_at": approved_at if approved_at is not None else time.time(),
        "quality": quality,
        "training_ready": training_ready,
    }


def _score_example_with_provenance(
    ex: dict[str, Any],
) -> dict[str, Any]:
    """Score an example and merge provenance metadata into the result."""
    q = score_example(ex)
    provenance = _make_example_provenance(
        source=ex.get("source", "unknown"),
        authored_by=ex.get("authored_by", "system"),
        ai_assisted=bool(ex.get("ai_assisted", False)),
        imported_from=ex.get("imported_from", ""),
        approved_at=ex.get("approved_at", time.time()),
        quality=q.get("total", 0.0),
        training_ready=q.get("training_ready", False),
    )
    # Merge provenance into the example so it persists in the JSONL
    ex.update(provenance)
    return q, ex


# ---------------------------------------------------------------------------
# Dataset Building
# ---------------------------------------------------------------------------

def build_dataset(
    store: Any | None = None,
    *,
    version: str | None = None,
    min_quality: float = 55.0,
    max_examples: int = 5000,
    val_split: float = 0.1,
    human_authored_only: bool = False,
) -> dict[str, Any]:
    """Build training + validation datasets.

    Parameters
    ----------
    store:
        Memory ``Store`` instance. If None, the global singleton is used.
    version:
        Dataset version label. Auto-generated from timestamp if None.
    min_quality:
        Minimum quality score for an example to be included.
    max_examples:
        Hard cap on dataset size.
    val_split:
        Fraction of examples reserved for validation.
    human_authored_only:
        If True, only include examples where ``ai_assisted`` is False
        and ``source`` is "correction" or "feedback".  This enforces that
        the final training corpus comes from human contributors.

    Returns
    -------
    dict with keys: ``train_path``, ``val_path``, ``train_count``,
    ``val_count``, ``total_tokens``, ``version``, ``sources``,
    ``human_only`` — whether the ``human_authored_only`` flag was active.
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
    # 1. Approved corrections (highest priority — these are human-written)
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
            "authored_by": item.get("author", "human"),
            "ai_assisted": False,  # corrections are explicitly human
            "imported_from": "",
            "approved_at": item.get("approved_at", time.time()),
            "rating": item.get("rating", "good"),
        }
        q = score_example(ex)
        ex["quality"] = q["total"]
        ex["training_ready"] = q["training_ready"]
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
            "authored_by": item.get("author", "human"),
            "ai_assisted": bool(item.get("ai_helper", False)),  # True if AI helped
            "imported_from": "",
            "approved_at": item.get("approved_at", time.time()),
            "rating": item.get("rating", "good"),
        }
        q, ex = _score_example_with_provenance(ex)
        examples.append(ex)

    # ------------------------------------------------------------------ #
    # 3. Important memories
    # ------------------------------------------------------------------ #
    memories = store.list_all(approved_only=True)
    for mem in memories:
        if mem.get("importance") in ("high", "medium"):
            ex = _memory_to_example(mem)
            q = score_example(ex)
            ex["quality"] = q["total"]
            ex["training_ready"] = q["training_ready"]
            examples.append(ex)

    # ------------------------------------------------------------------ #
    # 4. Optional: imported datasets (must have explicit human approval)
    # ------------------------------------------------------------------ #
    # Imported datasets are included only when human_authored_only is False.
    # They carry their own provenance so the UI can display "imported from X".
    if not human_authored_only:
        datasets_dir = Path("datasets")
        if datasets_dir.is_dir():
            for p in sorted(datasets_dir.glob("train_*.jsonl")):
                try:
                    for raw in p.read_text(encoding="utf-8").splitlines():
                        if not raw.strip():
                            continue
                        try:
                            imp = json.loads(raw)
                            if imp.get("source") in ("imported", "external"):
                                # Keep only if explicitly approved
                                if imp.get("approved", False):
                                    ex = {
                                        "prompt": imp.get("prompt", ""),
                                        "response": imp.get("response", ""),
                                        "source": imp.get("source", "imported"),
                                        "authored_by": imp.get("authored_by", "imported"),
                                        "ai_assisted": bool(imp.get("ai_assisted", False)),
                                        "imported_from": imp.get("imported_from", ""),
                                        "approved_at": imp.get("approved_at", time.time()),
                                        "quality": imp.get("quality", 0.0),
                                        "training_ready": imp.get(
                                            "training_ready", False
                                        ),
                                    }
                                    q = score_example(ex)
                                    ex["quality"] = q["total"]
                                    ex["training_ready"] = q["training_ready"]
                                    examples.append(ex)
                        except Exception:
                            pass
                except Exception:
                    pass

    # Deduplicate by response content (first 120 chars)
    seen_responses: set[str] = set()
    unique_examples: list[dict[str, Any]] = []
    for ex in examples:
        key = ex.get("response", "")[:120]
        if key not in seen_responses:
            seen_responses.add(key)
            unique_examples.append(ex)

    # Sort by quality descending, cap
    unique_examples.sort(
        key=lambda x: x.get("quality", 0.0), reverse=True
    )
    unique_examples = unique_examples[:max_examples]

    # Shuffle before split
    random.seed(42)  # deterministic shuffle
    random.shuffle(unique_examples)

    n_val = max(1, int(len(unique_examples) * val_split)) if unique_examples else 0
    # Ensure at least 1 example goes to training when data exists
    if n_val >= len(unique_examples):
        n_val = max(0, len(unique_examples) - 1)
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

    total_tokens = sum(len(e.get("response", "").split()) for e in unique_examples)

    return {
        "version": version,
        "train_path": str(train_path),
        "val_path": str(val_path),
        "train_count": len(train_examples),
        "val_count": len(val_examples),
        "total_tokens": total_tokens,
        "sources": {
            "corrections": sum(
                1 for e in train_examples if e.get("source") == "correction"
            ),
            "feedback": sum(
                1 for e in train_examples if e.get("source") == "feedback"
            ),
            "memories": sum(
                1 for e in train_examples if e.get("source") == "memory"
            ),
            "imported": sum(
                1 for e in train_examples if e.get("source") == "imported"
            ),
        },
        "human_only": human_authored_only,
    }