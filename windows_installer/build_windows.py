"""
Build script for creating Windows executable using PyInstaller
Run this on Windows or in a Windows environment
"""

import PyInstaller.__main__
import os
import shutil
import sys
from pathlib import Path

# Get script directory and parent directory
script_dir = Path(__file__).parent.resolve()
parent_dir = script_dir.parent

# Change to parent directory (where JobDocs-qt.py is located)
os.chdir(parent_dir)

# Try to import version info from windows_installer directory
sys.path.insert(0, str(script_dir))
try:
    from version_info import __version__, VERSION_INFO
    VERSION = __version__
except ImportError:
    VERSION = "1.0.0"
    VERSION_INFO = {}

print("="*70)
print(f"Building JobDocs v{VERSION}")
print("="*70)

# Clean previous builds
print("\n[1/5] Cleaning previous builds...")
if os.path.exists('build'):
    shutil.rmtree('build')
    print("  ✓ Removed build/")
if os.path.exists('dist'):
    shutil.rmtree('dist')
    print("  ✓ Removed dist/")

# Try to create icon if it doesn't exist
print("\n[2/5] Checking for icon...")
icon_path = script_dir / 'icon.ico'
if not icon_path.exists():
    print("  Icon not found, attempting to create one...")
    try:
        import create_icon
        os.chdir(script_dir)
        create_icon.create_icon()
        os.chdir(parent_dir)
    except Exception as e:
        print(f"  ⚠ Could not create icon: {e}")
        print("  Continuing without icon...")
else:
    print("  ✓ Found icon.ico")

# Create version resource file for Windows
print("\n[3/5] Creating version resource file...")

# Parse version into proper tuple
version_parts = VERSION.split('.')
while len(version_parts) < 3:
    version_parts.append('0')
version_tuple = ', '.join(version_parts[:3])

version_file_content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}, 0),
    prodvers=({version_tuple}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{VERSION_INFO.get("company_name", "JobDocs")}'),
        StringStruct(u'FileDescription', u'{VERSION_INFO.get("file_description", "JobDocs Application")}'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'{VERSION_INFO.get("internal_name", "JobDocs")}'),
        StringStruct(u'LegalCopyright', u'{VERSION_INFO.get("legal_copyright", "Copyright (c) 2024")}'),
        StringStruct(u'OriginalFilename', u'{VERSION_INFO.get("original_filename", "JobDocs.exe")}'),
        StringStruct(u'ProductName', u'{VERSION_INFO.get("product_name", "JobDocs")}'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

with open('version_resource.txt', 'w') as f:
    f.write(version_file_content)
print("  ✓ Created version_resource.txt")

# Build PyInstaller arguments
print("\n[4/5] Configuring PyInstaller...")

# Use correct path separator for current platform
path_sep = ';' if sys.platform == 'win32' else ':'

pyinstaller_args = [
    'JobDocs-qt.py',
    '--name=JobDocs',
    '--onefile',
    '--windowed',
    '--noconsole',
    '--clean',
    f'--distpath=dist',
    f'--workpath=build',
    f'--add-data=README.md{path_sep}.',
    f'--add-data=LICENSE{path_sep}.',
    '--hidden-import=PyQt6',
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--version-file=version_resource.txt',
]

# Add icon if it exists
if icon_path.exists():
    pyinstaller_args.append(f'--icon={icon_path}')
    print("  ✓ Icon will be embedded")

# Add Windows-specific optimizations
if sys.platform == 'win32':
    pyinstaller_args.extend([
        '--optimize=2',
        '--noupx',  # UPX can trigger antivirus
    ])

print("  ✓ Configuration complete")

# Run PyInstaller
print("\n[5/5] Building executable with PyInstaller...")
print("  This may take a few minutes...\n")
PyInstaller.__main__.run(pyinstaller_args)

# Cleanup
if os.path.exists('version_resource.txt'):
    os.remove('version_resource.txt')

print("\n" + "="*70)
print("✓ BUILD COMPLETE!")
print("="*70)
print(f"Executable: dist/JobDocs.exe")
print(f"Version: {VERSION}")
if os.path.exists('dist/JobDocs.exe'):
    size_mb = os.path.getsize('dist/JobDocs.exe') / (1024 * 1024)
    print(f"Size: {size_mb:.2f} MB")
print("\nNext step: Run Inno Setup Compiler on windows_installer/JobDocs-installer.iss")
print("="*70)
