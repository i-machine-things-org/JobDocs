# JobDocs Project Structure

This document provides an overview of the JobDocs project organization.

## Directory Structure

```
JobDocs/
├── core/                    # Core framework
│   ├── __init__.py
│   ├── app_context.py      # Shared application context
│   ├── base_module.py      # Module base class
│   └── module_loader.py    # Auto module discovery
│
├── shared/                  # Shared utilities
│   ├── __init__.py
│   ├── utils.py            # File operations, parsing
│   └── widgets.py          # Custom UI widgets
│
├── modules/                 # Plugin modules
│   ├── __init__.py
│   ├── quote/              # Quote creation module
│   ├── job/                # Job creation module
│   ├── add_to_job/         # Add files to existing jobs
│   ├── bulk/               # Bulk job creation
│   ├── search/             # Advanced search
│   ├── import_bp/          # Import blueprints
│   ├── history/            # Job history
│   ├── reporting/          # Reports (experimental)
│   └── _template/          # Template for new modules
│
├── build_scripts/           # Build standalone executables
│   ├── build_linux.sh      # Build Linux executable
│   ├── build_windows.bat   # Build Windows executable
│   └── README.md
│
├── linux/                   # Linux package files
│   ├── debian/             # Debian package source
│   ├── jobdocs_*.deb       # Built package
│   ├── PACKAGE_INFO.md     # User documentation
│   └── README.md
│
├── windows/                 # Windows installer files
│   ├── installer.iss       # Inno Setup script
│   ├── installer.nsi       # NSIS script (alternative)
│   ├── build_windows_installer.bat
│   ├── WINDOWS_INSTALLER.md
│   ├── INSTALL_GUIDE_WINDOWS.md
│   ├── README_FOR_USERS.txt
│   └── README.md
│
├── JobDocs.iconset/         # Application icons (various sizes)
├── icon.ico                 # Windows icon
│
├── main.py                  # Application entry point
├── settings_dialog.py       # Settings UI
├── requirements.txt         # Python dependencies
│
├── README.md                # Main documentation
├── BUILD.md                 # Building executables
├── CHANGELOG.md             # Version history
├── GETTING_STARTED.md       # Quick start guide
├── MODULAR_SYSTEM.md        # Module development guide
├── TESTING.md               # Testing instructions
├── MIGRATION_COMPLETE.md    # Migration notes
├── PACKAGE_SUMMARY.md       # Package distribution overview
│
└── LICENSE                  # MIT License
```

## Excluded from Git (see .gitignore)

### Development and Testing
- `docs/` - Development notes and session logs
- `.claude/` - Claude Code configuration
- `.github-push-checklist.md` - Personal checklist
- `test_jobs.csv` - Test data
- `itar/`, `not itar/`, `sample_files/` - Test directories
- `old/` - Legacy code archive
- `db_integration.py` - Database integration experiments

### Build Artifacts
- `dist/`, `build/` - PyInstaller output
- `*.spec` - PyInstaller spec files
- `*.exe`, `*.msi`, `*.app`, `*.deb` - Built packages
- `linux/debian/` - Package build directory
- `linux/*.deb` - Built Debian packages
- `windows/Output/` - Inno Setup output
- `JobDocs-Setup-*.exe` - Built installers
- `JobDocs-Windows/` - Windows distribution folder

### Python
- `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd` - Compiled Python
- `venv/`, `env/`, `ENV/` - Virtual environments
- `*.egg-info/` - Package metadata

### IDE and OS
- `.vscode/`, `.idea/` - IDE settings
- `.DS_Store`, `Thumbs.db` - OS metadata

## Source Files Overview

### Core Files (Essential)
- `main.py` - Application entry point
- `settings_dialog.py` - Settings dialog
- `requirements.txt` - Dependencies
- `core/` - Framework code
- `shared/` - Utilities
- `modules/` - Plugin modules

### Documentation (Essential)
- `README.md` - Main documentation
- `LICENSE` - MIT License
- `BUILD.md` - Build instructions
- `PACKAGE_SUMMARY.md` - Distribution guide

### Packaging (Essential)
- `build_scripts/` - Executable builders
- `linux/` - Debian package files
- `windows/` - Windows installer files
- `JobDocs.iconset/` - Application icons
- `icon.ico` - Windows icon

### Documentation (Optional/Archive)
- `CHANGELOG.md` - Version history
- `GETTING_STARTED.md` - Quick start
- `MODULAR_SYSTEM.md` - Module guide
- `TESTING.md` - Test instructions
- `MIGRATION_COMPLETE.md` - Migration notes

## What to Distribute

### GitHub Repository
Include:
- All source code (`core/`, `shared/`, `modules/`)
- Main application files (`main.py`, `settings_dialog.py`)
- Documentation (`README.md`, `BUILD.md`, etc.)
- Build scripts (`build_scripts/`, `linux/`, `windows/`)
- Icons (`JobDocs.iconset/`, `icon.ico`)
- Dependencies (`requirements.txt`)
- License (`LICENSE`)

Exclude (via .gitignore):
- Test data and directories
- Build artifacts
- IDE settings
- Development notes
- Compiled files

### GitHub Releases
Upload:
- `linux/jobdocs_*.deb` - Debian package
- `JobDocs-Setup-*.exe` - Windows installer
- `dist/jobdocs` - Linux standalone executable (optional)
- `dist/jobdocs.exe` - Windows standalone executable (optional)

## File Counts

- **Python modules**: ~30 files
- **UI files**: ~8 .ui files
- **Documentation**: ~15 .md files
- **Build scripts**: 6 files (bash, batch, installer scripts)
- **Icons**: 11 files (various sizes)

## Dependencies

### Runtime
- Python 3.8+
- PyQt6

### Build
- PyInstaller (for executables)
- dpkg-deb (for .deb packages)
- Inno Setup (for Windows installers)

## Architecture

### Plugin System
- Modules self-register with the framework
- Each module has its own UI and logic
- Shared context for cross-module communication

### File Organization
- Hard linking for blueprint files (saves disk space)
- Automatic folder structure creation
- ITAR separation support

## Development Workflow

1. **Source code** - Edit in `core/`, `shared/`, or `modules/`
2. **Test locally** - Run `python main.py`
3. **Build executables** - Use `build_scripts/`
4. **Package for distribution**:
   - Linux: Build .deb in `linux/`
   - Windows: Build installer in `windows/`
5. **Release** - Upload packages to GitHub Releases

## Clean Repository

To clean all build artifacts:
```bash
# Remove all ignored files (be careful!)
git clean -fdX

# Or manually:
rm -rf build/ dist/ linux/debian/ *.spec
```

## Version Control

- **Main branch**: Stable releases
- **Development**: Feature branches
- **Tags**: Version releases (v0.2.0-alpha, etc.)

## Notes

- All packaging files are organized in dedicated directories
- Build artifacts are gitignored to keep repository clean
- Documentation is comprehensive for both users and developers
- Icons are in multiple formats for cross-platform support
