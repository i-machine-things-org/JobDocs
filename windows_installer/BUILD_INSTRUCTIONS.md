# Building JobDocs Windows Installer

This guide explains how to build a Windows installer for JobDocs.

## Prerequisites

1. **Windows Computer** (or Windows VM)
2. **Python 3.8+** installed and in PATH
3. **Inno Setup** - Download from [https://jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php)

## Quick Build (Recommended)

### Option 1: Using Batch File
```cmd
build_installer.bat
```

### Option 2: Using PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File build_installer.ps1
```

Both scripts will:
1. Check Python installation
2. Install/upgrade PyInstaller
3. Build the executable
4. Create the installer (if Inno Setup is installed)

## Manual Build Steps

If you prefer to build manually:

### Step 1: Install Dependencies
```cmd
pip install pyinstaller PyQt6
```

### Step 2: Build Executable
```cmd
python build_windows.py
```

This creates `dist/JobDocs.exe`

### Step 3: Create Installer
1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Compile the installer script:
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" JobDocs-installer.iss
```

### Step 4: Find Your Installer
The installer will be in: `installer_output/JobDocs-1.0.0-Setup.exe`

## What the Installer Does

- ✅ Installs JobDocs to `C:\Program Files\JobDocs\`
- ✅ Creates Start Menu shortcuts
- ✅ Optionally creates Desktop shortcut
- ✅ Includes uninstaller
- ✅ Requires admin privileges

## Adding an Icon (Optional)

1. Create or download an `.ico` file
2. Save it as `icon.ico` in the JobDocs directory
3. The build scripts will automatically include it

Without an icon, Windows will use the default Python icon.

## Customization

### Change Version Number
Edit these files:
- `build_windows.py` - Change `VERSION = "1.0.0"`
- `JobDocs-installer.iss` - Change `#define MyAppVersion "1.0.0"`

### Change Install Location
Edit `JobDocs-installer.iss`:
- Change `DefaultDirName={autopf}\{#MyAppName}`

### Modify Shortcuts
Edit the `[Icons]` section in `JobDocs-installer.iss`

## Troubleshooting

### "Python not found"
- Make sure Python is installed and added to PATH
- Restart command prompt after installing Python

### "PyInstaller failed"
- Try: `pip install --upgrade pip`
- Then: `pip install --upgrade pyinstaller`

### "Inno Setup not found"
- Install from [https://jrsoftware.org/isinfo.php](https://jrsoftware.org/isinfo.php)
- Or manually compile: Right-click `JobDocs-installer.iss` → Compile

### Executable won't run
- Check if antivirus is blocking it
- Try building with: `--debug=all` flag in `build_windows.py`

## Distribution

The final installer (`JobDocs-1.0.0-Setup.exe`) is all users need. They don't need Python or any dependencies installed.

## File Structure After Build

```
JobDocs/
├── build/                      (temporary build files)
├── dist/
│   └── JobDocs.exe            (standalone executable)
├── installer_output/
│   └── JobDocs-1.0.0-Setup.exe (final installer)
├── build_windows.py
├── build_installer.bat
├── build_installer.ps1
└── JobDocs-installer.iss
```

## Notes

- The build process may take a few minutes
- The executable will be 50-100 MB (includes Python runtime and Qt libraries)
- First launch may be slow as Windows SmartScreen checks the file
- Users can install without admin rights if you change `PrivilegesRequired=lowest` in the .iss file
