# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for JobDocs application.
This spec file bundles the JobDocs application into a standalone executable.

Usage:
    pyinstaller JobDocs.spec

    # Custom dist path:
    pyinstaller --distpath custom_folder JobDocs.spec

Generated executable will be in the dist/ directory (or custom path if specified).
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
from pathlib import Path

# ============================================================================
# BUILD CONFIGURATION
# ============================================================================
# Application metadata
APP_NAME = 'JobDocs'

# Build paths (can be overridden with command-line options)
# To customize, use: pyinstaller --distpath <path> --workpath <path> JobDocs.spec
# Default values:
#   DISTPATH (output): 'dist' (in project root)
#   WORKPATH (temp):   'build' (in project root)
# ============================================================================

# Get the directory where this spec file is located
spec_root = Path(SPECPATH)

# Determine platform-specific icon file
import sys
if sys.platform == 'win32':
    # Prefer the pre-built .ico (no Pillow conversion needed)
    icon_path = spec_root / 'windows' / 'icon.ico'
    if not icon_path.exists():
        icon_path = spec_root.parent / 'windows' / 'icon.ico'
elif sys.platform == 'darwin':
    icon_path = spec_root / 'JobDocs.iconset' / 'icon_512x512.png'
    if not icon_path.exists():
        icon_path = spec_root.parent / 'JobDocs.iconset' / 'icon_512x512.png'
else:
    icon_path = spec_root / 'JobDocs.iconset' / 'icon_256x256.png'
    if not icon_path.exists():
        icon_path = spec_root.parent / 'JobDocs.iconset' / 'icon_256x256.png'

ICON_FILE = str(icon_path) if icon_path.exists() else None

# Collect all UI files from modules
ui_files = []
modules_dir = spec_root / 'modules'
if not modules_dir.exists():
    # If modules not found relative to spec, try parent directory
    modules_dir = spec_root.parent / 'modules'

# PSM-only modules excluded from stable build (Rule 3: modules/reporting/ is PSM-only)
PSM_ONLY_MODULES = {'reporting'}

for module_folder in modules_dir.iterdir():
    if module_folder.is_dir() and not module_folder.name.startswith('_') and module_folder.name not in PSM_ONLY_MODULES:
        ui_dir = module_folder / 'ui'
        if ui_dir.exists():
            for ui_file in ui_dir.glob('*.ui'):
                ui_files.append((str(ui_file), f'modules/{module_folder.name}/ui'))

# Collect all icon files
iconset_dir = spec_root / 'JobDocs.iconset'
if not iconset_dir.exists():
    iconset_dir = spec_root.parent / 'JobDocs.iconset'

icon_files = []
if iconset_dir.exists():
    for icon_file in iconset_dir.glob('*.png'):
        icon_files.append((str(icon_file), 'JobDocs.iconset'))

# Collect sample files
sample_dir = spec_root / 'sample_files'
if not sample_dir.exists():
    sample_dir = spec_root.parent / 'sample_files'

sample_files = []
if sample_dir.exists():
    for sample_file in sample_dir.glob('*'):
        if sample_file.is_file():
            sample_files.append((str(sample_file), 'sample_files'))

# Collect all data files
datas = ui_files + icon_files + sample_files

# Add README and LICENSE
readme_file = spec_root / 'README.md'
if not readme_file.exists():
    readme_file = spec_root.parent / 'README.md'
if readme_file.exists():
    datas.append((str(readme_file), '.'))

license_file = spec_root / 'LICENSE'
if not license_file.exists():
    license_file = spec_root.parent / 'LICENSE'
if license_file.exists():
    datas.append((str(license_file), '.'))

# Hidden imports - modules that PyInstaller might not detect automatically
hiddenimports = [
    # PyQt6 modules
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.uic',
    'PyQt6.sip',

    # Core modules
    'core',
    'core.app_context',
    'core.base_module',
    'core.module_loader',
    'core.settings_dialog',

    # Shared modules
    'shared',
    'shared.utils',
    'shared.widgets',

    # Modules package (parent for dynamically loaded modules)
    'modules',

    # All application modules (dynamically loaded)
    # Each module needs both the package and the module.py file
    'modules.quote',
    'modules.quote.module',
    'modules.job',
    'modules.job.module',
    'modules.add_to_job',
    'modules.add_to_job.module',
    'modules.bulk',
    'modules.bulk.module',
    'modules.search',
    'modules.search.module',
    'modules.import_bp',
    'modules.import_bp.module',
    'modules.history',
    'modules.history.module',
    # Shared modules
    'shared.remote_sync',

    # PDF preview (imported inside function body — PyInstaller won't auto-detect)
    'fitz',

    # stdlib modules used by dynamically-loaded plugins (not reachable via static analysis)
    'difflib',
]

# Third-party packages required by plugins (e.g. jobdocs-report-fixer uses pandas + openpyxl).
#
# Architectural note: because this is a onedir build, pure-Python plugin dependencies
# could in principle live in a plugin's own deps/ subfolder (added to sys.path by the
# plugin loader before exec_module). However, pandas contains compiled .pyd extensions
# that must exactly match the Python version bundled by PyInstaller — they cannot be
# shipped portably alongside a plugin. pandas must therefore be declared here so
# PyInstaller includes the correct pre-compiled binaries in the bundle.
# openpyxl is included here for the same reason as pandas (consistency and to avoid
# a split deps model until a proper per-plugin deps/ system is implemented).
hiddenimports += collect_submodules('pandas')
hiddenimports += collect_submodules('openpyxl')
datas += collect_data_files('pandas')

# Find main.py
main_py = spec_root / 'main.py'
if not main_py.exists():
    main_py = spec_root.parent / 'main.py'

# Analysis - scan the main script and all dependencies
a = Analysis(
    [str(main_py)],
    pathex=[str(main_py.parent)],  # Add parent directory to Python path
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'PIL',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ - compressed archive of Python modules
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# EXE - launcher (onedir build — binaries/data go into COLLECT)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # GUI application — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_FILE,
)

# COLLECT - gathers exe + all binaries/data into a single directory
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
