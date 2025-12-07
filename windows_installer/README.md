# Windows Installer

This directory contains all files needed to build a Windows installer for JobDocs.

## Quick Start

1. **On Windows**, navigate to this directory
2. Run one of:
   - `build_installer.bat` (Batch file - double-click)
   - `build_installer.ps1` (PowerShell - right-click → Run with PowerShell)

## Files in This Directory

- **build_installer.bat** - Main build script (Batch)
- **build_installer.ps1** - Main build script (PowerShell)
- **build_windows.py** - PyInstaller build script
- **JobDocs-installer.iss** - Inno Setup installer definition
- **create_icon.py** - Auto-generates application icon
- **version_info.py** - Version and metadata for the application
- **BUILD_INSTRUCTIONS.md** - Detailed build instructions
- **RELEASE_CHECKLIST.md** - Release process checklist

## Prerequisites

- Windows PC
- Python 3.8+
- [Inno Setup](https://jrsoftware.org/isinfo.php)

## Build Output

After building, you'll find:
- `dist/JobDocs.exe` - Standalone executable (one directory up)
- `installer_output/JobDocs-1.0.0-Setup.exe` - Windows installer (one directory up)

## For More Information

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for complete documentation.
