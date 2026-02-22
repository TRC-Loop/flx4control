@echo off
setlocal EnableExtensions EnableDelayedExpansion
title FLX4 Control -- Installer / Updater

echo.
echo ============================================================
echo   FLX4 Control ^|^| Installer / Updater
echo ============================================================
echo.

:: ---------------------------------------------------------------------------
:: Safety: prevent running from Windows temp (ZIP execution issue)
:: ---------------------------------------------------------------------------
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo %SCRIPT_DIR% | findstr /i "\AppData\Local\Temp\" >nul
if not errorlevel 1 (
    echo.
    echo   ERROR: Installer is running from a temporary folder.
    echo   Please extract the ZIP first, then run the installer.
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: 1. Find Python
:: ---------------------------------------------------------------------------
echo [1/7] Checking Python...
set "PYTHON_CMD="

for %%P in (py python python3) do (
    %%P --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=%%P"
        goto :found_python
    )
)

echo.
echo   ERROR: Python 3.10+ not found.
echo   Download from https://www.python.org/downloads/
echo.
pause
exit /b 1

:found_python
for /f "tokens=2 delims= " %%V in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%V"
echo   Found Python %PY_VER%

%PYTHON_CMD% -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python 3.10 or newer required.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------------------
:: 2. Install location
:: ---------------------------------------------------------------------------
if /i "%~1"=="PROGRAMFILES" (
    set "INSTALL_DIR=%PROGRAMFILES%\flx4control"
    goto :paths_set
)

echo Where would you like to install FLX4 Control?
echo.
echo   1. AppData (recommended)
echo      %LOCALAPPDATA%\Programs\flx4control
echo.
echo   2. Program Files (requires Admin)
echo      %PROGRAMFILES%\flx4control
echo.
set /p "LOC_CHOICE=Enter 1 or 2 [default: 1]: "

if "%LOC_CHOICE%"=="2" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo   Requesting administrator privileges...
        powershell -NoProfile -Command ^
            "Start-Process cmd -ArgumentList '/c \"%~f0\" PROGRAMFILES' -Verb RunAs"
        exit /b 0
    )
    set "INSTALL_DIR=%PROGRAMFILES%\flx4control"
) else (
    set "INSTALL_DIR=%LOCALAPPDATA%\Programs\flx4control"
)

:paths_set
set "VENV_DIR=%INSTALL_DIR%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo.
echo   Install directory: %INSTALL_DIR%
echo.

:: ---------------------------------------------------------------------------
:: Kill running instance before update
:: ---------------------------------------------------------------------------
tasklist | findstr /i "pythonw.exe" | findstr /i "flx4control" >nul
if not errorlevel 1 (
    echo   Closing running FLX4 Control...
    taskkill /f /im pythonw.exe >nul 2>&1
)

:: ---------------------------------------------------------------------------
:: 3. Copy files
:: ---------------------------------------------------------------------------
echo [2/7] Copying application files...

%PYTHON_CMD% -c "import os; exit(0 if os.path.normcase(os.path.abspath(r'%SCRIPT_DIR%')) == os.path.normcase(os.path.abspath(r'%INSTALL_DIR%')) else 1)" >nul 2>&1
if not errorlevel 1 (
    echo   Running from install directory - skipping copy.
    goto :redo_venv
)

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

robocopy "%SCRIPT_DIR%" "%INSTALL_DIR%" /E /IS /IT ^
    /XD .venv __pycache__ .git ^
    /XF .python-version .gitattributes *.tmp *.log ^
    /R:5 /W:3 ^
    /NFL /NDL /NJH /NJS

set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
    echo.
    echo   ERROR: File copy failed (robocopy exit %RC%)
    pause
    exit /b 1
)

echo   Files copied successfully.

:: ---------------------------------------------------------------------------
:: 4. Recreate venv
:: ---------------------------------------------------------------------------
:redo_venv
echo.
echo [3/7] Setting up virtual environment...

if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"

%PYTHON_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo   ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo   Virtual environment ready.

:: ---------------------------------------------------------------------------
:: 5. Upgrade pip
:: ---------------------------------------------------------------------------
echo.
echo [4/7] Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip >nul

:: ---------------------------------------------------------------------------
:: 6. Install dependencies
:: ---------------------------------------------------------------------------
echo.
echo [5/7] Installing dependencies...

"%VENV_PY%" -m pip install ^
    "PySide6>=6.5" ^
    "mido>=1.3.3,<2.0.0" ^
    "python-rtmidi>=1.5.8" ^
    "pygame>=2.0" ^
    "sounddevice" ^
    "pyautogui" ^
    "pynput" ^
    "pycaw" ^
    "comtypes"

if errorlevel 1 goto :dep_error

"%VENV_PY%" -m pip install "flx4py"

if errorlevel 1 goto :dep_error

echo   Dependencies installed.
goto :gen_icon

:dep_error
echo.
echo   ERROR: Dependency installation failed.
pause
exit /b 1

:: ---------------------------------------------------------------------------
:: 7. Generate icon
:: ---------------------------------------------------------------------------
:gen_icon
echo.
echo [6/7] Generating app icon...

if exist "%INSTALL_DIR%\generate_icon.py" (
    "%VENV_PY%" "%INSTALL_DIR%\generate_icon.py" "%INSTALL_DIR%"
)

:: ---------------------------------------------------------------------------
:: 8. Create launcher + shortcut
:: ---------------------------------------------------------------------------
echo.
echo [7/7] Creating launcher and shortcut...

(
    echo @echo off
    echo start "" "%VENV_DIR%\Scripts\pythonw.exe" "%INSTALL_DIR%\main.py"
) > "%INSTALL_DIR%\FLX4Control.bat"

set "VBS=%TEMP%\flx4_sc_%RANDOM%.vbs"
echo Set oWS = CreateObject("WScript.Shell") > "%VBS%"
echo sDesktop = oWS.SpecialFolders("Desktop") >> "%VBS%"
echo Set oLink = oWS.CreateShortcut(sDesktop ^& "\FLX4 Control.lnk") >> "%VBS%"
echo oLink.TargetPath = "%INSTALL_DIR%\FLX4Control.bat" >> "%VBS%"
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> "%VBS%"
echo oLink.Description = "FLX4 Control" >> "%VBS%"
if exist "%INSTALL_DIR%\flx4control.ico" (
    echo oLink.IconLocation = "%INSTALL_DIR%\flx4control.ico,0" >> "%VBS%"
)
echo oLink.Save >> "%VBS%"

cscript //nologo "%VBS%" >nul
del "%VBS%" >nul 2>&1

:: ---------------------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------------------
echo.
echo ============================================================
echo   Installation complete!
echo ============================================================
echo.
pause
