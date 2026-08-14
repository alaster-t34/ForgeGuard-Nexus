#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
RUNTIME_HOME="${FORGEGUARD_RUNTIME_HOME:-$DATA_HOME/forgeguard-nexus}"
RUNTIME_POINTER="$RUNTIME_HOME/venv-path.txt"
STATE_HELPER="$ROOT/scripts/native_env.py"

if [ -n "${FORGEGUARD_VENV_DIR:-}" ]; then
  VENV_DIR="$FORGEGUARD_VENV_DIR"
elif [ -s "$RUNTIME_POINTER" ]; then
  IFS= read -r VENV_DIR < "$RUNTIME_POINTER"
elif [ -s "$ROOT/.venv-path.txt" ]; then
  IFS= read -r VENV_DIR < "$ROOT/.venv-path.txt"
else
  VENV_DIR="$RUNTIME_HOME/venv"
fi
if command -v realpath >/dev/null 2>&1; then
  VENV_DIR="$(realpath -m "$VENV_DIR")"
else
  VENV_DIR="$(python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$VENV_DIR")"
fi
PROJECT_LOCAL_VENV="$ROOT/.venv"
if [ "$VENV_DIR" = "$PROJECT_LOCAL_VENV" ]; then
  echo "Project-local .venv is deprecated; switching to persistent storage: $RUNTIME_HOME/venv"
  VENV_DIR="$RUNTIME_HOME/venv"
fi
VENV_PYTHON="$VENV_DIR/bin/python"

READY=0
if [ -x "$VENV_PYTHON" ] && "$VENV_PYTHON" "$STATE_HELPER" status --venv "$VENV_DIR" --repair --quiet; then
  READY=1
fi
if [ "$READY" -eq 0 ]; then
  echo "Persistent native environment is missing or dependencies genuinely changed; synchronizing once."
  FORGEGUARD_VENV_DIR="$VENV_DIR" bash deploy/linux/install-native.sh
fi

if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: persistent environment interpreter is missing: $VENV_PYTHON" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/backend:$ROOT/edge-node${PYTHONPATH:+:$PYTHONPATH}"
exec "$VENV_PYTHON" -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${FORGEGUARD_PORT:-8000}"
