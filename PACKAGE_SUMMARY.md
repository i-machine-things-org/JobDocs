# JobDocs Installation Packages

This document summarizes the available installation packages for JobDocs.

## Available Packages

### 1. Debian/Ubuntu Package (.deb)

**File:** `linux/jobdocs_0.2.0-alpha_all.deb` (58 KB)

**Supported Systems:**
- Debian 10+ (Buster and newer)
- Ubuntu 20.04+ (Focal and newer)
- Linux Mint 20+
- Pop!_OS 20.04+
- Any Debian-based distribution

**Installation:**
```bash
sudo apt install ./jobdocs_0.2.0-alpha_all.deb
```

**Features:**
- Automatic dependency installation (python3, python3-pyqt6)
- Desktop menu integration
- System-wide installation to `/opt/jobdocs/`
- Command-line launcher: `jobdocs`
- Uninstaller via APT

**Documentation:** [linux/PACKAGE_INFO.md](linux/PACKAGE_INFO.md)

---

### 2. Windows Installer (.exe)

**File:** `JobDocs-Setup-0.2.0-alpha.exe` (60-100 MB)

**Supported Systems:**
- Windows 10 (64-bit)
- Windows 11

**Installation:**
- Download and run the installer
- Follow the installation wizard
- No additional dependencies needed

**Features:**
- Professional installation wizard
- Start Menu shortcuts
- Desktop icon (optional)
- Uninstaller via Control Panel
- Registry integration

**Build Instructions:** [windows/WINDOWS_INSTALLER.md](windows/WINDOWS_INSTALLER.md)

**Note:** The Windows installer must be built on a Windows PC using the provided scripts in the `windows/` directory.

---

## Building Instructions

### Linux (.deb)

The .deb package has already been built and is ready for distribution in the `linux/` directory.

To rebuild:
```bash
cd linux
dpkg-deb --build debian jobdocs_0.2.0-alpha_all.deb
```

See [linux/README.md](linux/README.md) for detailed instructions.

### Windows (.exe)

Building requires a Windows PC:

1. Install [Inno Setup](https://jrsoftware.org/isdl.php)
2. Run the build script from the windows directory:
   ```cmd
   cd windows
   build_windows_installer.bat
   ```
3. Output: `JobDocs-Setup-0.2.0-alpha.exe`

See [windows/WINDOWS_INSTALLER.md](windows/WINDOWS_INSTALLER.md) for detailed instructions.

---

## Distribution via GitHub Releases

### Recommended Release Assets

When creating a GitHub release, upload:

1. **Windows Users:**
   - `JobDocs-Setup-0.2.0-alpha.exe` - Installer (recommended)
   - `jobdocs.exe` - Portable executable (optional)

2. **Linux Users:**
   - `jobdocs_0.2.0-alpha_all.deb` - Debian/Ubuntu package
   - `jobdocs` - Standalone executable (optional)

3. **Documentation:**
   - Release notes
   - Installation instructions
   - Changelog

### Sample Release Notes

```markdown
# JobDocs v0.2.0-alpha

## Installation

### Windows
**Installer (Recommended):**
1. Download `JobDocs-Setup-0.2.0-alpha.exe`
2. Run the installer
3. Launch from Start Menu

**Portable:**
- Download `jobdocs.exe`
- Run directly (no installation needed)

### Linux (Debian/Ubuntu)
```bash
wget https://github.com/i-machine-things/JobDocs/releases/download/v0.2.0-alpha/jobdocs_0.2.0-alpha_all.deb
sudo apt install ./jobdocs_0.2.0-alpha_all.deb
jobdocs
```

## What's New
[List changes here]

## Requirements
- **Windows:** Windows 10/11 (64-bit)
- **Linux:** Debian 10+, Ubuntu 20.04+

No additional dependencies required!
```

---

## Package Comparison

| Feature | Windows Installer | Linux .deb |
|---------|------------------|------------|
| Size | 60-100 MB | 58 KB |
| Dependencies | Bundled | Downloaded |
| Installation | GUI Wizard | APT |
| Updates | Manual | APT |
| Shortcuts | Automatic | Automatic |
| Uninstall | Control Panel | APT |
| User Experience | Beginner-friendly | Standard |

**Note:** The Windows package is larger because it bundles Python and PyQt6, while the Linux package uses system libraries.

---

## Future Enhancements

- [ ] macOS installer (.dmg or .pkg)
- [ ] Windows MSI package (corporate deployments)
- [ ] RPM package (Red Hat/Fedora)
- [ ] AppImage (universal Linux)
- [ ] Flatpak package
- [ ] Code signing for Windows
- [ ] Homebrew formula (macOS/Linux)

---

## Files

```
JobDocs/
├── linux/                           # Linux package files
│   ├── debian/                     # Debian package source
│   │   ├── DEBIAN/control         # Package metadata
│   │   ├── opt/jobdocs/           # Application files
│   │   └── usr/                   # System integration
│   ├── jobdocs_0.2.0-alpha_all.deb # Built Debian package
│   ├── PACKAGE_INFO.md            # End-user documentation
│   └── README.md                   # Linux package overview
│
├── windows/                         # Windows installer files
│   ├── installer.iss               # Inno Setup script (recommended)
│   ├── installer.nsi               # NSIS script (alternative)
│   ├── build_windows_installer.bat # Build script
│   ├── WINDOWS_INSTALLER.md        # Developer documentation
│   ├── INSTALL_GUIDE_WINDOWS.md    # End-user installation guide
│   ├── README_FOR_USERS.txt        # Simple text instructions
│   └── README.md                   # Windows directory overview
│
├── build_scripts/                   # Standalone executable builders
│   ├── build_linux.sh              # Build Linux executable
│   ├── build_windows.bat           # Build Windows executable
│   └── README.md                   # Build scripts documentation
│
└── PACKAGE_SUMMARY.md               # This file
```

---

## Questions?

- General documentation: [README.md](README.md)
- Build instructions: [BUILD.md](BUILD.md)
- GitHub Issues: https://github.com/i-machine-things/JobDocs/issues
