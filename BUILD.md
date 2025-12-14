# Building JobDocs

This document explains how to build standalone executables for JobDocs on different platforms.

## Prerequisites

All platforms require:
- Python 3.8 or higher
- PyQt6
- PyInstaller

## Important: Executables vs Installers

**This guide is for building standalone executables** (portable versions).

For **installer packages** that end users should use:
- **Linux:** See [linux/](linux/) for `.deb` package
- **Windows:** See [windows/](windows/) for installer `.exe`

## Quick Build (Automated Scripts)

The easiest way to build standalone executables is using the provided build scripts in the `build_scripts/` directory.

### Linux

```bash
./build_scripts/build_linux.sh
```

The script will:
- Check Python version
- Auto-install PyQt6 and PyInstaller if needed
- Clean previous builds
- Build the executable
- Show installation instructions

Output: `dist/JobDocs`

### Windows

```cmd
build_scripts\build_windows.bat
```

The script will:
- Check Python version
- Auto-install PyQt6 and PyInstaller if needed
- Clean previous builds
- Build the executable
- Show installation instructions

Output: `JobDocs-Windows/` distribution folder containing:
- `jobdocs.exe` / `JobDocs.exe` (both executables)
- `README.txt` (installation instructions)
- `Create-Desktop-Shortcut.bat` (automated shortcut creator)

## Manual Build (All Platforms)

### Linux

```bash
# Install dependencies
pip install PyQt6 pyinstaller

# Build
python3 -m PyInstaller --onefile --windowed \
  --add-data "core:core" \
  --add-data "shared:shared" \
  --add-data "modules:modules" \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import PyQt6.uic \
  main.py

# Run
./dist/main
```

### macOS

```bash
# Install dependencies (using Homebrew)
brew install python
pip3 install PyQt6 pyinstaller

# Build
python3 -m PyInstaller --onefile --windowed \
  --osx-bundle-identifier=com.i-machine-things.jobdocs \
  --add-data "core:core" \
  --add-data "shared:shared" \
  --add-data "modules:modules" \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import PyQt6.uic \
  main.py

# Run
open dist/main.app
```

### Windows

```cmd
REM Install dependencies
py -m pip install --upgrade pyinstaller PyQt6

REM Build
py -m PyInstaller --onefile --windowed --noconsole ^
  --add-data "core;core" ^
  --add-data "shared;shared" ^
  --add-data "modules;modules" ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import PyQt6.uic ^
  main.py

REM Run
dist\main.exe
```

## PyInstaller Spec File (Recommended)

For easier building, create a `JobDocs.spec` file:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('core', 'core'),
        ('shared', 'shared'),
        ('modules', 'modules'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.uic',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='JobDocs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS only
app = BUNDLE(
    exe,
    name='JobDocs.app',
    icon=None,
    bundle_identifier='com.i-machine-things.jobdocs',
)
```

Then build with:
```bash
pyinstaller JobDocs.spec
```

## Build Output

After building, you'll find:

- **Linux**: `dist/jobdocs` and `dist/JobDocs` (executable with symlink)
- **macOS**: `dist/JobDocs.app` (application bundle)
- **Windows**: `JobDocs-Windows/` distribution folder (see Automated Scripts output above)

All builds include:
- Embedded Python runtime
- PyQt6 libraries
- Core framework (BaseModule, AppContext, ModuleLoader)
- Shared utilities and widgets
- All 8 plugin modules
- Application settings dialog

No additional dependencies required on target systems!

## Installation

### Linux

```bash
# System-wide installation
sudo cp dist/JobDocs /usr/local/bin/

# User installation
mkdir -p ~/.local/bin
cp dist/JobDocs ~/.local/bin/
```

### macOS

```bash
cp -r dist/JobDocs.app /Applications/
```

**macOS Security Note**: On first launch, macOS may show a security warning. To allow:
1. Go to **System Preferences → Security & Privacy**
2. Click **"Open Anyway"** next to the JobDocs warning

### Windows

**Using the automated build script:**

The `build_windows.bat` script creates a `JobDocs-Windows\` folder with everything you need:

1. Copy the entire `JobDocs-Windows` folder to your desired location (e.g., `C:\Program Files\JobDocs`)
2. Run `Create-Desktop-Shortcut.bat` to automatically create a desktop shortcut
3. (Optional) Pin the executable to Start Menu or Taskbar

**Manual installation:**

Simply copy `dist\jobdocs.exe` to your desired location and create shortcuts manually.

## Development Mode

To run without building:

```bash
# Install dependencies
pip install PyQt6

# Run directly
python main.py
# or
python3 main.py
```

## Build Troubleshooting

### "Module not found" errors

Make sure all dependencies are installed:
```bash
pip install PyQt6 pyinstaller
```

### Module loading issues

If modules don't load in the built executable, make sure all module directories are included:
```bash
# Verify the build includes:
# - core/
# - shared/
# - modules/
```

### UI files not found

If you get "UI file not found" errors, the modules' .ui files need to be included:
```bash
# Add to datas in spec file:
('modules/*/ui/*.ui', 'modules/*/ui'),
```

### Large executable size

This is normal! The executable includes:
- Python runtime (~20-30 MB)
- PyQt6 libraries (~40-60 MB)
- All modules and dependencies

Total size is typically 60-100 MB.

### Antivirus false positives

PyInstaller executables may trigger antivirus warnings. This is a known issue with packed executables. You can:
1. Add an exception in your antivirus
2. Code-sign the executable (advanced)
3. Build from source

## Platform-Specific Notes

### Linux

- Built executable works on most distributions
- Requires GTK+ and X11 libraries (usually pre-installed)
- For distribution, consider creating a .deb or .rpm package

### macOS

- Requires macOS 10.13 (High Sierra) or higher
- Application is not code-signed by default
- For distribution, consider Apple Developer Program for code signing

### Windows

- Requires Windows 10 or higher
- Consider using Inno Setup or NSIS for an installer
- No admin rights needed for per-user installation

## Advanced: Creating Installers

### Windows Installer (Inno Setup)

Create an `installer.iss` file:

```ini
[Setup]
AppName=JobDocs
AppVersion=2.0
DefaultDirName={autopf}\JobDocs
DefaultGroupName=JobDocs
OutputBaseFilename=JobDocs-Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\JobDocs.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\JobDocs"; Filename: "{app}\JobDocs.exe"
Name: "{autodesktop}\JobDocs"; Filename: "{app}\JobDocs.exe"
```

Then compile with Inno Setup Compiler.

### Linux Package (.deb)

Create a debian package structure and use `dpkg-deb`:

```bash
mkdir -p jobdocs-2.0/usr/local/bin
cp dist/JobDocs jobdocs-2.0/usr/local/bin/
dpkg-deb --build jobdocs-2.0
```

### macOS DMG

Create a disk image for distribution:

```bash
hdiutil create -volname "JobDocs" -srcfolder dist/JobDocs.app -ov -format UDZO JobDocs.dmg
```

## CI/CD

For automated builds, see `.github/workflows/build.yml` (example):

```yaml
name: Build
on: [push]
jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install PyQt6 pyinstaller
      - run: pyinstaller JobDocs.spec
      - uses: actions/upload-artifact@v2
        with:
          name: JobDocs-${{ matrix.os }}
          path: dist/
```

## Questions?

See [README.md](README.md) or open an issue on GitHub.

---

**Note**: The legacy `JobDocs-qt.py` version has been archived to `old/legacy/` and is no longer functional. All builds should use `main.py` with the modular architecture.
