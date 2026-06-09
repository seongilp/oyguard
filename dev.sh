#!/usr/bin/env bash
# Start backend (FastAPI) and frontend (Next.js) together for local development.
# Usage: ./dev.sh            (real tools)
#        DEMO=1 ./dev.sh     (backend demo mode, no images pulled)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "▶ backend  → http://localhost:8000  (docs: /docs)"
(
  cd "$ROOT/backend"
  uv sync --quiet
  OYGUARD_DEMO_MODE="${DEMO:-false}" uv run uvicorn app.main:app --reload --port 8000
) &

echo "▶ frontend → http://localhost:4000"
(
  cd "$ROOT/frontend"
  pnpm install --silent
  pnpm dev --port 4000
) &

wait
