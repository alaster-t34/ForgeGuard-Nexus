$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
. (Join-Path $PSScriptRoot "python-discovery.ps1")
Set-ForgeGuardUtf8Environment

if ($env:FORGEGUARD_RUNTIME_HOME) {
    $RuntimeHome = [System.IO.Path]::GetFullPath($env:FORGEGUARD_RUNTIME_HOME)
} else {
    $RuntimeHome = Join-Path $env:LOCALAPPDATA "ForgeGuardNexus"
}
$RuntimePointer = Join-Path $RuntimeHome "venv-path.txt"
$ProjectPointer = Join-Path $Root ".venv-path.txt"

if ($env:FORGEGUARD_VENV_DIR) {
    $VenvDir = [System.IO.Path]::GetFullPath($env:FORGEGUARD_VENV_DIR)
} elseif (Test-Path $RuntimePointer) {
    $VenvDir = [System.IO.Path]::GetFullPath((Read-ForgeGuardUtf8FirstLine -Path $RuntimePointer))
} elseif (Test-Path $ProjectPointer) {
    $VenvDir = [System.IO.Path]::GetFullPath((Read-ForgeGuardUtf8FirstLine -Path $ProjectPointer))
} else {
    $VenvDir = Join-Path $RuntimeHome "venv"
}
$ProjectLocalVenv = [System.IO.Path]::GetFullPath((Join-Path $Root ".venv"))
if ($VenvDir -eq $ProjectLocalVenv) {
    $VenvDir = Join-Path $RuntimeHome "venv"
}
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$StateHelper = Join-Path $Root "scripts\native_env.py"

$Ready = $false
if (Test-Path $VenvPython) {
    & $VenvPython $StateHelper status --venv $VenvDir --repair --quiet
    $Ready = ($LASTEXITCODE -eq 0)
}

if (-not $Ready) {
    Write-Host "Persistent native environment is missing or dependencies genuinely changed; synchronizing once." -ForegroundColor Yellow
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "deploy\windows\install-native.ps1") -VenvDir $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Native environment installation failed." }
}

if (-not (Test-Path $VenvPython)) {
    throw "Persistent environment interpreter is missing: $VenvPython"
}

$env:PYTHONPATH = "$Root\backend;$Root\edge-node" + $(if ($env:PYTHONPATH) { ";$env:PYTHONPATH" } else { "" })
& $VenvPython -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $(if ($env:FORGEGUARD_PORT) { $env:FORGEGUARD_PORT } else { "8000" })
