@echo off
setlocal enabledelayedexpansion
title FLX4 Control — Installer

echo ============================================
echo   FLX4 Control -- Installer / Updater
echo ============================================
echo.

:: --- Find Python ------------------------------------------------------------
set PYTHON=
for %%c in (python python3) do (
    if "!PYTHON!"=="" (
        %%c --version >nul 2>&1
        if !ERRORLEVEL! == 0 (
            for /f "tokens=2" %%v in ('%%c --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                    if %%a GEQ 3 if %%b GEQ 10 (
                        set PYTHON=%%c
                    )
                )
            )
        )
    )
)

if "%PYTHON%"=="" (
    echo ERROR: Python 3.10 or newer is required.
    echo   Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do set PY_VER=%%v
echo   Python: %PY_VER% ^(%PYTHON%^)

:: --- Set paths --------------------------------------------------------------
set SCRIPT_DIR=%~dp0
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

set INSTALL_DIR=%LOCALAPPDATA%\Programs\flx4control
set VENV_DIR=%INSTALL_DIR%\.venv

echo   Installing to: %INSTALL_DIR%
echo.

:: --- Copy files to install dir ----------------------------------------------
echo ^> Copying application files...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy all project files (skip .venv if it exists in source)
robocopy "%SCRIPT_DIR%" "%INSTALL_DIR%" /E /XD .venv /XD __pycache__ /NFL /NDL /NJH /NJS >nul 2>&1
if %ERRORLEVEL% GTR 7 (
    echo WARNING: Some files may not have copied correctly.
)

:: --- Virtual environment ----------------------------------------------------
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo ^> Updating existing virtual environment...
) else (
    echo ^> Creating virtual environment...
    %PYTHON% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo ^> Upgrading pip...
"%VENV_DIR%\Scripts\pip" install --upgrade pip --quiet

:: --- Dependencies -----------------------------------------------------------
echo ^> Installing dependencies...
"%VENV_DIR%\Scripts\pip" install ^
    "flx4py" ^
    "PySide6>=6.5" ^
    "pygame>=2.0" ^
    "pyautogui" ^
    "pynput" ^
    "sounddevice" ^
    "pycaw" ^
    "comtypes" ^
    --quiet

if %ERRORLEVEL% neq 0 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)
echo   Done.
echo.

:: --- Launcher batch file ----------------------------------------------------
echo ^> Creating launcher...
(
    echo @echo off
    echo start "" "%VENV_DIR%\Scripts\pythonw.exe" "%INSTALL_DIR%\main.py"
) > "%INSTALL_DIR%\FLX4Control.bat"

:: --- Desktop shortcut (via PowerShell) -------------------------------------
echo ^> Creating desktop shortcut...
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; ^
     $s  = $ws.CreateShortcut([System.Environment]::GetFolderPath('Desktop') + '\FLX4 Control.lnk'); ^
     $s.TargetPath      = '%INSTALL_DIR%\FLX4Control.bat'; ^
     $s.WorkingDirectory = '%INSTALL_DIR%'; ^
     $s.Description     = 'FLX4 Control — DDJ-FLX4 Streamdeck'; ^
     $s.Save()" 2>nul

if %ERRORLEVEL% == 0 (
    echo   Shortcut created on Desktop.
) else (
    echo   ^(Could not create shortcut — run FLX4Control.bat manually^)
)

echo.
echo ============================================
echo   Installation complete!
echo.
echo   To start: double-click 'FLX4 Control'
echo             on your Desktop
echo   Or run:   %INSTALL_DIR%\FLX4Control.bat
echo ============================================
echo.
pause
