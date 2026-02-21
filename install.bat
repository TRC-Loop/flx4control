@echo off
setlocal enabledelayedexpansion
title FLX4 Control -- Installer

echo ============================================
echo   FLX4 Control -- Installer / Updater
echo ============================================
echo.

:: ---------------------------------------------------------------------------
:: 1. Find Python (py launcher is most reliable on Windows)
:: ---------------------------------------------------------------------------
set "PYTHON_CMD="

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :found_python
)

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :found_python
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    goto :found_python
)

echo.
echo   ERROR: Python not found!
echo.
echo   Please install Python 3.10 or newer from:
echo     https://www.python.org/downloads/
echo.
echo   IMPORTANT: During installation, check the box that says
echo   "Add Python to PATH"
echo.
pause
exit /b 1

:found_python
for /f "tokens=2 delims= " %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%V"
echo   Python  : %PY_VER%  (using %PYTHON_CMD%)

:: Verify Python >= 3.10 using Python itself (more reliable than batch parsing)
%PYTHON_CMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python 3.10 or newer is required. Found %PY_VER%.
    echo   Download the latest Python from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: 2. Set paths
:: ---------------------------------------------------------------------------
:: SCRIPT_DIR = folder containing this .bat file
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\flx4control"
set "VENV_DIR=%INSTALL_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

echo   Install : %INSTALL_DIR%
echo.

:: ---------------------------------------------------------------------------
:: 3. Copy application files (skip if already running from install dir)
:: ---------------------------------------------------------------------------
%PYTHON_CMD% -c "import os; exit(0 if os.path.normcase(os.path.abspath(r'%SCRIPT_DIR%')) == os.path.normcase(os.path.abspath(r'%INSTALL_DIR%')) else 1)" >nul 2>&1
if not errorlevel 1 (
    echo   Source == install dir, skipping file copy.
    goto :create_venv
)

echo ^> Copying application files...
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo   ERROR: Cannot create directory %INSTALL_DIR%
        pause & exit /b 1
    )
)

:: robocopy: exit codes 0-7 are success
robocopy "%SCRIPT_DIR%" "%INSTALL_DIR%" /E ^
    /XD .venv __pycache__ .git ^
    /XF .python-version .gitattributes ^
    /NFL /NDL /NJH /NJS >nul 2>&1
set "RC=%ERRORLEVEL%"
if %RC% GTR 7 (
    echo   ERROR: File copy failed (robocopy exit code %RC%)
    pause & exit /b 1
)
echo   Files copied.

:: ---------------------------------------------------------------------------
:: 4. Create / update virtual environment
:: ---------------------------------------------------------------------------
:create_venv
if exist "%VENV_PY%" (
    echo ^> Updating existing virtual environment...
) else (
    echo ^> Creating virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo   ERROR: Failed to create virtual environment.
        echo   Try running this installer as Administrator.
        echo.
        pause & exit /b 1
    )
)

:: ---------------------------------------------------------------------------
:: 5. Install / upgrade dependencies
:: ---------------------------------------------------------------------------
echo ^> Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo   WARNING: pip upgrade failed, continuing with existing pip.
)

echo ^> Installing dependencies (this may take a few minutes)...
"%VENV_PY%" -m pip install ^
    "flx4py" ^
    "PySide6>=6.5" ^
    "pygame>=2.0" ^
    "pyautogui" ^
    "pynput" ^
    "sounddevice" ^
    "pycaw" ^
    "comtypes" ^
    --quiet

if errorlevel 1 (
    echo.
    echo   ERROR: Dependency installation failed.
    echo   Check your internet connection and try again.
    echo.
    pause & exit /b 1
)
echo   Dependencies installed.

:: ---------------------------------------------------------------------------
:: 6. Create launcher batch file
:: ---------------------------------------------------------------------------
echo ^> Creating launcher...
(
    echo @echo off
    echo start "" "%VENV_DIR%\Scripts\pythonw.exe" "%INSTALL_DIR%\main.py"
) > "%INSTALL_DIR%\FLX4Control.bat"
echo   Launcher: %INSTALL_DIR%\FLX4Control.bat

:: ---------------------------------------------------------------------------
:: 7. Create Desktop shortcut via a temp PowerShell script file
::    (avoids quoting issues with inline -Command)
:: ---------------------------------------------------------------------------
echo ^> Creating Desktop shortcut...
set "PS_TMP=%TEMP%\flx4_shortcut_%RANDOM%.ps1"

(
    echo $ws = New-Object -ComObject WScript.Shell
    echo $desktop = [System.Environment]::GetFolderPath^('Desktop'^)
    echo $s = $ws.CreateShortcut^("$desktop\FLX4 Control.lnk"^)
    echo $s.TargetPath = "%INSTALL_DIR%\FLX4Control.bat"
    echo $s.WorkingDirectory = "%INSTALL_DIR%"
    echo $s.Description = "FLX4 Control - DDJ-FLX4 Streamdeck"
    echo $s.Save^(^)
) > "%PS_TMP%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_TMP%" >nul 2>&1
if errorlevel 1 (
    echo   WARNING: Desktop shortcut could not be created.
    echo   You can still launch via: %INSTALL_DIR%\FLX4Control.bat
) else (
    echo   Shortcut created on Desktop.
)
del "%PS_TMP%" >nul 2>&1

:: ---------------------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------------------
echo.
echo ============================================
echo   Installation complete!
echo.
echo   Launch:  Double-click "FLX4 Control" on Desktop
echo   Or run:  %INSTALL_DIR%\FLX4Control.bat
echo.
echo   NOTE: If the DDJ-FLX4 is not detected, please
echo   run the application once and follow the setup
echo   guide that appears on first launch.
echo ============================================
echo.
pause
