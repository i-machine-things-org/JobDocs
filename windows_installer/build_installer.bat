@echo off
REM Build script for JobDocs Windows installer
REM Run this from the windows_installer directory

color 0A
echo ============================================================
echo          JobDocs Windows Installer Build Script
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "..\JobDocs-qt.py" (
    color 0C
    echo ERROR: JobDocs-qt.py not found in parent directory
    echo.
    echo This script must be run from the windows_installer directory
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

REM Step 1: Check if Python is installed
echo [1/5] Checking Python installation...
py --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)
py --version
echo.

REM Step 2: Install/upgrade required packages
echo [2/5] Installing/upgrading build dependencies...
py -m pip install --upgrade pyinstaller pillow
if errorlevel 1 (
    color 0C
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Step 3: Create icon if needed
echo [3/5] Creating application icon...
py create_icon.py
echo.

REM Step 4: Build the executable
echo [4/5] Building executable with PyInstaller...
py build_windows.py
if errorlevel 1 (
    color 0C
    echo ERROR: Build failed
    pause
    exit /b 1
)
echo.

REM Step 5: Check for Inno Setup and build installer
echo [5/5] Building installer with Inno Setup...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" JobDocs-installer.iss
    if errorlevel 1 (
        color 0C
        echo ERROR: Inno Setup compilation failed
        pause
        exit /b 1
    )
    echo.
    color 0A
    echo ============================================================
    echo                     BUILD COMPLETE!
    echo ============================================================
    echo Installer: ..\installer_output\JobDocs-1.0.0-Setup.exe
    echo Executable: ..\dist\JobDocs.exe
    echo.
    dir /B ..\installer_output\*.exe 2>nul
    echo.
) else (
    color 0E
    echo.
    echo Inno Setup not found at default location.
    echo Download from: https://jrsoftware.org/isinfo.php
    echo After installing, run:
    echo   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" JobDocs-installer.iss
    echo.
    echo Executable is ready in: ..\dist\JobDocs.exe
    echo.
)

color 0F
echo Build process complete!
pause
