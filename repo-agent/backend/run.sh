#!/usr/bin/env bash
# Launch the RepoAgent backend (serves the API and the static preview at /preview).
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080 "$@"
