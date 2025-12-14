@echo off
REM Build Windows Installer for JobDocs
REM This script builds the executable and creates an installer using Inno Setup

REM Version number - update this when releasing new versions
set VERSION=0.2.0-alpha

echo ==========================================
echo JobDocs Windows Installer Build Script
echo ==========================================
echo.

REM Step 1: Build the executable using the existing script
echo [Step 1/2] Building JobDocs executable...
echo.
cd ..
call build_scripts\build_windows.bat
cd windows
if errorlevel 1 (
    echo ERROR: Failed to build executable
    pause
    exit /b 1
)

echo.
echo ==========================================
echo.

REM Step 2: Create installer with Inno Setup
echo [Step 2/2] Creating installer...
echo.

REM Check if Inno Setup is installed
set INNO_PATH="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO_PATH% (
    set INNO_PATH="C:\Program Files\Inno Setup 6\ISCC.exe"
)

if not exist %INNO_PATH% (
    echo.
    echo WARNING: Inno Setup not found!
    echo.
    echo To create an installer, please:
    echo   1. Download Inno Setup from: https://jrsoftware.org/isdl.php
    echo   2. Install Inno Setup
    echo   3. Run this script again
    echo.
    echo Alternatively, you can:
    echo   - Use the pre-built executable in: dist\jobdocs.exe
    echo   - Manually compile installer.iss with Inno Setup GUI
    echo.
    pause
    exit /b 0
)

REM Build installer
echo Building installer with Inno Setup...
%INNO_PATH% /DVERSION=%VERSION% installer.iss

if errorlevel 1 (
    echo ERROR: Failed to create installer
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Build Complete!
echo ==========================================
echo.
echo Output files:
echo   - Installer: JobDocs-Setup-%VERSION%.exe
echo   - Executable: dist\jobdocs.exe
echo   - Package: JobDocs-Windows\
echo.
echo The installer includes:
echo   - Automatic installation to Program Files
echo   - Start Menu shortcuts
echo   - Desktop shortcut (optional)
echo   - Uninstaller
echo   - Windows registry integration
echo.
echo Next steps:
echo   - Test the installer: JobDocs-Setup-%VERSION%.exe
echo   - Upload to GitHub Releases
echo.
pause
