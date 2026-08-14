#!/usr/bin/env bash
set -Eeuo pipefail
printf 'ForgeGuard Jetson preflight\n'
[ -f /etc/nv_tegra_release ] || { echo 'FAIL: not a Jetson L4T system'; exit 1; }
cat /etc/nv_tegra_release
command -v docker >/dev/null || { echo 'FAIL: Docker missing'; exit 1; }
docker compose version >/dev/null || { echo 'FAIL: Docker Compose v2 missing'; exit 1; }
python3 -c 'import tensorrt as trt; print("TensorRT", trt.__version__)' || echo 'WARN: host TensorRT Python API unavailable'
FREE_GB=$(df -Pk "$(pwd)" | awk 'NR==2 {print int($4/1024/1024)}')
[ "$FREE_GB" -ge 8 ] || { echo "FAIL: 8 GB free required; ${FREE_GB} GB available"; exit 1; }
echo 'PASS: Jetson platform ready'
