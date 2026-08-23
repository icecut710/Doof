#!/usr/bin/env python3
import base64, zlib, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
parts = sorted(root.glob("data/App.tsx.b64.part*"))
if parts:
    joined = "".join(p.read_text().replace("\n", "") for p in parts)
    (root / "data/App.tsx.b64").write_text(joined)
    print("joined App.tsx.b64", len(joined))
for src, dest in [("data/api.py.b64", "doof/api.py"), ("data/App.tsx.b64", "frontend/src/App.tsx")]:
    p_src = root / src
    if not p_src.exists():
        print("skip missing", src)
        continue
    b64 = p_src.read_text().replace("\n", "")
    p = root / dest
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(zlib.decompress(base64.b64decode(b64)))
    print("restored", dest, p.stat().st_size)
