#!/usr/bin/env bash
set -Eeuo pipefail
curl -fsS -X POST http://127.0.0.1:${FORGEGUARD_PORT:-8000}/api/v1/demo/reset -H 'Content-Type: application/json' -d '{}'
