@echo off
REM Build script for JobDocs Windows executable
REM Creates a standalone executable using PyInstaller

color 0A
echo ============================================================
echo          JobDocs Windows Executable Build Script
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "JobDocs-qt.py" (
    color 0C
    echo ERROR: JobDocs-qt.py not found
    echo.
    echo This script must be run from the JobDocs directory
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

REM Step 1: Check if Python is installed
echo [1/4] Checking Python installation...
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
echo [2/4] Installing/upgrading build dependencies...
py -m pip install --upgrade pyinstaller PyQt6 pillow
if errorlevel 1 (
    color 0C
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Step 3: Clean previous builds
echo [3/4] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo   + Cleaned build directories
echo.

REM Step 4: Build the executable
echo [4/4] Building executable with PyInstaller...
echo   This may take a few minutes...
echo.

REM Check for icon
set ICON_ARG=
if exist "icon.ico" (
    set ICON_ARG=--icon=icon.ico
    echo   + Using icon.ico
)

REM Find PyQt6.sip binary
set SIP_ARG=
for /f "delims=" %%i in ('py -c "import PyQt6.sip; print(PyQt6.sip.__file__)" 2^>nul') do set SIP_BINARY=%%i
if defined SIP_BINARY (
    if exist "%SIP_BINARY%" (
        set SIP_ARG=--add-binary="%SIP_BINARY%;PyQt6"
        echo   + Found PyQt6.sip at %SIP_BINARY%
    )
)

py -m PyInstaller ^
    --name=JobDocs ^
    --onefile ^
    --windowed ^
    --noconsole ^
    --clean ^
    --distpath=dist ^
    --workpath=build ^
    --add-data="README.md;." ^
    --add-data="LICENSE;." ^
    --copy-metadata=PyQt6 ^
    --copy-metadata=PyQt6_sip ^
    --collect-all=PyQt6 ^
    --collect-binaries=PyQt6 ^
    --hidden-import=PyQt6.sip ^
    --hidden-import=db_integration ^
    %SIP_ARG% ^
    %ICON_ARG% ^
    JobDocs-qt.py

if errorlevel 1 (
    color 0C
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
color 0A
echo ============================================================
echo                     BUILD COMPLETE!
echo ============================================================
echo Executable: dist\JobDocs.exe

if exist dist\JobDocs.exe (
    for %%A in (dist\JobDocs.exe) do echo Size: %%~zA bytes
)

echo.
echo To run: dist\JobDocs.exe
echo ============================================================
color 0F
pause
