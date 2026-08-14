#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

FORCE=0
RECREATE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --recreate) RECREATE=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash deploy/linux/install-native.sh [--force] [--recreate]

The Python environment is stored outside the extracted project and reused by
all later ForgeGuard versions:
  ${XDG_DATA_HOME:-$HOME/.local/share}/forgeguard-nexus/venv

--force      Re-check and synchronize dependencies without deleting the venv.
--recreate   Delete and recreate the persistent environment.

Overrides:
  FORGEGUARD_RUNTIME_HOME=/path/to/runtime
  FORGEGUARD_VENV_DIR=/path/to/venv
  FORGEGUARD_PYTHON=/path/to/python3.11
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
RUNTIME_HOME="${FORGEGUARD_RUNTIME_HOME:-$DATA_HOME/forgeguard-nexus}"
RUNTIME_POINTER="$RUNTIME_HOME/venv-path.txt"
STATE_HELPER="$ROOT/scripts/native_env.py"

if [ -n "${FORGEGUARD_VENV_DIR:-}" ]; then
  VENV_DIR="$FORGEGUARD_VENV_DIR"
elif [ -s "$RUNTIME_POINTER" ]; then
  IFS= read -r VENV_DIR < "$RUNTIME_POINTER"
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
PIP_CACHE_DIR="${PIP_CACHE_DIR:-$RUNTIME_HOME/pip-cache}"
export PIP_CACHE_DIR

mkdir -p "$RUNTIME_HOME" "$(dirname "$VENV_DIR")" "$PIP_CACHE_DIR"

write_pointers_and_link() {
  printf '%s\n' "$VENV_DIR" > "$RUNTIME_POINTER"
  printf '%s\n' "$VENV_DIR" > "$ROOT/.venv-path.txt"

  if [ -L "$ROOT/.venv" ]; then
    rm -f "$ROOT/.venv"
  elif [ -e "$ROOT/.venv" ]; then
    local backup="$RUNTIME_HOME/legacy-project-venv-$(date +%Y%m%d-%H%M%S)"
    echo "Moving redundant project-local .venv to: $backup"
    mv "$ROOT/.venv" "$backup"
  fi
  ln -s "$VENV_DIR" "$ROOT/.venv" 2>/dev/null || true
}

# Migrate an older real project-local environment before creating anything new.
if [ ! -x "$VENV_DIR/bin/python" ] && [ -d "$ROOT/.venv" ] && [ ! -L "$ROOT/.venv" ] && [ -x "$ROOT/.venv/bin/python" ]; then
  echo "Migrating legacy project-local .venv into persistent storage: $VENV_DIR"
  mv "$ROOT/.venv" "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

# The existing venv can validate itself. A separately installed host Python is
# not required on the fast reuse path.
if [ "$RECREATE" -eq 0 ] && [ "$FORCE" -eq 0 ] && [ -x "$VENV_PYTHON" ]; then
  if "$VENV_PYTHON" "$STATE_HELPER" status --venv "$VENV_DIR" --repair --quiet; then
    write_pointers_and_link
    echo "ForgeGuard native environment is already current."
    echo "Reused: $VENV_DIR"
    echo "Dependency installation skipped."
    exit 0
  fi
fi

PYTHON_BIN="${FORGEGUARD_PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  for candidate in python3.11 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
      fi
    fi
  done
fi

if [ "$RECREATE" -eq 1 ] && [ -e "$VENV_DIR" ]; then
  echo "Recreating persistent environment: $VENV_DIR"
  rm -rf -- "$VENV_DIR"
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: the environment needs synchronization, but CPython 3.11/3.12 was not found." >&2
  echo "Install Python 3.11/3.12, use Docker, or set FORGEGUARD_PYTHON." >&2
  exit 1
fi

VENV_PYTHON="$VENV_DIR/bin/python"
if [ -x "$VENV_PYTHON" ]; then
  if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)' >/dev/null 2>&1; then
    echo "Existing environment uses an incompatible Python; recreating it."
    rm -rf -- "$VENV_DIR"
  fi
fi

CREATED=0
VENV_PYTHON="$VENV_DIR/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "Creating persistent environment once: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  CREATED=1
else
  # Refresh standard venv launchers after migrating an old project-local venv.
  "$PYTHON_BIN" -m venv --upgrade "$VENV_DIR" >/dev/null 2>&1 || true
fi

VENV_PYTHON="$VENV_DIR/bin/python"
if [ "$CREATED" -eq 1 ]; then
  "$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade pip
fi

# Synchronize in place. The venv is not deleted, and the persistent cache avoids
# repeat downloads when a dependency genuinely changes.
"$VENV_PYTHON" -m pip install --disable-pip-version-check --prefer-binary \
  -r backend/requirements.lock.txt \
  -r edge-node/requirements.lock.txt

"$VENV_PYTHON" "$STATE_HELPER" verify --venv "$VENV_DIR"
"$VENV_PYTHON" "$STATE_HELPER" write --venv "$VENV_DIR" --quiet
write_pointers_and_link

echo "ForgeGuard native environment is ready."
echo "Persistent path: $VENV_DIR"
echo "Pip cache: $PIP_CACHE_DIR"
echo "Later project packages will reuse this environment automatically."
