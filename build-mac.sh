#!/bin/bash
# Build script for JobDocs executable
# Run this on macOS to create a macOS application bundle

echo "Building JobDocs for macOS..."

# Install PyInstaller if not already installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip3 install --user pyinstaller
fi

# Clean previous builds
rm -rf build dist *.spec

# Build the application bundle
pyinstaller --name="JobDocs" \
    --onefile \
    --windowed \
    --icon=icon.icns \
    --add-data="LICENSE:." \
    --hidden-import=PyQt6 \
    --osx-bundle-identifier=com.jobdocs.app \
    JobDocs-qt.py

echo ""
echo "Build complete!"
echo "Application bundle: dist/JobDocs.app"
echo ""
echo "To test: open dist/JobDocs.app"
echo "To create DMG: hdiutil create -volname JobDocs -srcfolder dist/JobDocs.app -ov -format UDZO dist/JobDocs.dmg"
