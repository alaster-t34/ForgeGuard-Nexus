#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
bash deploy/jetson-5/preflight.sh
export FORGEGUARD_DEPLOYMENT_PROFILE=jetson-orin-jp622
export FORGEGUARD_PLATFORM_NAME="NVIDIA Jetson Orin"
export FORGEGUARD_PORT="${FORGEGUARD_PORT:-8000}"
docker compose -f compose.yaml up -d --build api
echo "ForgeGuard Jetson console: http://localhost:${FORGEGUARD_PORT}"
