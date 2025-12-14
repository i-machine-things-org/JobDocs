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
rm -rf build/ dist/ *.spec
echo "      Cleaned"

# Build the executable
echo "[4/5] Building executable..."
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name jobdocs \
    --add-data "core:core" \
    --add-data "shared:shared" \
    --add-data "modules:modules" \
    --hidden-import PyQt6.QtCore \
    --hidden-import PyQt6.QtGui \
    --hidden-import PyQt6.QtWidgets \
    --hidden-import PyQt6.uic \
    main.py

if [ $? -eq 0 ]; then
    echo "      Build successful!"
else
    echo "      Build failed!"
    exit 1
fi

# Create symlink for capitalized version
echo "Creating JobDocs symlink..."
cd dist
ln -sf jobdocs JobDocs
cd ..

# Show build info
echo "[5/5] Build complete!"
echo ""
echo "======================================"
echo "Output: dist/jobdocs (with JobDocs symlink)"
echo "Size: $(du -h dist/jobdocs | cut -f1)"
echo "======================================"
echo ""
echo "To install system-wide:"
echo "  sudo cp dist/jobdocs /usr/local/bin/"
echo "  sudo ln -sf /usr/local/bin/jobdocs /usr/local/bin/JobDocs"
echo ""
echo "To install for current user:"
echo "  mkdir -p ~/.local/bin"
echo "  cp dist/jobdocs ~/.local/bin/"
echo "  ln -sf ~/.local/bin/jobdocs ~/.local/bin/JobDocs"
echo ""
echo "To run:"
echo "  ./dist/jobdocs  (or ./dist/JobDocs)"
echo ""
