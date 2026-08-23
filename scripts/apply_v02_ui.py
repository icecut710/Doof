#!/usr/bin/env python3
from pathlib import Path
import base64, zlib
ROOT = Path(__file__).resolve().parents[1]
parts = [(ROOT / "data" / f"app_chunk_{i}.b64").read_text().strip() for i in range(5)]
raw = zlib.decompress(base64.b64decode("".join(parts)))
(ROOT / "frontend" / "src" / "App.tsx").write_bytes(raw)
print("ui", len(raw))
