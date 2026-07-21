#!/usr/bin/env bash
# Run FastAPI and Angular together for local development.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID"
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "${CONDA_DEFAULT_ENV:-}" != "repo-agent" ]]; then
  echo "Warning: expected Conda environment 'repo-agent'; active environment is '${CONDA_DEFAULT_ENV:-none}'."
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run: cd $ROOT_DIR/frontend && npm install"
  exit 1
fi

echo "Starting backend at http://127.0.0.1:8080"
"$ROOT_DIR/backend/run.sh" &
BACKEND_PID=$!

echo "Starting Angular UI at http://localhost:4200"
cd "$ROOT_DIR/frontend"
npm start
