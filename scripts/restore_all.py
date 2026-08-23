#!/usr/bin/env python3
"""Restore DOOF v0.1 critical source files."""
import runpy
from pathlib import Path
root = Path(__file__).resolve().parent
runpy.run_path(str(root / "restore_from_data.py"))
print("Done. Then: python -m doof train && cd frontend && npm i && npm run build")
