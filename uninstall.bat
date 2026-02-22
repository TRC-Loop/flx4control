@echo off
setlocal enabledelayedexpansion
title FLX4 Control -- Uninstaller

echo.
echo ============================================================
echo   FLX4 Control ^|^| Uninstaller
echo ============================================================
echo.

:: ---------------------------------------------------------------------------
:: Find installation (check both possible locations)
:: ---------------------------------------------------------------------------
set "APPDATA_INSTALL=%LOCALAPPDATA%\Programs\flx4control"
set "PROGFILES_INSTALL=%PROGRAMFILES%\flx4control"
set "INSTALL_DIR="

if exist "%APPDATA_INSTALL%\main.py"   set "INSTALL_DIR=%APPDATA_INSTALL%"
if exist "%PROGFILES_INSTALL%\main.py" set "INSTALL_DIR=%PROGFILES_INSTALL%"

if "%INSTALL_DIR%"=="" (
    echo   FLX4 Control does not appear to be installed.
    echo   ^(Checked AppData and Program Files^)
    echo.
    pause
    exit /b 0
)

echo   Found installation at:
echo     %INSTALL_DIR%
echo.

:: Check if Program Files install needs admin
if /i "%INSTALL_DIR%"=="%PROGFILES_INSTALL%" (
    net session >nul 2>&1
    if errorlevel 1 (
        echo   Program Files install detected — requesting Administrator...
        powershell -NoProfile -Command ^
            "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
        exit /b 0
    )
)

:: ---------------------------------------------------------------------------
:: Confirm
:: ---------------------------------------------------------------------------
set /p "CONFIRM=Remove FLX4 Control from %INSTALL_DIR%? (y/N): "
if /i not "%CONFIRM%"=="y" (
    echo   Cancelled.
    pause
    exit /b 0
)
echo.

:: ---------------------------------------------------------------------------
:: Remove desktop shortcut
:: ---------------------------------------------------------------------------
set "SHORTCUT=%USERPROFILE%\Desktop\FLX4 Control.lnk"
if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo   Removed Desktop shortcut.
)

:: ---------------------------------------------------------------------------
:: Remove installation directory
:: ---------------------------------------------------------------------------
echo   Removing installation directory...
rmdir /s /q "%INSTALL_DIR%"
if errorlevel 1 (
    echo   WARNING: Could not fully remove %INSTALL_DIR%.
    echo   You may need to delete it manually.
) else (
    echo   Installation directory removed.
)

:: ---------------------------------------------------------------------------
:: Optionally remove user config and sounds
:: ---------------------------------------------------------------------------
echo.
set "CFG_DIR=%APPDATA%\flx4control"
if exist "%CFG_DIR%" (
    echo   User settings and sounds are kept at:
    echo     %CFG_DIR%
    echo.
    set /p "RMCFG=Remove settings and sounds as well? (y/N): "
    if /i "!RMCFG!"=="y" (
        rmdir /s /q "%CFG_DIR%"
        echo   Settings and sounds removed.
    ) else (
        echo   Settings and sounds kept.
    )
)

:: ---------------------------------------------------------------------------
:: Done
:: ---------------------------------------------------------------------------
echo.
echo ============================================================
echo   FLX4 Control has been uninstalled.
echo ============================================================
echo.
pause
