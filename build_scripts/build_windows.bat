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
if exist ..\build rmdir /s /q ..\build
if exist ..\dist rmdir /s /q ..\dist
echo       Cleaned
echo.

REM Build the executable
echo [4/5] Building executable...
cd ..
py -m PyInstaller build_scripts\JobDocs.spec
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

REM Copy executable and all dependencies
echo       Copying files...
xcopy /E /I /Q ..\dist\JobDocs JobDocs-Windows\JobDocs >nul

REM Create README
echo Creating README...
(
echo JobDocs - Windows Distribution
echo ==============================
echo.
echo Installation:
echo   1. Copy this folder to your desired location ^(e.g., C:\Program Files\JobDocs^)
echo   2. Right-click on JobDocs\JobDocs.exe and select "Send to" ^> "Desktop ^(create shortcut^)"
echo   3. ^(Optional^) Pin the shortcut to Start Menu or Taskbar
echo.
echo Running JobDocs:
echo   - Double-click JobDocs\JobDocs.exe
echo   - Or use the desktop shortcut
echo   - Or run Create-Desktop-Shortcut.bat to create a shortcut automatically
echo.
echo First-time setup:
echo   On first launch, JobDocs will ask you to configure:
echo   - ITAR directory ^(for controlled files^)
echo   - Non-ITAR directory ^(for regular files^)
echo   - Blueprints directory
echo.
echo For help and documentation, see:
echo   https://github.com/i-machine-things/JobDocs
echo.
echo Version: 0.2.0-alpha
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
echo echo oLink.TargetPath = "%%~dp0JobDocs\JobDocs.exe" ^>^> %%SCRIPT%%
echo echo oLink.WorkingDirectory = "%%~dp0JobDocs" ^>^> %%SCRIPT%%
echo echo oLink.Description = "JobDocs - Job and Quote Management" ^>^> %%SCRIPT%%
echo echo oLink.Save ^>^> %%SCRIPT%%
echo.
echo cscript /nologo %%SCRIPT%%
echo del %%SCRIPT%%
echo.
echo echo Desktop shortcut created successfully!
echo pause
) > JobDocs-Windows\Create-Desktop-Shortcut.bat

REM Show build info
echo.
echo ======================================
echo Build Complete!
echo ======================================
echo.
echo Distribution package: JobDocs-Windows\
echo.
echo Contents:
echo   - JobDocs\ (application folder with all dependencies)
echo   - README.txt
echo   - Create-Desktop-Shortcut.bat
echo.
for %%I in (JobDocs-Windows\JobDocs\JobDocs.exe) do echo Executable size: %%~zI bytes
echo.
echo Next steps:
echo   1. Copy the JobDocs-Windows folder to your desired location
echo   2. Run Create-Desktop-Shortcut.bat to create a desktop shortcut
echo   3. Or manually create shortcuts to Start Menu/Taskbar
echo.
pause
