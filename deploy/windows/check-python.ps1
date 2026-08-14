$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "python-discovery.ps1")
Set-ForgeGuardUtf8Environment

$Python = Find-ForgeGuardPython
if (-not $Python) {
    Write-Error "No compatible CPython 3.12/3.11 installation was found. Set FORGEGUARD_PYTHON to an explicit python.exe path if needed."
}

$CommandParts = @($Python.Executable) + @($Python.Prefix)
[pscustomobject]@{
    Supported = $true
    Version = $Python.Version
    Interpreter = $Python.Interpreter
    Source = $Python.Source
    Command = ($CommandParts -join " ").Trim()
} | Format-List
