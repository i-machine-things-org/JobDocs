# Build Scripts

This directory contains scripts for building standalone executables of JobDocs.

## Files

- **build_linux.sh** - Build standalone executable for Linux
- **build_windows.bat** - Build standalone executable for Windows

## Important Note

These scripts build **standalone executables only** (the portable versions).

For **installer packages**, use:
- **Linux:** See [../linux/](../linux/) for `.deb` package
- **Windows:** See [../windows/](../windows/) for installer `.exe`

## Usage

### Linux Executable

```bash
cd /path/to/JobDocs
./build_scripts/build_linux.sh
```

Output: `dist/jobdocs` (standalone executable)

### Windows Executable

```cmd
cd C:\path\to\JobDocs
build_scripts\build_windows.bat
```

Output: `dist\jobdocs.exe` (standalone executable)

## What These Scripts Do

Both scripts:
1. Check Python version
2. Install PyInstaller and PyQt6 if needed
3. Clean previous builds
4. Build a standalone executable using PyInstaller
5. Bundle Python runtime and all dependencies

## Standalone vs Installer

| Feature | Standalone Executable | Installer Package |
|---------|----------------------|-------------------|
| Installation | None needed | Proper installation |
| Shortcuts | Manual | Automatic |
| Uninstaller | Just delete | Built-in |
| Best for | USB drives, testing | End users |
| Build location | This directory | `linux/` or `windows/` |

## For End Users

End users should use the **installer packages** instead:
- Linux: [linux/jobdocs_0.2.0-alpha_all.deb](../linux/jobdocs_0.2.0-alpha_all.deb)
- Windows: `JobDocs-Setup-0.2.0-alpha.exe` (build from [../windows/](../windows/))

## For Developers

Use these scripts when you need:
- Quick testing of builds
- Portable versions
- Development builds

For distribution, use the installer packages in `linux/` and `windows/` directories.
