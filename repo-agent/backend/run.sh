#!/usr/bin/env bash
# Launch RepoAgent using its dedicated Conda environment.
set -euo pipefail

cd "$(dirname "$0")"

CONDA_ENV_NAME="${REPO_AGENT_CONDA_ENV:-repo-agent}"
UVICORN_ARGS=(app.main:app --host 127.0.0.1 --port 8080 "$@")

if [[ "${CONDA_DEFAULT_ENV:-}" == "$CONDA_ENV_NAME" ]]; then
  echo "Starting RepoAgent backend in active Conda environment: $CONDA_ENV_NAME"
  exec python -m uvicorn "${UVICORN_ARGS[@]}"
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: Conda is not available and '$CONDA_ENV_NAME' is not active." >&2
  echo "Activate it first: conda activate $CONDA_ENV_NAME" >&2
  exit 1
fi

if ! conda run -n "$CONDA_ENV_NAME" python -c "import fastapi, uvicorn, pydantic" >/dev/null 2>&1; then
  echo "Error: Conda environment '$CONDA_ENV_NAME' is missing or incomplete." >&2
  echo "Create/update it from repo-agent/:" >&2
  echo "  conda env update -f environment.yml --prune" >&2
  exit 1
fi

echo "Conda environment '$CONDA_ENV_NAME' is not active; launching through conda run."
exec conda run --no-capture-output -n "$CONDA_ENV_NAME" \
  python -m uvicorn "${UVICORN_ARGS[@]}"
