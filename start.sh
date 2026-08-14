#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for the recommended portable deployment."
  echo "Use deploy/linux/install-native.sh for a local Python deployment."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required."
  exit 1
fi
mkdir -p runtime-data artifacts
FREE_GB=$(df -Pk . | awk 'NR==2 {print int($4/1024/1024)}')
if [ "$FREE_GB" -lt 6 ]; then
  echo "At least 6 GB free disk space is required; ${FREE_GB} GB detected."
  exit 1
fi
docker compose -f compose.yaml up -d --build api
echo "ForgeGuard is starting: http://localhost:${FORGEGUARD_PORT:-8000}"
