"""Full DOOF HTTP API (zlib+base64 body in _api_full.z64)."""
from __future__ import annotations
import base64, zlib
from pathlib import Path
_blob = Path(__file__).resolve().parent / "_api_full.z64"
_code = zlib.decompress(base64.b64decode(_blob.read_text(encoding="ascii"))).decode("utf-8")
exec(compile(_code, str(Path(__file__).resolve()), "exec"), globals())
