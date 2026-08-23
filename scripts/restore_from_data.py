#!/usr/bin/env python3
import base64, zlib, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
# Prefer segment files App.tsx.b64.s0..sn
segs = sorted(root.glob("data/App.tsx.b64.s*"), key=lambda p: p.name)
if segs:
    joined = "".join(p.read_text().replace("\n", "") for p in segs)
    (root / "data/App.tsx.b64").write_text(joined)
    print("joined segments", len(joined), "from", len(segs), "files")
for src, dest in [("data/api.py.b64", "doof/api.py"), ("data/App.tsx.b64", "frontend/src/App.tsx")]:
    p_src = root / src
    if not p_src.exists():
        print("skip", src); continue
    try:
        raw = zlib.decompress(base64.b64decode(p_src.read_text().replace("\n", "")))
        p = root / dest
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        print("restored", dest, p.stat().st_size)
    except Exception as e:
        print("failed", src, e)
