#!/usr/bin/env python3
"""Restore DOOF critical sources from data/*.b64 if missing."""
import base64
import zlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]

def restore_b64(b64: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(zlib.decompress(base64.b64decode(b64.replace("\n", ""))))
    print("restored", dest, dest.stat().st_size)

# api.py
api_dest = root / "doof" / "api.py"
api_b64 = root / "data" / "api.py.b64"
if not api_dest.exists() or api_dest.stat().st_size < 1000:
    if api_b64.exists():
        restore_b64(api_b64.read_text(), api_dest)
    else:
        print("missing data/api.py.b64")
else:
    print("skip (exists)", api_dest, api_dest.stat().st_size)

# App.tsx — prefer single file, else join a+b, else s* segments
app_dest = root / "frontend" / "src" / "App.tsx"
app_b64 = root / "data" / "App.tsx.b64"
app_a = root / "data" / "App.tsx.b64.a"
app_b = root / "data" / "App.tsx.b64.b"

if app_dest.exists() and app_dest.stat().st_size > 5000 and "useCallback" in app_dest.read_text(encoding="utf-8", errors="ignore")[:200]:
    print("skip (exists production)", app_dest, app_dest.stat().st_size)
elif app_a.exists() and app_b.exists():
    b64 = app_a.read_text().strip() + app_b.read_text().strip()
    restore_b64(b64, app_dest)
elif app_b64.exists():
    try:
        restore_b64(app_b64.read_text(), app_dest)
    except Exception as e:
        print("App.tsx.b64 failed:", e)
        segs = sorted(root.glob("data/App.tsx.b64.s*"))
        if segs:
            b64 = "".join(s.read_text().strip() for s in segs)
            restore_b64(b64, app_dest)
else:
    segs = sorted(root.glob("data/App.tsx.b64.s*"))
    if segs:
        b64 = "".join(s.read_text().strip() for s in segs)
        restore_b64(b64, app_dest)
    else:
        print("missing App.tsx payload")

print("Done.")
