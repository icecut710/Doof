#!/usr/bin/env python3
import base64, zlib, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
for src, dest in [("data/api.py.b64", "doof/api.py"), ("data/App.tsx.b64", "frontend/src/App.tsx")]:
    b64 = (root / src).read_text().replace("\n", "")
    p = root / dest
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(zlib.decompress(base64.b64decode(b64)))
    print("restored", dest, p.stat().st_size)
