"""DOOF Intelligence — Model Evaluation.

Computes perplexity of a checkpoint against held-out examples.
This is the gate that determines whether a candidate brain should be
promoted to production.

Perplexity is the standard language model metric:
    PPL = exp(mean negative log-likelihood per token)

Lower is better.  A new brain must have lower perplexity than the
current production brain to be promoted.
"""
from __future__ import annotations

import json
import math
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
DATASETS_DIR = ROOT / "datasets"
CKPT_DIR = ROOT / "checkpoints"
EVAL_LOG = DATA_DIR / "eval_log.json"


def _load_val_examples(val_path: str | Path | None = None) -> list[str]:
    """Load validation texts from the most recent validation JSONL."""
    if val_path:
        p = Path(val_path)
    else:
        # Find most recent validation file
        val_files = sorted(DATASETS_DIR.glob("validation_*.jsonl"))
        if not val_files:
            return []
        p = val_files[-1]

    texts: list[str] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                if obj.get("response"):
                    texts.append(obj["response"])
    except Exception:
        pass
    return texts


def evaluate_checkpoint(
    checkpoint_path: str | Path | None = None,
    *,
    val_path: str | Path | None = None,
    max_examples: int = 200,
) -> dict[str, Any]:
    """Evaluate a checkpoint and return perplexity + metadata.

    Parameters
    ----------
    checkpoint_path:
        Path to the `.pt` checkpoint file.  Defaults to the production
        checkpoint (``checkpoints/doof_v01.pt`` or latest step file).
    val_path:
        Path to a JSONL validation file.  Defaults to the most recent one
        in ``datasets/``.
    max_examples:
        Cap on number of validation examples to evaluate (for speed).

    Returns
    -------
    dict with keys: ``perplexity``, ``nll``, ``n_tokens``, ``n_examples``,
    ``checkpoint``, ``timestamp``, ``status``.
    """
    result: dict[str, Any] = {
        "checkpoint": str(checkpoint_path) if checkpoint_path else None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "ok",
        "perplexity": None,
        "nll": None,
        "n_tokens": 0,
        "n_examples": 0,
    }

    try:
        import torch
        import torch.nn.functional as F
        from doof.inference import DOOFInference

        # Resolve checkpoint
        if checkpoint_path is None:
            candidates = [CKPT_DIR / "doof_v01.pt"] + sorted(
                CKPT_DIR.glob("doof_step_*.pt")
            )
            existing = [c for c in candidates if c.exists()]
            if not existing:
                result["status"] = "no_checkpoint"
                return result
            checkpoint_path = existing[-1]

        result["checkpoint"] = str(checkpoint_path)

        inf = DOOFInference(str(checkpoint_path))
        inf.model.eval()

        texts = _load_val_examples(val_path)
        if not texts:
            result["status"] = "no_validation_data"
            return result

        texts = texts[:max_examples]
        total_nll = 0.0
        total_tokens = 0

        with torch.no_grad():
            for text in texts:
                ids = inf.tokenizer.encode(text)
                if len(ids) < 2:
                    continue
                x = torch.tensor([ids[:-1]], dtype=torch.long, device=inf.device)
                y = torch.tensor([ids[1:]], dtype=torch.long, device=inf.device)
                logits = inf.model(x)
                nll = F.cross_entropy(
                    logits.reshape(-1, logits.size(-1)),
                    y.reshape(-1),
                    reduction="sum",
                )
                total_nll += float(nll.item())
                total_tokens += len(ids) - 1

        if total_tokens == 0:
            result["status"] = "no_tokens"
            return result

        mean_nll = total_nll / total_tokens
        perplexity = math.exp(min(mean_nll, 20.0))  # cap at e^20 to avoid inf

        result.update(
            {
                "perplexity": round(perplexity, 4),
                "nll": round(mean_nll, 6),
                "n_tokens": total_tokens,
                "n_examples": len(texts),
            }
        )

    except FileNotFoundError as e:
        result["status"] = f"file_not_found: {e}"
    except ImportError as e:
        result["status"] = f"import_error: {e}"
    except Exception as e:
        result["status"] = f"error: {e}"

    # Append to eval log
    _append_eval_log(result)
    return result


def _append_eval_log(result: dict[str, Any]) -> None:
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing: list[dict] = []
        if EVAL_LOG.exists():
            existing = json.loads(EVAL_LOG.read_text(encoding="utf-8"))
        existing.append(result)
        EVAL_LOG.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def get_eval_history() -> list[dict[str, Any]]:
    """Return all past evaluation results, newest first."""
    if not EVAL_LOG.exists():
        return []
    try:
        items = json.loads(EVAL_LOG.read_text(encoding="utf-8"))
        return list(reversed(items))
    except Exception:
        return []
