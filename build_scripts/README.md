# Build Scripts

This directory contains scripts for building standalone executables of JobDocs.

## Files

- **JobDocs.spec** - PyInstaller specification file (used by both build scripts)
- **build_linux.sh** - Build standalone executable for Linux
- **build_windows.bat** - Build standalone executable for Windows
- **README.md** - This file

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

Output: `dist/JobDocs` (single-file standalone executable)

### Windows Executable

```cmd
cd C:\path\to\JobDocs
build_scripts\build_windows.bat
```

Output: `build_scripts\JobDocs-Windows\JobDocs.exe` (single-file standalone executable)

## What These Scripts Do

Both scripts:
1. Check Python version
2. Install PyInstaller and PyQt6 if needed
3. Clean previous builds
4. Build using the `JobDocs.spec` file
5. Bundle Python runtime and all dependencies into a distributable package

## The Spec File

The `JobDocs.spec` file contains all the build configuration:
- **Single-file build** - Creates one standalone executable
- Automatically collects all `.ui` files from modules
- Includes all icons from `JobDocs.iconset/`
- Bundles sample files and documentation
- Specifies all hidden imports for dynamically loaded modules
- Cross-platform support (Windows, Linux, macOS)
- UPX compression enabled for smaller file size
- No external dependencies or DLL files needed

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
