# Windows Installer Files

This directory contains everything needed to build a Windows installer for JobDocs.

## Files

- **generate_installer.py** - Python script that generates the Inno Setup script with version
- **installer.iss** - Auto-generated Inno Setup script (DO NOT EDIT MANUALLY)
- **installer.nsi** - NSIS script (alternative installer)
- **build_windows_installer.bat** - Automated build script
- **WINDOWS_INSTALLER.md** - Complete documentation
- **INSTALL_GUIDE_WINDOWS.md** - End-user installation guide
- **README_FOR_USERS.txt** - Simple instructions for end users
- **icon.ico** - Application icon

## Quick Start

### Prerequisites

1. Windows PC with Python 3.8+
2. Download and install [Inno Setup](https://jrsoftware.org/isdl.php)

### Build the Installer

From the `JobDocs` root directory, run:

```cmd
cd windows
build_windows_installer.bat
```

This will:
1. Read version from `../VERSION` file
2. Build the JobDocs executable using PyInstaller
3. Generate the `installer.iss` file with the correct version
4. Create the Windows installer package
5. Output: `JobDocs-Setup-{version}.exe` in the parent directory

## Version Management

The version is controlled by the `VERSION` file in the project root. To update:

1. Edit `../VERSION` (e.g., change `0.2.0-alpha` to `0.3.0`)
2. Run `build_windows_installer.bat`

The version will automatically be:
- Used in the installer filename (e.g., `JobDocs-Setup-0.3.0.exe`)
- Embedded in the Windows executable metadata
- Shown in the installer UI

## Manual Build

If you prefer to build manually:

### Step 1: Build the executable
```cmd
cd ..
build_windows.bat
cd windows
```

### Step 2: Compile the installer

**Using Inno Setup GUI:**
1. Open Inno Setup Compiler
2. File → Open → `installer.iss`
3. Build → Compile

**Using command line:**
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## Output

The installer will be created at:
- `../JobDocs-Setup-0.2.0-alpha.exe`

## Documentation

- **For developers:** See [WINDOWS_INSTALLER.md](WINDOWS_INSTALLER.md)
- **For end users:** See [INSTALL_GUIDE_WINDOWS.md](INSTALL_GUIDE_WINDOWS.md)
- **Simple text guide:** See [README_FOR_USERS.txt](README_FOR_USERS.txt)

## Notes

- The installer is designed to be extremely user-friendly ("baby boomer usable")
- Automatically creates desktop icon and Start Menu shortcuts
- Includes proper uninstaller
- No technical knowledge required for end users
