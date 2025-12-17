@echo off
REM Build Windows Installer for JobDocs
REM This script builds the executable and creates an installer using Inno Setup

echo ==========================================
echo JobDocs Windows Installer Build Script
echo ==========================================
echo.

REM Read version from VERSION file
cd ..
set /p VERSION=<VERSION
cd windows
echo Version: %VERSION%
echo.

REM Step 1: Build the executable using the existing script
echo [Step 1/3] Building JobDocs executable...
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

REM Step 2: Generate installer script with version
echo [Step 2/3] Generating installer script...
echo.
python generate_installer.py %VERSION%
if errorlevel 1 (
    echo ERROR: Failed to generate installer script
    pause
    exit /b 1
)

echo.
echo ==========================================
echo.

REM Step 3: Create installer with Inno Setup
echo [Step 3/3] Creating installer...
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
%INNO_PATH% installer.iss

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
