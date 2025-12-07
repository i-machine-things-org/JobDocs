#!/bin/bash
# Build script for JobDocs Linux executable
# Creates a standalone executable using PyInstaller

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}        JobDocs Linux Executable Build Script${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "JobDocs-qt.py" ]; then
    echo -e "${RED}ERROR: JobDocs-qt.py not found${NC}"
    echo ""
    echo -e "${YELLOW}This script must be run from the JobDocs directory${NC}"
    echo -e "${YELLOW}Current directory: $(pwd)${NC}"
    echo ""
    exit 1
fi

# Step 1: Check Python
echo -e "${YELLOW}[1/4] Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed${NC}"
    echo "Install with: sudo pacman -S python"
    exit 1
fi
python3 --version
echo ""

# Step 2: Install dependencies
echo -e "${YELLOW}[2/4] Installing/upgrading build dependencies...${NC}"
# PEP 668 workaround: Try --user first, fall back to --break-system-packages if needed
if pip install --user --upgrade pyinstaller PyQt6 2>/dev/null; then
    echo -e "${GREEN}  ✓ Dependencies installed with --user${NC}"
elif pip install --user --upgrade --break-system-packages pyinstaller PyQt6 2>/dev/null; then
    echo -e "${GREEN}  ✓ Dependencies installed with --break-system-packages (PEP 668 workaround)${NC}"
else
    echo -e "${RED}ERROR: Failed to install dependencies${NC}"
    echo -e "${YELLOW}Try creating a virtual environment:${NC}"
    echo -e "  python3 -m venv venv"
    echo -e "  source venv/bin/activate"
    echo -e "  ./build_linux.sh"
    exit 1
fi
echo ""

# Step 3: Clean previous builds
echo -e "${YELLOW}[3/4] Cleaning previous builds...${NC}"
rm -rf build dist
echo -e "${GREEN}  ✓ Cleaned build directories${NC}"
echo ""

# Step 4: Build executable
echo -e "${YELLOW}[4/4] Building executable with PyInstaller...${NC}"
python3 -m PyInstaller \
    --name=JobDocs \
    --onefile \
    --windowed \
    --noconsole \
    --clean \
    --add-data="README.md:." \
    --add-data="LICENSE:." \
    --hidden-import=PyQt6 \
    --hidden-import=PyQt6.QtCore \
    --hidden-import=PyQt6.QtGui \
    --hidden-import=PyQt6.QtWidgets \
    JobDocs-qt.py

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ BUILD COMPLETE!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "Executable: ${GREEN}dist/JobDocs${NC}"

if [ -f "dist/JobDocs" ]; then
    SIZE=$(du -h "dist/JobDocs" | cut -f1)
    echo -e "Size: ${GREEN}${SIZE}${NC}"

    # Make executable
    chmod +x dist/JobDocs
    echo -e "${GREEN}  ✓ Made executable${NC}"
fi

echo ""
echo -e "${CYAN}To run:${NC} ./dist/JobDocs"
echo -e "${CYAN}To install system-wide:${NC} sudo cp dist/JobDocs /usr/local/bin/"
echo -e "${GREEN}============================================================${NC}"
