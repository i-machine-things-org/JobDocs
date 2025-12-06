@echo off
REM Build script for JobDocs executable
REM Run this on Windows to create a Windows executable

echo Building JobDocs for Windows...

REM Install PyInstaller if not already installed
python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

REM Build the executable
pyinstaller --name=JobDocs ^
    --onefile ^
    --windowed ^
    --icon=icon.ico ^
    --add-data="LICENSE;." ^
    --hidden-import=PyQt6 ^
    JobDocs-qt.py

echo.
echo Build complete!
echo Executable location: dist\JobDocs.exe
echo.
echo To test: dist\JobDocs.exe
pause
