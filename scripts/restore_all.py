#!/usr/bin/env python3
"""Restore DOOF v0.1 critical source files."""
import runpy
from pathlib import Path
root = Path(__file__).resolve().parent
for name in ("restore_api.py", "restore_app.py"):
    runpy.run_path(str(root / name))
print("All restored. Then: cd frontend && npm i && npm run build && python -m doof train")
