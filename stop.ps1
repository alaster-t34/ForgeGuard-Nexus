$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
docker compose -f compose.yaml down
