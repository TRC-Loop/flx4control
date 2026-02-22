#Requires -Version 5.1
param(
    [ValidateSet("AppData","ProgramFiles")]
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FLX4 Control || Installer / Updater" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Bootstrap: if main.py is not next to this script, we were downloaded as a
# single file. Download the full repo ZIP and re-launch from there.
# ---------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $PSScriptRoot "main.py"))) {

    Write-Host "[Bootstrap] Downloading FLX4 Control from GitHub..." -ForegroundColor Yellow

    $zipUrl     = "https://github.com/TRC-Loop/flx4control/archive/refs/heads/main.zip"
    $zipPath    = Join-Path $env:TEMP "flx4control.zip"
    $extractDir = Join-Path $env:TEMP "flx4control_src"

    Write-Host "  Fetching archive..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing

    if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $repoRoot     = (Get-ChildItem $extractDir -Directory | Select-Object -First 1).FullName
    $newInstaller = Join-Path $repoRoot "install.ps1"

    Write-Host "  Re-launching from extracted source..."
    $launchArgs = @("-ExecutionPolicy", "Bypass", "-File", $newInstaller)
    if ($Target) { $launchArgs += @("-Target", $Target) }
    & powershell @launchArgs
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# 1. Find Python 3.10-3.12 (required for python-rtmidi binary wheel)
# ---------------------------------------------------------------------------
Write-Host "[1/7] Checking Python..." -ForegroundColor Green

function Find-CompatiblePython {
    # Try py launcher with specific compatible versions first
    foreach ($ver in @("3.12", "3.11", "3.10")) {
        try {
            $exe = (& py "-$ver" -c "import sys; print(sys.executable)" 2>&1).ToString().Trim()
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe }
        } catch {}
    }
    # Try named executables
    foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python", "python3", "py")) {
        try {
            $null = & $cmd --version 2>&1
            if ($LASTEXITCODE -ne 0) { continue }
            $mn = [int](& $cmd -c "import sys; print(sys.version_info.minor)" 2>&1)
            $mj = [int](& $cmd -c "import sys; print(sys.version_info.major)" 2>&1)
            if ($mj -eq 3 -and $mn -ge 10 -and $mn -le 12) { return $cmd }
        } catch {}
    }
    return $null
}

function Install-Python312 {
    $pyExe = Join-Path $env:TEMP "python-3.12.9-amd64.exe"
    $pyUrl = "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
    Write-Host "  Downloading Python 3.12.9..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyExe -UseBasicParsing
    Write-Host "  Installing Python 3.12 (user install, no admin required)..."
    $proc = Start-Process $pyExe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait -PassThru
    Remove-Item $pyExe -ErrorAction SilentlyContinue
    if ($proc.ExitCode -ne 0) {
        Write-Host "ERROR: Python 3.12 installer exited with code $($proc.ExitCode)." -ForegroundColor Red
        pause; exit 1
    }
    # Refresh PATH so the new install is visible in this session
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","User") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    Write-Host "  Python 3.12 installed." -ForegroundColor Green
}

$pythonCmd = Find-CompatiblePython

if (-not $pythonCmd) {
    Write-Host "  No compatible Python (3.10-3.12) found." -ForegroundColor Yellow
    Install-Python312
    # Try py launcher first, then common user-install path
    $pythonCmd = Find-CompatiblePython
    if (-not $pythonCmd) {
        $fallback = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
        if (Test-Path $fallback) { $pythonCmd = $fallback }
    }
    if (-not $pythonCmd) {
        Write-Host ""
        Write-Host "ERROR: Could not locate Python 3.12 after installation." -ForegroundColor Red
        Write-Host "  Please restart your terminal and run the installer again."
        Write-Host ""
        pause; exit 1
    }
}

$pyVerStr = (& $pythonCmd --version 2>&1).ToString()
Write-Host "  Using: $pyVerStr"

# ---------------------------------------------------------------------------
# 2. Choose install location
# ---------------------------------------------------------------------------
if (-not $Target) {
    Write-Host ""
    Write-Host "Where would you like to install FLX4 Control?" -ForegroundColor Green
    Write-Host ""
    Write-Host "  1. AppData (recommended - no Admin required)"
    Write-Host "     $env:LOCALAPPDATA\Programs\flx4control"
    Write-Host ""
    Write-Host "  2. Program Files (requires Admin)"
    Write-Host "     $env:ProgramFiles\flx4control"
    Write-Host ""
    $choice = Read-Host "Enter 1 or 2 [default: 1]"
    if ($choice -eq "2") { $Target = "ProgramFiles" } else { $Target = "AppData" }
}

if ($Target -eq "ProgramFiles") {
    $installDir = "$env:ProgramFiles\flx4control"
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "  Requesting administrator privileges..." -ForegroundColor Yellow
        Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Target ProgramFiles" -Verb RunAs
        exit
    }
} else {
    $installDir = "$env:LOCALAPPDATA\Programs\flx4control"
}

$venvDir = Join-Path $installDir ".venv"
$venvPy  = Join-Path $venvDir "Scripts\python.exe"

Write-Host ""
Write-Host "  Install directory: $installDir"
Write-Host ""

# ---------------------------------------------------------------------------
# Kill any running instance
# ---------------------------------------------------------------------------
Get-Process -Name pythonw -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------------
# 3. Wipe existing install directory for a clean install
# ---------------------------------------------------------------------------
if (Test-Path $installDir) {
    Write-Host "  Removing existing installation at $installDir ..."
    Remove-Item $installDir -Recurse -Force
}

# ---------------------------------------------------------------------------
# 4. Copy application files
# ---------------------------------------------------------------------------
Write-Host "[2/7] Copying application files..." -ForegroundColor Green

New-Item -ItemType Directory -Force -Path $installDir | Out-Null

robocopy $PSScriptRoot $installDir /E /IS /IT `
    /XD .venv __pycache__ .git `
    /XF *.tmp *.log .python-version .gitattributes `
    /R:5 /W:3 | Out-Null

if ($LASTEXITCODE -ge 8) {
    Write-Host "ERROR: File copy failed (robocopy exit $LASTEXITCODE)" -ForegroundColor Red
    pause; exit 1
}
Write-Host "  Files copied."

# ---------------------------------------------------------------------------
# 4. Recreate virtual environment
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/7] Setting up virtual environment..." -ForegroundColor Green

if (Test-Path $venvDir) {
    Write-Host "  Removing old venv..."
    Remove-Item $venvDir -Recurse -Force
}

Write-Host "  Creating fresh venv..."
& $pythonCmd -m venv $venvDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create virtual environment." -ForegroundColor Red
    pause; exit 1
}

# ---------------------------------------------------------------------------
# 5. Upgrade pip
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/7] Upgrading pip..." -ForegroundColor Green
& $venvPy -m pip install --upgrade pip --quiet

# ---------------------------------------------------------------------------
# 6. Install dependencies
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/7] Installing dependencies..." -ForegroundColor Green

Write-Host "  python-rtmidi (binary only - no C compiler required)..."
& $venvPy -m pip install "python-rtmidi>=1.5.8" --only-binary :all:
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: python-rtmidi binary wheel not available for Python $pyMajor.$pyMinor." -ForegroundColor Red
    Write-Host "  Pre-built wheels exist for Python 3.10, 3.11, and 3.12 on Windows x64."
    Write-Host "  Install Python 3.12: https://www.python.org/downloads/release/python-3129/"
    pause; exit 1
}

Write-Host "  Installing remaining packages..."
& $venvPy -m pip install `
    "PySide6>=6.5" `
    "mido>=1.3.3,<2.0.0" `
    "pygame>=2.0" `
    "sounddevice" `
    "pyautogui" `
    "pynput" `
    "pycaw" `
    "comtypes" `
    "flx4py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Dependency installation failed." -ForegroundColor Red
    pause; exit 1
}
Write-Host "  All dependencies installed."

# ---------------------------------------------------------------------------
# 7. Generate icon
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/7] Generating app icon..." -ForegroundColor Green

$iconScript = Join-Path $installDir "generate_icon.py"
if (Test-Path $iconScript) {
    & $venvPy $iconScript $installDir
    Write-Host "  Icon generated."
} else {
    Write-Host "  generate_icon.py not found - skipping."
}

# ---------------------------------------------------------------------------
# 8. Create launcher + desktop shortcut
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[7/7] Creating launcher and desktop shortcut..." -ForegroundColor Green

$launcher = Join-Path $installDir "FLX4Control.bat"
$launcherContent = "@echo off`r`nstart `"`" `"$venvDir\Scripts\pythonw.exe`" `"$installDir\main.py`""
[System.IO.File]::WriteAllText($launcher, $launcherContent, [System.Text.Encoding]::ASCII)

# VBScript shortcut - most reliable across all Windows versions
$vbsPath      = Join-Path $env:TEMP "flx4_shortcut_$PID.vbs"
$shortcutPath = "$env:USERPROFILE\Desktop\FLX4 Control.lnk"
$iconFile     = Join-Path $installDir "flx4control.ico"

$vbs = New-Object System.Collections.Generic.List[string]
$vbs.Add('Set oWS = CreateObject("WScript.Shell")')
$vbs.Add("Set oLink = oWS.CreateShortcut(""$shortcutPath"")")
$vbs.Add("oLink.TargetPath = ""$launcher""")
$vbs.Add("oLink.WorkingDirectory = ""$installDir""")
$vbs.Add('oLink.Description = "FLX4 Control"')
if (Test-Path $iconFile) {
    $vbs.Add("oLink.IconLocation = ""$iconFile,0""")
}
$vbs.Add("oLink.Save")

[System.IO.File]::WriteAllLines($vbsPath, $vbs, [System.Text.Encoding]::ASCII)
cscript //nologo $vbsPath
Remove-Item $vbsPath -ErrorAction SilentlyContinue

Write-Host "  Launcher : $launcher"
Write-Host "  Shortcut : Desktop\FLX4 Control.lnk"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Installation complete!" -ForegroundColor Cyan
Write-Host "  Use the desktop shortcut to launch FLX4 Control." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
pause
