@echo off
REM Build script for JobDocs Windows executable
REM Creates a standalone executable using PyInstaller

color 0A
echo ============================================================
echo          JobDocs Windows Executable Build Script
echo ============================================================
echo.

REM Prompt for custom output directory
set /p CUSTOM_DIST="Enter output directory (press Enter for default 'dist'): "
if "%CUSTOM_DIST%"=="" (
    set DIST_DIR=dist
    echo Using default output directory: dist
) else (
    set DIST_DIR=%CUSTOM_DIST%
    echo Using custom output directory: %DIST_DIR%
)
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
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

REM Step 2: Install/upgrade required packages
echo [2/4] Installing/upgrading build dependencies...
python -m pip install --upgrade pyinstaller PyQt6 pillow
if errorlevel 1 (
    color 0C
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

REM Step 3: Clean previous builds
echo [3/4] Cleaning previous builds...
if exist build rmdir /s /q build 2>nul
if exist "%DIST_DIR%\JobDocs.exe" (
    echo   + Attempting to remove old executable...
    del /F /Q "%DIST_DIR%\JobDocs.exe" 2>nul
    if exist "%DIST_DIR%\JobDocs.exe" (
        echo   WARNING: Could not delete old executable - will attempt to overwrite
        echo   TIP: Try a different output directory or add to Windows Defender exclusions
    ) else (
        echo   + Removed old executable
    )
)
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
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
for /f "delims=" %%i in ('python -c "import PyQt6.sip; print(PyQt6.sip.__file__)" 2^>nul') do set SIP_BINARY=%%i
if defined SIP_BINARY (
    if exist "%SIP_BINARY%" (
        set SIP_ARG=--add-binary="%SIP_BINARY%;PyQt6"
        echo   + Found PyQt6.sip at %SIP_BINARY%
    )
)

python -m PyInstaller ^
    --name=JobDocs ^
    --onefile ^
    --windowed ^
    --noconsole ^
    --noconfirm ^
    --distpath=%DIST_DIR% ^
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
echo Executable: %DIST_DIR%\JobDocs.exe

if exist "%DIST_DIR%\JobDocs.exe" (
    for %%A in ("%DIST_DIR%\JobDocs.exe") do echo Size: %%~zA bytes
)

echo.
echo To run: %DIST_DIR%\JobDocs.exe
echo ============================================================
color 0F
pause
