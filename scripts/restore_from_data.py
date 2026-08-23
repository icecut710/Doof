#!/usr/bin/env python3
"""Restore DOOF critical sources from data/*.b64 if missing."""
import base64, zlib
from pathlib import Path
root = Path(__file__).resolve().parents[1]
pairs = [
    ("data/api.py.b64", "doof/api.py"),
    ("data/App.tsx.b64", "frontend/src/App.tsx"),
]
for src, dest in pairs:
    sp, dp = root / src, root / dest
    if dp.exists() and dp.stat().st_size > 1000:
        print("skip (exists)", dest, dp.stat().st_size)
        continue
    if not sp.exists():
        if "App" in src:
            segs = sorted(root.glob("data/App.tsx.b64.s*"))
            if segs:
                b64 = "".join(s.read_text().strip() for s in segs)
                dp.parent.mkdir(parents=True, exist_ok=True)
                dp.write_bytes(zlib.decompress(base64.b64decode(b64)))
                print("restored from segments", dest, dp.stat().st_size)
                continue
        print("missing", src)
        continue
    b64 = sp.read_text().replace("\n", "")
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_bytes(zlib.decompress(base64.b64decode(b64)))
    print("restored", dest, dp.stat().st_size)
print("Done.")
