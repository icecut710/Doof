#!/usr/bin/env python3
from pathlib import Path
import base64, zlib
ROOT = Path(__file__).resolve().parents[1]
parts = [(ROOT / "data" / f"api_chunk_{i}.b64").read_text().strip() for i in range(4)]
raw = zlib.decompress(base64.b64decode("".join(parts)))
(ROOT / "doof" / "api.py").write_bytes(raw)
print("api", len(raw))
