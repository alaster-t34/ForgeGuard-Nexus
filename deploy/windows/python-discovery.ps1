function Set-ForgeGuardUtf8Environment {
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    try { [Console]::InputEncoding = $Utf8NoBom } catch { }
    try { [Console]::OutputEncoding = $Utf8NoBom } catch { }
    $global:OutputEncoding = $Utf8NoBom
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
}

function Read-ForgeGuardUtf8FirstLine {
    param([Parameter(Mandatory = $true)][string]$Path)
    $Value = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    return (($Value -split "`r?`n", 2)[0]).Trim().TrimStart([char]0xFEFF)
}

function Test-ForgeGuardPythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Prefix = @(),
        [string]$Source = "unknown",
        [int]$Order = 0
    )

    try {
        $Code = "import json,platform,sys; print(json.dumps({'major':sys.version_info.major,'minor':sys.version_info.minor,'version':platform.python_version(),'executable':sys.executable,'implementation':platform.python_implementation()}, ensure_ascii=True))"
        $Output = & $Executable @Prefix -c $Code 2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -ne 0 -or -not $Output) { return $null }
        $Info = $Output | ConvertFrom-Json
        if ($Info.implementation -ne "CPython") { return $null }
        if ($Info.major -ne 3 -or $Info.minor -notin @(11, 12)) { return $null }
        return [pscustomobject]@{
            Executable = $Executable
            Prefix = [string[]]$Prefix
            Version = [string]$Info.version
            Major = [int]$Info.major
            Minor = [int]$Info.minor
            Interpreter = [string]$Info.executable
            Source = $Source
            Order = $Order
        }
    } catch {
        return $null
    }
}

function Find-ForgeGuardPython {
    Set-ForgeGuardUtf8Environment
    $Candidates = New-Object System.Collections.Generic.List[object]
    $Seen = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)
    $script:ForgeGuardPythonCandidateOrder = 0

    function Add-ForgeGuardPythonCandidate {
        param([string]$Executable, [string[]]$Prefix = @(), [string]$Source)
        if (-not $Executable) { return }
        $Resolved = $Executable
        if (-not [System.IO.Path]::IsPathRooted($Executable)) {
            $Command = Get-Command $Executable -ErrorAction SilentlyContinue | Select-Object -First 1
            if (-not $Command) { return }
            $Resolved = $Command.Source
        } elseif (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
            return
        }
        $Key = "$Resolved|$($Prefix -join ' ')"
        if ($Seen.Add($Key)) {
            $script:ForgeGuardPythonCandidateOrder += 1
            $Candidates.Add([pscustomobject]@{
                Executable = $Resolved
                Prefix = [string[]]$Prefix
                Source = $Source
                Order = $script:ForgeGuardPythonCandidateOrder
            })
        }
    }

    if ($env:FORGEGUARD_PYTHON) {
        Add-ForgeGuardPythonCandidate -Executable $env:FORGEGUARD_PYTHON -Source "FORGEGUARD_PYTHON"
    }

    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($PyLauncher) {
        Add-ForgeGuardPythonCandidate -Executable $PyLauncher.Source -Prefix @("-3.12") -Source "Python launcher 3.12"
        Add-ForgeGuardPythonCandidate -Executable $PyLauncher.Source -Prefix @("-3.11") -Source "Python launcher 3.11"
    }

    if ($env:LOCALAPPDATA) {
        Add-ForgeGuardPythonCandidate -Executable (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe") -Source "per-user Python 3.12"
        Add-ForgeGuardPythonCandidate -Executable (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe") -Source "per-user Python 3.11"
    }
    foreach ($Base in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if ($Base) {
            Add-ForgeGuardPythonCandidate -Executable (Join-Path $Base "Python312\python.exe") -Source "system Python 3.12"
            Add-ForgeGuardPythonCandidate -Executable (Join-Path $Base "Python311\python.exe") -Source "system Python 3.11"
        }
    }

    $ActivePython = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($ActivePython) {
        Add-ForgeGuardPythonCandidate -Executable $ActivePython.Source -Source "PATH python"
    }

    $CondaRoots = New-Object System.Collections.Generic.List[string]
    foreach ($Root in @(
        $env:CONDA_PREFIX,
        $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE "anaconda3" }),
        $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE "miniconda3" }),
        $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE "miniforge3" }),
        "C:\ProgramData\anaconda3",
        "C:\ProgramData\miniconda3"
    )) {
        if ($Root -and (Test-Path -LiteralPath $Root -PathType Container)) { $CondaRoots.Add($Root) }
    }

    $CondaCommand = if ($env:CONDA_EXE -and (Test-Path -LiteralPath $env:CONDA_EXE)) {
        $env:CONDA_EXE
    } else {
        $FoundConda = Get-Command conda -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($FoundConda) { $FoundConda.Source } else { $null }
    }
    if ($CondaCommand) {
        try {
            $CondaInfo = (& $CondaCommand env list --json 2>$null) -join "`n" | ConvertFrom-Json
            foreach ($EnvironmentPath in $CondaInfo.envs) {
                if ($EnvironmentPath -and (Test-Path -LiteralPath $EnvironmentPath -PathType Container)) {
                    $CondaRoots.Add([string]$EnvironmentPath)
                }
            }
        } catch { }
    }
    foreach ($Root in @($CondaRoots | Select-Object -Unique)) {
        Add-ForgeGuardPythonCandidate -Executable (Join-Path $Root "python.exe") -Source "Conda environment"
        $Envs = Join-Path $Root "envs"
        if (Test-Path -LiteralPath $Envs -PathType Container) {
            foreach ($Environment in Get-ChildItem -LiteralPath $Envs -Directory -ErrorAction SilentlyContinue) {
                Add-ForgeGuardPythonCandidate -Executable (Join-Path $Environment.FullName "python.exe") -Source "Conda named environment"
            }
        }
    }

    foreach ($Minor in @("3.12", "3.11")) {
        foreach ($RegistryPath in @(
            "HKCU:\Software\Python\PythonCore\$Minor\InstallPath",
            "HKLM:\Software\Python\PythonCore\$Minor\InstallPath",
            "HKLM:\Software\WOW6432Node\Python\PythonCore\$Minor\InstallPath"
        )) {
            try {
                $InstallPath = (Get-Item -LiteralPath $RegistryPath -ErrorAction Stop).GetValue("")
                if ($InstallPath) {
                    Add-ForgeGuardPythonCandidate -Executable (Join-Path $InstallPath "python.exe") -Source "PythonCore registry $Minor"
                }
            } catch { }
        }
    }

    $Fallback = $null
    foreach ($Candidate in $Candidates) {
        $Result = Test-ForgeGuardPythonCandidate -Executable $Candidate.Executable -Prefix $Candidate.Prefix -Source $Candidate.Source -Order $Candidate.Order
        if (-not $Result) { continue }
        if ($Result.Source -eq "FORGEGUARD_PYTHON" -or $Result.Minor -eq 12) {
            return $Result
        }
        if (-not $Fallback) { $Fallback = $Result }
    }
    return $Fallback
}
