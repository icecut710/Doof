"""Full DOOF HTTP API (zlib+base64 body in _api_full_{a,b}.z64)."""
from __future__ import annotations
import base64, zlib
from pathlib import Path
_dir = Path(__file__).resolve().parent
_blob = (_dir / "_api_full_a.z64").read_text(encoding="ascii") + (_dir / "_api_full_b.z64").read_text(encoding="ascii")
_code = zlib.decompress(base64.b64decode(_blob)).decode("utf-8")
exec(compile(_code, str(Path(__file__).resolve()), "exec"), globals())
