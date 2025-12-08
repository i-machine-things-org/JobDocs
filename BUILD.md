# Building JobDocs

This document explains how to build standalone executables for JobDocs on different platforms.

## Prerequisites

All platforms require:
- Python 3.8 or higher
- PyQt6
- PyInstaller

## Linux Build

### Quick Build

```bash
./build_linux.sh
```

### Manual Build

```bash
# Install dependencies
pip install --user PyQt6 pyinstaller

# Build
python3 -m PyInstaller --onefile --windowed JobDocs-qt.py

# Run
./dist/JobDocs
```

### System-wide Installation

```bash
sudo cp dist/JobDocs /usr/local/bin/
```

### Arch Linux Package (AUR)

For Arch users, you can create a PKGBUILD:

```bash
# TODO: Create AUR package
```

---

## macOS Build

### Quick Build

```bash
./build_macos.sh
```

### Manual Build

```bash
# Install dependencies (using Homebrew)
brew install python
pip3 install PyQt6 pyinstaller

# Build
python3 -m PyInstaller --onefile --windowed --osx-bundle-identifier=com.i-machine-things.jobdocs JobDocs-qt.py

# Run
open dist/JobDocs.app
```

### Installation

```bash
cp -r dist/JobDocs.app /Applications/
```

### macOS Security Note

On first launch, macOS may show a security warning. To allow:
1. Go to **System Preferences → Security & Privacy**
2. Click **"Open Anyway"** next to the JobDocs warning

---

## Windows Build

### Quick Build

```cmd
build_windows.bat
```

This creates a standalone executable at `dist\JobDocs.exe`

### Manual Build

```cmd
REM Install dependencies
py -m pip install --upgrade pyinstaller PyQt6 pillow

REM Build
py -m PyInstaller --onefile --windowed --noconsole JobDocs-qt.py

REM Run
dist\JobDocs.exe
```

**Note**: `pillow` is used for icon generation if you're creating icons from PNG files.

### Using PowerShell

You can also run the batch file from PowerShell:
```powershell
cmd /c build_windows.bat
```

---

## Build Output

After building, you'll find:

- **Linux**: `dist/JobDocs` (single executable)
- **macOS**: `dist/JobDocs.app` (application bundle)
- **Windows**: `dist/JobDocs.exe` (single executable)

All builds include:
- Embedded Python runtime
- PyQt6 libraries
- Application code
- README and LICENSE files

No additional dependencies required on target systems!

**Note**: The experimental database integration feature (see [DATABASE_INTEGRATION.md](DATABASE_INTEGRATION.md)) requires additional database drivers to be installed separately. The built executable will work without these drivers - the database features simply won't be available until drivers are installed.

---

## Development Mode

To run without building:

```bash
# Install dependencies
pip install PyQt6

# Run directly
python JobDocs-qt.py
# or
python3 JobDocs-qt.py
```

---

## Build Troubleshooting

### "Module not found" errors

Make sure all dependencies are installed:
```bash
pip install PyQt6 pyinstaller
```

### Large executable size

This is normal! The executable includes:
- Python runtime (~20-30 MB)
- PyQt6 libraries (~40-60 MB)
- Application code

Total size is typically 60-100 MB.

### Antivirus false positives

PyInstaller executables may trigger antivirus warnings. This is a known issue with packed executables. You can:
1. Add an exception in your antivirus
2. Code-sign the executable (advanced)
3. Build from source

---

## Platform-Specific Notes

### Linux

- Built executable works on most distributions
- Requires GTK+ and X11 libraries (usually pre-installed)
- AppImage support coming soon

### macOS

- Requires macOS 10.13 (High Sierra) or higher
- Application is not code-signed by default
- For distribution, consider Apple Developer Program

### Windows

- Requires Windows 10 or higher
- Installer supports silent installation: `/SILENT` or `/VERYSILENT`
- No admin rights needed for per-user installation

---

## CI/CD

For automated builds, see `.github/workflows/` (coming soon).

---

## Questions?

See [README.md](README.md) or open an issue on GitHub.
