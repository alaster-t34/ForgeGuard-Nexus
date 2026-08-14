param(
    [switch]$Force,
    [switch]$Recreate,
    [string]$VenvDir = ""
)

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

if (-not $VenvDir) {
    if ($env:FORGEGUARD_VENV_DIR) {
        $VenvDir = $env:FORGEGUARD_VENV_DIR
    } elseif (Test-Path $RuntimePointer) {
        $VenvDir = Read-ForgeGuardUtf8FirstLine -Path $RuntimePointer
    } else {
        $VenvDir = Join-Path $RuntimeHome "venv"
    }
}
$VenvDir = [System.IO.Path]::GetFullPath($VenvDir)
$ProjectLocalVenv = [System.IO.Path]::GetFullPath((Join-Path $Root ".venv"))
if ($VenvDir -eq $ProjectLocalVenv) {
    Write-Host "Project-local .venv is deprecated; switching to persistent storage." -ForegroundColor Yellow
    $VenvDir = Join-Path $RuntimeHome "venv"
}
$PipCache = if ($env:PIP_CACHE_DIR) { $env:PIP_CACHE_DIR } else { Join-Path $RuntimeHome "pip-cache" }
$env:PIP_CACHE_DIR = $PipCache
$StateHelper = Join-Path $Root "scripts\native_env.py"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$ProjectVenv = Join-Path $Root ".venv"

$HostPython = Find-ForgeGuardPython
$PythonExe = if ($HostPython) { $HostPython.Executable } else { $null }
$PythonPrefix = if ($HostPython) { @($HostPython.Prefix) } else { @() }

function Invoke-HostPython {
    param([string[]]$Arguments)
    if (-not $PythonExe) {
        throw "ForgeGuard native deployment requires CPython 3.11 or 3.12. Install Python 3.11/3.12 or use Docker Desktop."
    }
    & $PythonExe @PythonPrefix @Arguments
}

function Test-ReparsePoint {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    $Item = Get-Item -LiteralPath $Path -Force
    return [bool]($Item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Value)
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Value + [Environment]::NewLine, $Utf8NoBom)
}

function Set-ProjectVenvPointer {
    New-Item -ItemType Directory -Force -Path $RuntimeHome | Out-Null
    Write-Utf8NoBom -Path $RuntimePointer -Value $VenvDir
    Write-Utf8NoBom -Path (Join-Path $Root ".venv-path.txt") -Value $VenvDir

    if (Test-Path $ProjectVenv) {
        if (Test-ReparsePoint $ProjectVenv) {
            Remove-Item -Force $ProjectVenv
        } else {
            $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
            $Backup = Join-Path $RuntimeHome "legacy-project-venv-$Stamp"
            Write-Host "Moving redundant project-local .venv to: $Backup" -ForegroundColor Yellow
            Move-Item -Force $ProjectVenv $Backup
        }
    }
    try {
        New-Item -ItemType Junction -Path $ProjectVenv -Target $VenvDir -ErrorAction Stop | Out-Null
    } catch {
        # Scripts and the EXE use the stable pointer directly. The junction is an IDE convenience.
        Write-Host "Could not create the optional .venv junction: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

New-Item -ItemType Directory -Force -Path @($RuntimeHome, (Split-Path $VenvDir -Parent), $PipCache) | Out-Null

Write-Host "[1/4] Locating a reusable ForgeGuard Python environment..." -ForegroundColor Cyan
Write-Host "Persistent environment: $VenvDir"
Write-Host "Persistent pip cache: $PipCache"
if ($HostPython) {
    Write-Host "Detected host Python: $($HostPython.Version)"
    Write-Host "Interpreter: $($HostPython.Interpreter)"
    Write-Host "Discovery source: $($HostPython.Source)"
} else {
    Write-Host "No compatible host CPython was discovered yet; an existing verified environment can still be reused." -ForegroundColor Yellow
}
Write-Host ""

# Migrate a real project-local venv created by older releases before creating a new one.
$LegacyPython = Join-Path $ProjectVenv "Scripts\python.exe"
if (-not (Test-Path $VenvPython) -and (Test-Path $LegacyPython) -and -not (Test-ReparsePoint $ProjectVenv)) {
    Write-Host "Migrating legacy project-local .venv into persistent storage: $VenvDir" -ForegroundColor Cyan
    Move-Item -Force $ProjectVenv $VenvDir
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if ($PythonExe) {
        try { Invoke-HostPython -Arguments @("-m", "venv", "--upgrade", $VenvDir) } catch { }
    }
}

if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Host "Recreating persistent environment: $VenvDir" -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$CheckPython = if (Test-Path $VenvPython) { $VenvPython } else { $null }

# Repair/adopt an existing environment before invoking pip. This covers deleted
# state files, a newly extracted code folder and older environment schemas.
if (-not $Force -and $CheckPython) {
    Write-Host "[2/4] Verifying installed packages and portable model compatibility..." -ForegroundColor Cyan
    & $CheckPython $StateHelper status --venv $VenvDir --repair --quiet
    if ($LASTEXITCODE -eq 0) {
        Set-ProjectVenvPointer
        Write-Host "ForgeGuard native environment is already current." -ForegroundColor Green
        Write-Host "Reused: $VenvDir"
        Write-Host "Dependency installation skipped."
        exit 0
    }
}

if (-not $PythonExe) {
    throw "The persistent environment needs synchronization, but CPython 3.11/3.12 is not available. Install it or use Docker Desktop."
}

if (Test-Path $VenvPython) {
    & $VenvPython -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,13) else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Existing environment uses an incompatible Python; recreating it." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VenvDir
    }
}

$Created = $false
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    New-Item -ItemType Directory -Force (Split-Path $VenvDir -Parent) | Out-Null
    Write-Host "[2/4] Creating the persistent environment once: $VenvDir" -ForegroundColor Cyan
    Invoke-HostPython -Arguments @("-m", "venv", $VenvDir)
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the virtual environment." }
    $Created = $true
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if ($Created) {
    & $VenvPython -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
}

# Synchronize in place. The environment is not deleted, and the stable pip cache
# prevents repeat downloads when a dependency genuinely changes.
Write-Host "[3/4] Synchronizing locked dependencies. Existing correct packages will be reused." -ForegroundColor Cyan
& $VenvPython -m pip install --disable-pip-version-check --prefer-binary `
    -r (Join-Path $Root "backend\requirements.lock.txt") `
    -r (Join-Path $Root "edge-node\requirements.lock.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency synchronization failed." }

Write-Host "[4/4] Verifying Python, locked packages and the portable bundled model..." -ForegroundColor Cyan
& $VenvPython $StateHelper verify --venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw "Native environment verification failed." }
& $VenvPython $StateHelper write --venv $VenvDir --quiet
if ($LASTEXITCODE -ne 0) { throw "Failed to write native environment state." }

Set-ProjectVenvPointer
Write-Host "ForgeGuard native environment is ready." -ForegroundColor Green
Write-Host "Persistent path: $VenvDir"
Write-Host "Pip cache: $PipCache"
Write-Host "Later project packages will reuse this environment automatically."
