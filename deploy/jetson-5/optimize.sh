#!/usr/bin/env bash
set -Eeuo pipefail
sudo install -d -m 0755 /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"},
  "default-shm-size": "1G"
}
JSON
sudo systemctl restart docker
sudo sysctl -w fs.inotify.max_user_watches=524288
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
if [ "${1:-}" = "--max-clocks" ]; then
  sudo jetson_clocks
fi
echo "Jetson runtime optimization applied."
