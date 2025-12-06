# Building JobDocs Executables

This guide explains how to create standalone executables for Linux, Windows, and macOS.

## Important Notes

⚠️ **Platform Requirement**: You must build on each target platform
- Linux executable → Build on Linux
- Windows executable → Build on Windows
- macOS executable → Build on macOS

⚠️ **Cross-compilation is NOT supported** - PyInstaller cannot create Windows executables on Linux, etc.

## Prerequisites

### All Platforms
1. Python 3.8 or higher installed
2. PyQt6 installed: `pip install PyQt6` or `pacman -S python-pyqt6`
3. PyInstaller: Will be auto-installed by build scripts

## Building on Linux

### Method 1: Using Build Script (Recommended)
```bash
cd /home/allan/Code/JobDocs
./build.sh
```

The executable will be created at: `dist/JobDocs`

### Method 2: Using Spec File
```bash
pip install --user pyinstaller
pyinstaller JobDocs.spec
```

### Method 3: Manual Command
```bash
pyinstaller --name="JobDocs" \
    --onefile \
    --windowed \
    --add-data="LICENSE:." \
    --hidden-import=PyQt6 \
    JobDocs-qt.py
```

### Testing
```bash
./dist/JobDocs
```

### Distribution
The single file `dist/JobDocs` can be copied to other Linux systems with similar architecture (x86_64).

## Building on Windows

### Method 1: Using Build Script (Recommended)
```batch
cd C:\path\to\JobDocs
build.bat
```

The executable will be created at: `dist\JobDocs.exe`

### Method 2: Using Spec File
```batch
pip install pyinstaller
pyinstaller JobDocs.spec
```

### Method 3: Manual Command
```batch
pyinstaller --name=JobDocs ^
    --onefile ^
    --windowed ^
    --add-data="LICENSE;." ^
    --hidden-import=PyQt6 ^
    JobDocs-qt.py
```

### Testing
```batch
dist\JobDocs.exe
```

### Distribution
- The single file `dist\JobDocs.exe` can be copied to other Windows systems
- Consider creating an installer using:
  - NSIS (Nullsoft Scriptable Install System)
  - Inno Setup
  - WiX Toolset

## Building on macOS

### Method 1: Using Build Script (Recommended)
```bash
cd ~/Code/JobDocs
./build-mac.sh
```

The application bundle will be created at: `dist/JobDocs.app`

### Method 2: Using Spec File
```bash
pip3 install --user pyinstaller
pyinstaller JobDocs.spec
```

### Testing
```bash
open dist/JobDocs.app
```

### Creating DMG for Distribution
```bash
# Create a DMG disk image for distribution
hdiutil create -volname JobDocs -srcfolder dist/JobDocs.app -ov -format UDZO dist/JobDocs.dmg
```

### Code Signing (Optional, for Distribution)
```bash
# Sign the app (requires Apple Developer account)
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/JobDocs.app

# Notarize with Apple (required for macOS 10.15+)
xcrun notarytool submit dist/JobDocs.dmg --apple-id your@email.com --team-id TEAMID --wait
```

## Build Options Explained

### Common Options
- `--onefile` - Bundle everything into a single executable
- `--windowed` - No console window (GUI only)
- `--name` - Name of the executable
- `--add-data` - Include data files (LICENSE)
- `--hidden-import` - Explicitly import modules PyInstaller might miss

### Alternative: Directory Mode
For faster startup (but multiple files):
```bash
# Remove --onefile flag
pyinstaller --name="JobDocs" --windowed JobDocs-qt.py
```
This creates `dist/JobDocs/` directory with executable and dependencies.

## Troubleshooting

### "Module not found" errors
Add missing modules to spec file:
```python
hiddenimports=['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets', 'missing_module']
```

### Large executable size
The PyQt6 executable will be 80-150MB due to Qt libraries. To reduce:
1. Use directory mode instead of `--onefile`
2. Use UPX compression (included by default)
3. Exclude unused Qt modules in spec file

### Testing builds
Always test on a clean system without Python/PyQt6 installed to ensure all dependencies are bundled.

### Debug mode
If the app crashes silently, rebuild with console:
```bash
# Change in spec file: console=True
# Or use flag: --console instead of --windowed
```

## CI/CD Automation

### GitHub Actions Example
Create `.github/workflows/build.yml`:

```yaml
name: Build Executables

on: [push, pull_request]

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install PyQt6 pyinstaller
      - run: pyinstaller JobDocs.spec
      - uses: actions/upload-artifact@v3
        with:
          name: JobDocs-Linux
          path: dist/JobDocs

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install PyQt6 pyinstaller
      - run: pyinstaller JobDocs.spec
      - uses: actions/upload-artifact@v3
        with:
          name: JobDocs-Windows
          path: dist/JobDocs.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install PyQt6 pyinstaller
      - run: pyinstaller JobDocs.spec
      - uses: actions/upload-artifact@v3
        with:
          name: JobDocs-macOS
          path: dist/JobDocs.app
```

## File Sizes (Approximate)

- **Linux**: 80-120 MB
- **Windows**: 90-130 MB
- **macOS**: 100-150 MB

Size is large due to bundled Qt libraries. This is normal for PyQt applications.

## Licensing Considerations

When distributing executables with PyQt6:
- **Internal use**: GPL license is fine (no restrictions)
- **Commercial distribution**: You MUST either:
  1. Purchase PyQt6 commercial license from Riverbank Computing (~$500/year)
  2. Release your app under GPL v3 (open source)
  3. Switch to PySide6 (LGPL, free for commercial use)

Your code is MIT licensed, but the PyQt6 library bundled in the executable is GPL.

## Support

For PyInstaller issues, see: https://pyinstaller.org/en/stable/
For PyQt6 licensing: https://riverbankcomputing.com/commercial/license-faq
