$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker Desktop is required. Alternatively run deploy/windows/install-native.ps1."
}
docker compose version | Out-Null
New-Item -ItemType Directory -Force runtime-data, artifacts | Out-Null
docker compose -f compose.yaml up -d --build api
Write-Host "ForgeGuard is starting at http://localhost:8000" -ForegroundColor Cyan
