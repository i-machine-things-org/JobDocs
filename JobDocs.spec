# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for JobDocs
#
# Build commands:
#   Linux:   pyinstaller JobDocs.spec
#   Windows: pyinstaller JobDocs.spec
#   macOS:   pyinstaller JobDocs.spec

block_cipher = None

a = Analysis(
    ['JobDocs-qt.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('LICENSE', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='JobDocs',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS-specific: Create .app bundle
import sys
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='JobDocs.app',
        icon=None,
        bundle_identifier='com.jobdocs.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
