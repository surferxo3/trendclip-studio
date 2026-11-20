$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

Set-Location $ProjectDir

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    Write-Host "FFmpeg and ffprobe are required."
    Write-Host "Run: winget install --id Gyan.FFmpeg -e"
    Write-Host "Then open a new terminal and run this setup again."
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js LTS is required for reliable YouTube access."
    Write-Host "Run: winget install OpenJS.NodeJS.LTS"
    Write-Host "Then open a new terminal and run this setup again."
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path $VenvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        Write-Host "Python 3.10 or newer is required: https://www.python.org/downloads/"
        Read-Host "Press Enter to close"
        exit 1
    }
}

& $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.10 or newer is required. Delete .venv after installing it, then run setup again."
    Read-Host "Press Enter to close"
    exit 1
}

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -e $ProjectDir
& $VenvPython -m trendclip doctor

Write-Host ""
Read-Host "Setup complete. Press Enter to close"
