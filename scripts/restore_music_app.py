#!/usr/bin/env python3
"""Fail the build if App.tsx is a placeholder. Do not silently ship a broken UI."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
app = root / "frontend" / "src" / "App.tsx"
text = app.read_text(encoding="utf-8", errors="replace").strip() if app.is_file() else ""
if len(text) < 500 or text in {"PLACEHOLDER", "PLACEHOLDER_WILL_FAIL"}:
    print("ERROR: frontend/src/App.tsx is a placeholder. Restore the real UI before packaging.")
    sys.exit(1)
print("App.tsx looks valid", len(text), "bytes")
