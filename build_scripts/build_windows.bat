@echo off
REM Build script for JobDocs on Windows
REM Creates a standalone executable using PyInstaller

REM ============================================================================
REM Configuration
REM ============================================================================
REM You can customize these paths:
REM set DIST_PATH=custom_dist
REM set BUILD_PATH=custom_build

REM Default paths (relative to project root):
set DIST_PATH=output
set BUILD_PATH=build
REM ============================================================================

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
    py -m pip install --user PyQt6>=6.5.0
    if errorlevel 1 (
        echo       ERROR: Failed to install PyQt6
        echo       Please check your internet connection and try again
        pause
        exit /b 1
    )
    echo       PyQt6 installed successfully
) else (
    echo       PyQt6 found
)

py -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo       PyInstaller not found. Installing...
    py -m pip install --user pyinstaller>=6.0.0
    if errorlevel 1 (
        echo       ERROR: Failed to install PyInstaller
        echo       Please check your internet connection and try again
        pause
        exit /b 1
    )
    echo       PyInstaller installed successfully
) else (
    echo       PyInstaller found
)

REM Clean previous builds
echo [3/5] Cleaning previous builds...
if exist "..\%BUILD_PATH%" rmdir /s /q "..\%BUILD_PATH%"
if exist "..\%DIST_PATH%" rmdir /s /q "..\%DIST_PATH%"
echo       Cleaned
echo.

REM Build the executable
echo [4/5] Building executable...
cd ..
py -m PyInstaller --distpath "%DIST_PATH%" --workpath "%BUILD_PATH%" build_scripts\JobDocs.spec
cd build_scripts

if errorlevel 1 (
    echo       Build failed!
    pause
    exit /b 1
)

echo       Build successful!
echo.

REM Create distribution directory
echo [5/5] Creating distribution package...
if exist JobDocs-Windows rmdir /s /q JobDocs-Windows
mkdir JobDocs-Windows

REM Copy executable
copy "..\%DIST_PATH%\JobDocs.exe" JobDocs-Windows\ >nul

REM Create README
echo Creating README...
(
echo JobDocs - Windows Distribution
echo ==============================
echo.
echo Installation:
echo   If running build script as Administrator, JobDocs is automatically
echo   installed to C:\Program Files\JobDocs
echo.
echo   Manual installation:
echo   1. Copy this folder to your desired location
echo   2. Right-click on JobDocs.exe and select "Send to" ^> "Desktop ^(create shortcut^)"
echo   3. ^(Optional^) Pin the shortcut to Start Menu or Taskbar
echo.
echo Running JobDocs:
echo   - Double-click JobDocs.exe
echo   - Or use the desktop shortcut
echo   - Or run Create-Desktop-Shortcut.bat to create a shortcut automatically
echo.
echo First-time setup:
echo   On first launch, go to File ^> Settings to configure:
echo   - Customer Files Directory: Where job folders are created
echo   - Blueprints Directory: Central drawing storage
echo   - ^(Optional^) ITAR directories for controlled files
echo.
echo Modules:
echo   - Create Quote Folder: Create quote folders for customers
echo   - Create Job Folder: Create job folders with blueprint links
echo   - Bulk Create: Create multiple jobs from CSV
echo   - Search: Search across all customers and jobs
echo   - Import Blueprints: Import blueprint files
echo   - History: View recent job history
echo   - Report Fixer: Transform Excel job reports to match templates
echo.
echo For help and documentation, see:
echo   https://github.com/i-machine-things/JobDocs
echo.
echo Version: 0.3.0
echo Build date: %date%
) > JobDocs-Windows\README.txt

REM Create shortcut script
echo Creating shortcut helper...
(
echo @echo off
echo echo Creating JobDocs desktop shortcut...
echo.
echo set SCRIPT="%TEMP%\create_jobdocs_shortcut.vbs"
echo.
echo echo Set oWS = WScript.CreateObject^("WScript.Shell"^) ^> %%SCRIPT%%
echo echo sLinkFile = oWS.SpecialFolders^("Desktop"^) ^& "\JobDocs.lnk" ^>^> %%SCRIPT%%
echo echo Set oLink = oWS.CreateShortcut^(sLinkFile^) ^>^> %%SCRIPT%%
echo echo oLink.TargetPath = "%%~dp0JobDocs.exe" ^>^> %%SCRIPT%%
echo echo oLink.WorkingDirectory = "%%~dp0" ^>^> %%SCRIPT%%
echo echo oLink.Description = "JobDocs - Job and Quote Management" ^>^> %%SCRIPT%%
echo echo oLink.Save ^>^> %%SCRIPT%%
echo.
echo cscript /nologo %%SCRIPT%%
echo del %%SCRIPT%%
echo.
echo echo Desktop shortcut created successfully!
echo pause
) > JobDocs-Windows\Create-Desktop-Shortcut.bat

REM Copy to Program Files (requires admin)
echo.
echo [6/6] Installing to Program Files...
set INSTALL_PATH=C:\Program Files\JobDocs

REM Check if we have admin rights
net session >nul 2>&1
if errorlevel 1 (
    echo       NOTE: Run as Administrator to install to "%INSTALL_PATH%"
    echo       Skipping Program Files installation...
) else (
    if not exist "%INSTALL_PATH%" mkdir "%INSTALL_PATH%"
    copy /Y "..\%DIST_PATH%\JobDocs.exe" "%INSTALL_PATH%\" >nul
    copy /Y "JobDocs-Windows\README.txt" "%INSTALL_PATH%\" >nul
    if errorlevel 1 (
        echo       WARNING: Could not copy to "%INSTALL_PATH%"
    ) else (
        echo       Installed to: %INSTALL_PATH%\JobDocs.exe
    )
)

REM Show build info
echo.
echo ======================================
echo Build Complete!
echo ======================================
echo.
echo Distribution package: JobDocs-Windows\
echo.
echo Contents:
echo   - JobDocs.exe (standalone single-file executable)
echo   - README.txt
echo   - Create-Desktop-Shortcut.bat
echo.
for %%I in (JobDocs-Windows\JobDocs.exe) do echo Executable size: %%~zI bytes
echo.
if exist "%INSTALL_PATH%\JobDocs.exe" (
    echo Installed to: %INSTALL_PATH%\JobDocs.exe
    echo.
)
echo Next steps:
echo   1. Copy the JobDocs-Windows folder to your desired location
echo   2. Run Create-Desktop-Shortcut.bat to create a desktop shortcut
echo   3. Or manually create shortcuts to Start Menu/Taskbar
echo.
pause
