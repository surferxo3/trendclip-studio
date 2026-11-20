$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "TrendClip needs its one-time setup. Run Setup TrendClip Studio.bat first."
    Read-Host "Press Enter to close"
    exit 1
}

Set-Location $ProjectDir
& $Python -m trendclip studio
