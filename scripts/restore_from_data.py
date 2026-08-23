#!/usr/bin/env python3
"""Restore DOOF critical sources from data/*.b64 if missing."""
import base64
import re
import zlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def restore_b64(b64: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(zlib.decompress(base64.b64decode(b64.replace("\n", ""))))
    print("restored", dest, dest.stat().st_size)


api_dest = root / "doof" / "api.py"
api_b64 = root / "data" / "api.py.b64"
if not api_dest.exists() or api_dest.stat().st_size < 1000:
    if api_b64.exists():
        restore_b64(api_b64.read_text(), api_dest)
    else:
        print("missing data/api.py.b64")
else:
    print("skip (exists)", api_dest, api_dest.stat().st_size)

app_dest = root / "frontend" / "src" / "App.tsx"
need = True
if app_dest.exists() and app_dest.stat().st_size > 8000:
    head = app_dest.read_text(encoding="utf-8", errors="ignore")[:300]
    if "Atmosphere" in head or "StarField" in head:
        print("skip (exists premium UI)", app_dest, app_dest.stat().st_size)
        need = False

if need:
    parts = sorted(
        [p for p in root.glob("data/App.tsx.b64.p*") if re.match(r"App\.tsx\.b64\.p\d+$", p.name)],
        key=lambda p: int(re.search(r"p(\d+)$", p.name).group(1)),
    )
    if parts:
        b64 = "".join(p.read_text().strip() for p in parts)
        restore_b64(b64, app_dest)
    else:
        print("missing App.tsx payload parts data/App.tsx.b64.p0..")

print("Done.")
