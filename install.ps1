param(
    [ValidateSet("AppData","ProgramFiles")]
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host "  FLX4 Control || Installer / Updater"
Write-Host "============================================================"
Write-Host ""

# ------------------------------------------------------------
# If running from TEMP → bootstrap full repo
# ------------------------------------------------------------
if ($PSScriptRoot -like "*AppData\Local\Temp*") {

    Write-Host "[Bootstrap] Downloading full repository..."

    $zipUrl = "https://github.com/TRC-Loop/flx4control/archive/refs/heads/main.zip"
    $zipPath = Join-Path $env:TEMP "flx4control.zip"
    $extractPath = Join-Path $env:TEMP "flx4control_src"

    Invoke-WebRequest $zipUrl -OutFile $zipPath

    if (Test-Path $extractPath) {
        Remove-Item $extractPath -Recurse -Force
    }

    Expand-Archive $zipPath -DestinationPath $extractPath

    $realRoot = Get-ChildItem $extractPath | Select-Object -First 1
    $newInstaller = Join-Path $realRoot.FullName "install.ps1"

    Write-Host "Re-launching installer from extracted source..."
    powershell -ExecutionPolicy Bypass -File $newInstaller -Target $Target
    exit
}

# ------------------------------------------------------------
# Find Python
# ------------------------------------------------------------
Write-Host "[1/7] Checking Python..."

$pythonCmd = @("py","python","python3") |
    Where-Object {
        try { & $_ --version *> $null; $true } catch { $false }
    } | Select-Object -First 1

if (-not $pythonCmd) {
    Write-Host "ERROR: Python 3.10+ not found."
    pause
    exit 1
}

$version = & $pythonCmd --version 2>&1
Write-Host "  Found $version"

& $pythonCmd -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python 3.10+ required."
    pause
    exit 1
}

# ------------------------------------------------------------
# Choose location
# ------------------------------------------------------------
if (-not $Target) {
    Write-Host ""
    Write-Host "1. AppData (recommended)"
    Write-Host "   $env:LOCALAPPDATA\Programs\flx4control"
    Write-Host ""
    Write-Host "2. Program Files (requires Admin)"
    Write-Host "   $env:ProgramFiles\flx4control"
    Write-Host ""
    $choice = Read-Host "Enter 1 or 2 [default: 1]"
    if ($choice -eq "2") { $Target = "ProgramFiles" }
    else { $Target = "AppData" }
}

if ($Target -eq "ProgramFiles") {
    $installDir = "$env:ProgramFiles\flx4control"

    if (-not ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {

        Write-Host "Requesting administrator privileges..."
        Start-Process powershell `
            "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Target ProgramFiles" `
            -Verb RunAs
        exit
    }
}
else {
    $installDir = "$env:LOCALAPPDATA\Programs\flx4control"
}

$venvDir = Join-Path $installDir ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"

Write-Host ""
Write-Host "Install directory: $installDir"
Write-Host ""

# ------------------------------------------------------------
# Kill running instance
# ------------------------------------------------------------
Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# ------------------------------------------------------------
# Copy files
# ------------------------------------------------------------
Write-Host "[2/7] Copying application files..."

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

robocopy $PSScriptRoot $installDir /E /IS /IT `
    /XD .venv __pycache__ .git `
    /XF *.tmp *.log `
    /R:5 /W:3 | Out-Null

if ($LASTEXITCODE -ge 8) {
    Write-Host "ERROR: File copy failed (robocopy exit $LASTEXITCODE)"
    pause
    exit 1
}

Write-Host "Files copied."

# ------------------------------------------------------------
# Recreate venv
# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/7] Setting up virtual environment..."

if (Test-Path $venvDir) {
    Remove-Item $venvDir -Recurse -Force
}

& $pythonCmd -m venv $venvDir

Write-Host ""
Write-Host "[4/7] Installing dependencies..."

& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install `
    "PySide6>=6.5" `
    "mido>=1.3.3,<2.0.0" `
    "python-rtmidi>=1.5.8" `
    "pygame>=2.0" `
    "sounddevice" `
    "pyautogui" `
    "pynput" `
    "pycaw" `
    "comtypes" `
    "flx4py"

# ------------------------------------------------------------
# Launcher
# ------------------------------------------------------------
$launcher = Join-Path $installDir "FLX4Control.bat"
@"
@echo off
start "" "$venvDir\Scripts\pythonw.exe" "$installDir\main.py"
"@ | Set-Content $launcher -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\FLX4 Control.lnk")
$Shortcut.TargetPath = $launcher
$Shortcut.WorkingDirectory = $installDir
$Shortcut.Save()

Write-Host ""
Write-Host "============================================================"
Write-Host "Installation complete."
Write-Host "============================================================"
pause
