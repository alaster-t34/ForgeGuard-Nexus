#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
docker compose -f compose.yaml down
