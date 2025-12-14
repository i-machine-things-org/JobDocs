@echo off
REM Build script for JobDocs on Windows
REM Creates a standalone executable using PyInstaller

echo ======================================
echo JobDocs Windows Build Script
echo ======================================
echo.

REM Check for Python
py --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
py --version
echo.

REM Check and install dependencies
echo [2/5] Checking dependencies...

py -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo       PyQt6 not found. Installing...
    py -m pip install --user PyQt6
) else (
    echo       PyQt6 found
)

py -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo       PyInstaller not found. Installing...
    py -m pip install --user pyinstaller
) else (
    echo       PyInstaller found
)

REM Clean previous builds
echo [3/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec
echo       Cleaned
echo.

REM Build the executable
echo [4/5] Building executable...
py -m PyInstaller ^
    --onefile ^
    --windowed ^
    --noconsole ^
    --name JobDocs ^
    --add-data "core;core" ^
    --add-data "shared;shared" ^
    --add-data "modules;modules" ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    main.py

if errorlevel 1 (
    echo       Build failed!
    pause
    exit /b 1
)

echo       Build successful!
echo.

REM Show build info
echo [5/5] Build complete!
echo.
echo ======================================
echo Output: dist\JobDocs.exe
for %%I in (dist\JobDocs.exe) do echo Size: %%~zI bytes
echo ======================================
echo.
echo To run:
echo   dist\JobDocs.exe
echo.
echo To create a shortcut:
echo   Right-click dist\JobDocs.exe ^> Send to ^> Desktop
echo.
pause
