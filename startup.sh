#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DOOF_API_HOST="${DOOF_API_HOST:-0.0.0.0}"

if curl -sf -o /dev/null --max-time 1 "http://127.0.0.1:8080/" 2>/dev/null; then
  echo "DOOF already up"
  exit 0
fi

echo "Starting DOOF API on :8765..."
python3 -m doof serve --host 0.0.0.0 --port 8765 >/tmp/doof-api.log 2>&1 &
sleep 1

echo "Starting frontend on :8080..."
cd frontend
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev -- --host 0.0.0.0 --port 8080
