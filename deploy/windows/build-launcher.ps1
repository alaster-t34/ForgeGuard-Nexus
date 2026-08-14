$ErrorActionPreference = "Stop"
$Root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $Root
. (Join-Path $PSScriptRoot "python-discovery.ps1")
Set-ForgeGuardUtf8Environment
if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
  throw "Go 1.23+ is required to rebuild the Windows launcher. Prebuilt EXE files are in dist\windows."
}
New-Item -ItemType Directory -Force dist\windows | Out-Null
$env:GOCACHE = if ($env:GOCACHE) { $env:GOCACHE } else { Join-Path ([System.IO.Path]::GetTempPath()) "forgeguard-go-build-cache" }
New-Item -ItemType Directory -Force $env:GOCACHE | Out-Null
$env:CGO_ENABLED = "0"
go build -trimpath -ldflags "-s -w -H windowsgui" -o dist\windows\ForgeGuard-Nexus.exe windows-launcher\main_windows.go
if ($LASTEXITCODE -ne 0) { throw "Failed to build ForgeGuard-Nexus.exe" }
Copy-Item dist\windows\ForgeGuard-Nexus.exe dist\windows\ForgeGuard-Nexus-Desktop.exe -Force
Copy-Item dist\windows\ForgeGuard-Nexus.exe dist\windows\ForgeGuard-Nexus-Stop.exe -Force
go build -trimpath -ldflags "-s -w" -o dist\windows\ForgeGuard-Native-Setup.exe windows-launcher\setup_windows.go
if ($LASTEXITCODE -ne 0) { throw "Failed to build ForgeGuard-Native-Setup.exe" }
Write-Host "Built desktop, stop, and visible native-environment setup launchers in dist\windows" -ForegroundColor Green
