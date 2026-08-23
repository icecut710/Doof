#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 scripts/install_v02_a.py
python3 scripts/install_v02_b.py
echo ""
echo "DOOF v0.2 intelligence + API installed."
echo "Restart: python -m doof serve"
