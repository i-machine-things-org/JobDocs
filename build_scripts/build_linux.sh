#!/bin/bash
# Build script for JobDocs on Linux
# Creates a standalone executable using PyInstaller

set -e  # Exit on error

echo "======================================"
echo "JobDocs Linux Build Script"
echo "======================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

echo "[1/5] Checking Python version..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "      Python $PYTHON_VERSION found"

# Check for PyQt6
echo "[2/5] Checking dependencies..."
if ! python3 -c "import PyQt6" 2>/dev/null; then
    echo "      PyQt6 not found. Installing..."
    if python3 -m pip install --user "PyQt6>=6.5.0" 2>/dev/null; then
        echo "      PyQt6 installed successfully"
    else
        echo "      ERROR: Failed to install PyQt6"
        echo "      Please install manually: sudo apt install python3-pyqt6 python3-pip"
        echo "      Or: python3 -m pip install --user 'PyQt6>=6.5.0'"
        exit 1
    fi
else
    echo "      PyQt6 found"
fi

# Check for PyInstaller
if ! python3 -c "import PyInstaller" 2>/dev/null && ! command -v pyinstaller &> /dev/null; then
    echo "      PyInstaller not found. Installing..."
    if python3 -m pip install --user "pyinstaller>=6.0.0" 2>/dev/null; then
        echo "      PyInstaller installed successfully"
    else
        echo "      ERROR: Failed to install PyInstaller"
        echo "      Please install manually:"
        echo "        Option 1: sudo apt install python3-pip && python3 -m pip install --user 'pyinstaller>=6.0.0'"
        echo "        Option 2: sudo apt install pyinstaller"
        exit 1
    fi
else
    echo "      PyInstaller found"
fi

# Clean previous builds
echo "[3/5] Cleaning previous builds..."
cd ..
rm -rf build/ dist/
echo "      Cleaned"

# Build the executable
echo "[4/5] Building executable..."
python3 -m PyInstaller build_scripts/JobDocs.spec

if [ $? -eq 0 ]; then
    echo "      Build successful!"
else
    echo "      Build failed!"
    exit 1
fi

# Show build info
echo "[5/5] Build complete!"
echo ""
echo "======================================"
echo "Output: dist/JobDocs (single-file executable)"
if [ -f dist/JobDocs ]; then
    echo "Size: $(du -h dist/JobDocs | cut -f1)"
fi
echo "======================================"
echo ""
echo "To run:"
echo "  ./dist/JobDocs"
echo ""
echo "To install system-wide:"
echo "  sudo cp dist/JobDocs /usr/local/bin/jobdocs"
echo "  sudo chmod +x /usr/local/bin/jobdocs"
echo ""
echo "To install for current user:"
echo "  mkdir -p ~/.local/bin"
echo "  cp dist/JobDocs ~/.local/bin/jobdocs"
echo "  chmod +x ~/.local/bin/jobdocs"
echo ""
