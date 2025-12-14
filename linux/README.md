# Linux Package Files

This directory contains everything needed to build a Debian/Ubuntu package for JobDocs.

## Files

- **debian/** - Debian package source directory
- **jobdocs_0.2.0-alpha_all.deb** - Built Debian package (ready to distribute)
- **PACKAGE_INFO.md** - Installation and usage documentation
- **README.md** - This file

## Quick Start

### Installing the Pre-built Package

The `.deb` package is already built and ready to install:

```bash
sudo apt install ./jobdocs_0.2.0-alpha_all.deb
```

Or:

```bash
sudo dpkg -i jobdocs_0.2.0-alpha_all.deb
sudo apt-get install -f  # Install any missing dependencies
```

## Rebuilding the Package

To rebuild the package from source:

```bash
cd ..
dpkg-deb --build linux/debian jobdocs_0.2.0-alpha_all.deb
mv jobdocs_0.2.0-alpha_all.deb linux/
```

## Package Details

- **Package name:** jobdocs
- **Version:** 0.2.0-alpha
- **Architecture:** all (platform-independent)
- **Dependencies:** python3 (>= 3.8), python3-pyqt6
- **Size:** ~58 KB (dependencies downloaded separately)

## Installation Locations

After installation, files are placed at:

- Application files: `/opt/jobdocs/`
- Launcher script: `/usr/bin/jobdocs`
- Desktop entry: `/usr/share/applications/jobdocs.desktop`
- Icon: `/usr/share/pixmaps/jobdocs.png`

## Supported Distributions

- Debian 10+ (Buster and newer)
- Ubuntu 20.04+ (Focal and newer)
- Linux Mint 20+
- Pop!_OS 20.04+
- Any Debian-based distribution with PyQt6 available

## Usage

After installation, launch JobDocs:

```bash
jobdocs
```

Or find it in your applications menu under Office/Database.

## Uninstalling

```bash
sudo apt remove jobdocs
```

**Note:** User configuration and data in `~/.local/share/JobDocs/` is preserved during uninstall.

## Package Contents

The Debian package includes:

```
debian/
├── DEBIAN/
│   ├── control         # Package metadata
│   ├── postinst        # Post-installation script
│   └── prerm           # Pre-removal script
├── opt/jobdocs/        # Application files
│   ├── core/           # Core framework
│   ├── modules/        # Plugin modules
│   ├── shared/         # Shared utilities
│   ├── main.py         # Main application
│   ├── jobdocs         # Launcher script
│   └── ...
└── usr/
    ├── bin/
    │   └── jobdocs -> /opt/jobdocs/jobdocs
    └── share/
        ├── applications/
        │   └── jobdocs.desktop
        └── pixmaps/
            └── jobdocs.png
```

## Documentation

- **For end users:** See [PACKAGE_INFO.md](PACKAGE_INFO.md)
- **For general info:** See [../README.md](../README.md)

## Distribution

Upload `jobdocs_0.2.0-alpha_all.deb` to:
- GitHub Releases
- Personal APT repository
- Direct download

## Notes

- The package follows Debian packaging standards
- No modifications to system Python required
- Uses system-provided PyQt6 libraries
- Lightweight package (application code only, ~58 KB)
