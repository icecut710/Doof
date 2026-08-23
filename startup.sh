#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
echo "Starting DOOF API on :8765..."
python3 -m doof serve &
API_PID=$!
cleanup() { kill $API_PID 2>/dev/null || true; }
trap cleanup EXIT
sleep 1
if [ ! -d frontend/dist ]; then
  echo "Building frontend..."
  (cd frontend && npm install && npm run build)
fi
echo "Starting frontend on :8080..."
(cd frontend && npm run preview -- --host 127.0.0.1 --port 8080)
