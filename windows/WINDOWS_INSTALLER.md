# Building a Windows Installer for JobDocs

This guide explains how to create a professional Windows installer (.exe) for JobDocs.

## Quick Start

### Prerequisites

1. **Windows PC** (you'll need Windows to build the installer)
2. **Python 3.8+** installed
3. **Inno Setup** - Download from: https://jrsoftware.org/isdl.php

### Build Steps

1. **Install Inno Setup** (if not already installed)
   - Download from https://jrsoftware.org/isdl.php
   - Run the installer
   - Use default installation settings

2. **Run the automated build script:**
   ```cmd
   build_windows_installer.bat
   ```

   This will:
   - Build the JobDocs executable with PyInstaller
   - Create the installer package
   - Output: `JobDocs-Setup-0.2.0-alpha.exe`

3. **Test the installer:**
   - Run `JobDocs-Setup-0.2.0-alpha.exe`
   - Follow the installation wizard
   - Verify JobDocs launches correctly

## Manual Build (Step by Step)

If you prefer to build manually:

### Step 1: Build the Executable

```cmd
build_windows.bat
```

This creates `dist\jobdocs.exe`

### Step 2: Compile the Installer

**Option A: Using Inno Setup GUI**
1. Open Inno Setup Compiler
2. File → Open → Select `installer.iss`
3. Build → Compile
4. Output: `JobDocs-Setup-0.2.0-alpha.exe`

**Option B: Using Command Line**
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## Installer Features

The generated installer includes:

- ✅ **Professional Installation Wizard** - Modern UI with license agreement
- ✅ **Program Files Installation** - Installs to standard Windows location
- ✅ **Start Menu Shortcuts** - Automatic shortcuts in Start Menu
- ✅ **Desktop Icon** - Optional desktop shortcut
- ✅ **Uninstaller** - Complete removal via Control Panel
- ✅ **Registry Integration** - Appears in Add/Remove Programs
- ✅ **Administrator Privileges** - Proper installation permissions
- ✅ **64-bit Support** - Native 64-bit installation

## Installer Configuration Files

Two installer scripts are provided:

### 1. **installer.iss** (Recommended) - Inno Setup

- **Pros:**
  - Easy to use and configure
  - Modern, professional-looking installer
  - Free and open source
  - Industry standard for Windows installers
  - Great documentation

- **Download Inno Setup:**
  https://jrsoftware.org/isdl.php

### 2. **installer.nsi** (Alternative) - NSIS

- **Pros:**
  - Extremely flexible
  - Smaller installer file size
  - Free and open source

- **Cons:**
  - Steeper learning curve
  - More complex configuration

- **Download NSIS:**
  https://nsis.sourceforge.io/Download

## Customization

### Changing Version Number

Edit `installer.iss` and update:
```ini
AppVersion=0.2.0-alpha
OutputBaseFilename=JobDocs-Setup-0.2.0-alpha
```

### Adding Application Icon

The installer uses `icon.ico` for the application icon. To customize:

1. Create or convert your icon to .ico format
2. Replace `icon.ico` in the project root
3. Rebuild the installer

### Changing Installation Directory

Edit `installer.iss`:
```ini
DefaultDirName={autopf}\JobDocs
```

Options:
- `{autopf}` - Program Files (recommended)
- `{localappdata}` - User's AppData folder
- `{sd}` - System drive root

### Modifying Start Menu Folder

Edit `installer.iss`:
```ini
DefaultGroupName=JobDocs
```

## Distribution

### File Sizes

- **Executable only:** ~60-100 MB
- **Installer package:** ~60-100 MB (compressed)

### Uploading to GitHub

1. Create a new release on GitHub
2. Upload both:
   - `JobDocs-Setup-0.2.0-alpha.exe` (installer)
   - `dist\jobdocs.exe` (standalone executable)

3. Add release notes:
   ```markdown
   ## Installation Options

   **Recommended:** Download and run `JobDocs-Setup-0.2.0-alpha.exe`
   - Automatic installation to Program Files
   - Creates Start Menu and Desktop shortcuts
   - Includes uninstaller

   **Portable:** Download `jobdocs.exe`
   - No installation required
   - Run directly from any location
   - Ideal for USB drives
   ```

## User Installation

### Using the Installer

1. Download `JobDocs-Setup-0.2.0-alpha.exe`
2. Double-click to run
3. Click through the installation wizard
4. Launch from Start Menu or Desktop shortcut

### Uninstalling

**Method 1: Control Panel**
1. Open "Add or Remove Programs"
2. Find "JobDocs"
3. Click "Uninstall"

**Method 2: Start Menu**
1. Find JobDocs in Start Menu
2. Click "Uninstall JobDocs"

**Note:** User data and settings in `%LOCALAPPDATA%\JobDocs` are preserved during uninstall

## Troubleshooting

### "Windows protected your PC" Warning

This warning appears because the installer isn't code-signed. To proceed:
1. Click "More info"
2. Click "Run anyway"

**To prevent this warning:**
- Purchase a code signing certificate (~$100-400/year)
- Sign the installer with `signtool.exe`

### Antivirus False Positives

PyInstaller executables may trigger antivirus warnings. Solutions:
1. Add exception in antivirus software
2. Code-sign the executable (recommended for distribution)
3. Upload to VirusTotal to establish reputation

### Build Failures

**"Python not found"**
- Install Python from https://www.python.org/
- Ensure Python is in PATH

**"PyQt6 not found"**
```cmd
py -m pip install PyQt6
```

**"Inno Setup not found"**
- Install from https://jrsoftware.org/isdl.php
- Or use the GUI to compile `installer.iss` manually

## Advanced: Code Signing

To remove Windows SmartScreen warnings:

1. **Purchase a code signing certificate**
   - Recommended providers: Sectigo, DigiCert, GlobalSign
   - Cost: ~$100-400/year

2. **Install the certificate**
   - Import to Windows Certificate Store

3. **Sign the executable**
   ```cmd
   signtool sign /f certificate.pfx /p password /tr http://timestamp.digicert.com /td sha256 /fd sha256 "JobDocs-Setup-0.2.0-alpha.exe"
   ```

4. **Verify signature**
   ```cmd
   signtool verify /pa "JobDocs-Setup-0.2.0-alpha.exe"
   ```

## Comparison: Installer vs Portable

| Feature | Installer | Portable Exe |
|---------|-----------|--------------|
| Installation | Program Files | Any folder |
| Start Menu | Yes | No |
| Desktop Icon | Optional | Manual |
| Uninstaller | Yes | Just delete |
| Admin Required | Yes | No |
| Auto-updates | Possible | Manual |
| User Experience | Professional | Simple |

**Recommendation:** Offer both options in GitHub Releases

## Files Overview

```
JobDocs/
├── installer.iss                    # Inno Setup script (recommended)
├── installer.nsi                    # NSIS script (alternative)
├── build_windows_installer.bat      # Automated build script
├── build_windows.bat                # Executable-only build
├── icon.ico                         # Application icon
└── dist/
    └── jobdocs.exe                  # Standalone executable
```

## Next Steps

1. ✅ Build the installer using `build_windows_installer.bat`
2. ✅ Test installation on a clean Windows machine
3. ✅ Upload to GitHub Releases
4. 🔲 (Optional) Code-sign for professional distribution
5. 🔲 (Optional) Set up auto-update mechanism

## Questions?

- See [BUILD.md](BUILD.md) for executable building
- See [README.md](README.md) for general documentation
- Open issues on GitHub for support

---

**Note:** Building the installer requires Windows. The .deb package (for Linux) can be built separately on Linux systems.
