@echo off
setlocal enabledelayedexpansion
title FLX4 Control -- Installer / Updater

echo.
echo ============================================================
echo   FLX4 Control ^|^| Installer / Updater
echo ============================================================
echo.

:: ---------------------------------------------------------------------------
:: 1. Find Python (py launcher is most reliable on Windows)
:: ---------------------------------------------------------------------------
echo [1/7] Checking Python...
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
echo   IMPORTANT: Check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found_python
for /f "tokens=2 delims= " %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%V"
echo   Found Python %PY_VER% ^(%PYTHON_CMD%^)

%PYTHON_CMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   ERROR: Python 3.10 or newer required ^(found %PY_VER%^).
    echo   Download from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: 2. Set paths
:: ---------------------------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "INSTALL_DIR=%LOCALAPPDATA%\Programs\flx4control"
set "VENV_DIR=%INSTALL_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo.
echo   Install directory : %INSTALL_DIR%
echo.

:: ---------------------------------------------------------------------------
:: 3. Copy application files (skip if already in install dir)
:: ---------------------------------------------------------------------------
echo [2/7] Copying application files...

%PYTHON_CMD% -c "import os; exit(0 if os.path.normcase(os.path.abspath(r'%SCRIPT_DIR%')) == os.path.normcase(os.path.abspath(r'%INSTALL_DIR%')) else 1)" >nul 2>&1
if not errorlevel 1 (
    echo   Running from install directory - skipping file copy.
    goto :redo_venv
)

if not exist "%INSTALL_DIR%" (
    echo   Creating install directory...
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo   ERROR: Cannot create %INSTALL_DIR%
        pause & exit /b 1
    )
)

echo   Copying files ^(this replaces all app files, configs are safe^)...
robocopy "%SCRIPT_DIR%" "%INSTALL_DIR%" /E /IS /IT ^
    /XD .venv __pycache__ .git ^
    /XF .python-version .gitattributes ^
    /NFL /NDL /NJH /NJS
set "RC=%ERRORLEVEL%"
if %RC% GTR 7 (
    echo   ERROR: File copy failed ^(robocopy exit %RC%^)
    pause & exit /b 1
)
echo   Files copied OK ^(robocopy exit %RC%^).

:: ---------------------------------------------------------------------------
:: 4. Recreate virtual environment (always, for clean update)
:: ---------------------------------------------------------------------------
:redo_venv
echo.
echo [3/7] Setting up virtual environment...

if exist "%VENV_DIR%" (
    echo   Removing existing venv for clean reinstall...
    rmdir /s /q "%VENV_DIR%"
    if errorlevel 1 (
        echo   WARNING: Could not remove old venv. Continuing anyway...
    )
)

echo   Creating new virtual environment...
%PYTHON_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo.
    echo   ERROR: Failed to create virtual environment.
    echo   Try running as Administrator.
    echo.
    pause & exit /b 1
)
echo   Virtual environment ready.

:: ---------------------------------------------------------------------------
:: 5. Upgrade pip
:: ---------------------------------------------------------------------------
echo.
echo [4/7] Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo   WARNING: pip upgrade failed, continuing with existing pip.
)

:: ---------------------------------------------------------------------------
:: 6. Install dependencies (verbose — shows download progress)
:: ---------------------------------------------------------------------------
echo.
echo [5/7] Installing dependencies...
echo.
echo   --- GUI framework (PySide6) ---
"%VENV_PY%" -m pip install "PySide6>=6.5"
if errorlevel 1 goto :dep_error

echo.
echo   --- MIDI backend (mido + python-rtmidi) ---
"%VENV_PY%" -m pip install "mido>=1.3.3,<2.0.0" "python-rtmidi>=1.5.8"
if errorlevel 1 goto :dep_error

echo.
echo   --- Audio (pygame + sounddevice) ---
"%VENV_PY%" -m pip install "pygame>=2.0" "sounddevice"
if errorlevel 1 goto :dep_error

echo.
echo   --- Input control (pyautogui + pynput) ---
"%VENV_PY%" -m pip install "pyautogui" "pynput"
if errorlevel 1 goto :dep_error

echo.
echo   --- Windows audio (pycaw + comtypes) ---
"%VENV_PY%" -m pip install "pycaw" "comtypes"
if errorlevel 1 goto :dep_error

echo.
echo   --- flx4py (controller library) ---
set "LOCAL_FLX4PY=%SCRIPT_DIR%\..\flx4py"
if exist "%LOCAL_FLX4PY%\pyproject.toml" (
    echo   Installing from local source: %LOCAL_FLX4PY%
    "%VENV_PY%" -m pip install "%LOCAL_FLX4PY%"
) else (
    echo   Installing from GitHub...
    "%VENV_PY%" -m pip install "git+https://github.com/TRC-Loop/flx4py.git"
)
if errorlevel 1 goto :dep_error

echo.
echo   All dependencies installed.
goto :gen_icon

:dep_error
echo.
echo   ERROR: Dependency installation failed.
echo   Check your internet connection and try again.
echo.
pause & exit /b 1

:: ---------------------------------------------------------------------------
:: 7. Generate app icon
:: ---------------------------------------------------------------------------
:gen_icon
echo.
echo [6/7] Generating app icon...
if exist "%INSTALL_DIR%\generate_icon.py" (
    "%VENV_PY%" "%INSTALL_DIR%\generate_icon.py" "%INSTALL_DIR%"
) else (
    echo   generate_icon.py not found - skipping icon generation.
)

:: ---------------------------------------------------------------------------
:: 8. Create launcher batch file
:: ---------------------------------------------------------------------------
echo.
echo [7/7] Creating launcher and shortcut...
(
    echo @echo off
    echo start "" "%VENV_DIR%\Scripts\pythonw.exe" "%INSTALL_DIR%\main.py"
) > "%INSTALL_DIR%\FLX4Control.bat"
echo   Launcher: %INSTALL_DIR%\FLX4Control.bat

:: Create Desktop shortcut via VBScript (more reliable than PowerShell)
set "VBS=%TEMP%\flx4_sc_%RANDOM%.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS%"
echo sDesktop = oWS.SpecialFolders("Desktop") >> "%VBS%"
echo Set oLink = oWS.CreateShortcut(sDesktop ^& "\FLX4 Control.lnk") >> "%VBS%"
echo oLink.TargetPath = "%INSTALL_DIR%\FLX4Control.bat" >> "%VBS%"
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS%"
echo oLink.Description = "FLX4 Control - DDJ-FLX4 Streamdeck" >> "%VBS%"
if exist "%INSTALL_DIR%\flx4control.ico" (
    echo oLink.IconLocation = "%INSTALL_DIR%\flx4control.ico,0" >> "%VBS%"
)
echo oLink.Save >> "%VBS%"

cscript //nologo "%VBS%"
if errorlevel 1 (
    echo   WARNING: Desktop shortcut could not be created.
    echo   You can launch via: %INSTALL_DIR%\FLX4Control.bat
) else (
    echo   Desktop shortcut created: "FLX4 Control.lnk"
)
del "%VBS%" >nul 2>&1

:: ---------------------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------------------
echo.
echo ============================================================
echo   Installation complete!
echo.
echo   Launch: Double-click "FLX4 Control" on the Desktop
echo   Or run: %INSTALL_DIR%\FLX4Control.bat
echo.
echo   Configs are stored in: %APPDATA%\flx4control\
echo   (they are never overwritten by updates)
echo ============================================================
echo.
pause
