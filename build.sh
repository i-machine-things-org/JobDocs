#!/bin/bash
# Build script for JobDocs executable
# Run this on Linux to create a Linux executable

echo "Building JobDocs for Linux..."

# Install PyInstaller if not already installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install --user pyinstaller
fi

# Clean previous builds
rm -rf build dist *.spec

# Build the executable
pyinstaller --name="JobDocs" \
    --onefile \
    --windowed \
    --icon=icon.png \
    --add-data="LICENSE:." \
    --hidden-import=PySide6 \
    JobDocs-qt.py

echo ""
echo "Build complete!"
echo "Executable location: dist/JobDocs"
echo ""
echo "To test: ./dist/JobDocs"
