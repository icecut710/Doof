#!/usr/bin/env python3
import base64, zlib, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
# Join App payload: full App.tsx.b64 OR .a + .b0+.b1+.b2 OR parts
a = root / "data/App.tsx.b64.a"
b_parts = [root / f"data/App.tsx.b64.b{i}" for i in range(10)]
b_parts = [p for p in b_parts if p.exists()]
if a.exists() and b_parts:
    joined = a.read_text().replace("\n", "") + "".join(p.read_text().replace("\n", "") for p in b_parts)
    (root / "data/App.tsx.b64").write_text(joined)
    print("joined from a+b*", len(joined))
elif (root / "data/App.tsx.b64").exists():
    print("using existing App.tsx.b64", (root / "data/App.tsx.b64").stat().st_size)
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
