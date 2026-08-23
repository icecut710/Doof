#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 scripts/apply_v02_api.py
python3 scripts/apply_v02_ui.py
echo "DOOF v0.2 Alpha sources applied. Restart API + rebuild frontend."
