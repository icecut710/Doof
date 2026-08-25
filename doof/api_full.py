"""Full DOOF HTTP API implementation (assembled from _af*.txt segments)."""
from __future__ import annotations
from pathlib import Path
_parts = sorted(Path(__file__).resolve().parent.glob("_af*.txt"))
if not _parts:
    raise ImportError("DOOF api_full segments (_af*.txt) missing")
_code = "".join(p.read_text(encoding="utf-8") for p in _parts)
exec(compile(_code, str(Path(__file__).resolve()), "exec"), globals())
