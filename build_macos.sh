#!/bin/bash
# Build script for JobDocs macOS application bundle
# Creates a standalone .app bundle using PyInstaller

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}        JobDocs macOS Application Build Script${NC}"
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

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${YELLOW}WARNING: This script is designed for macOS${NC}"
    echo -e "${YELLOW}Current OS: $OSTYPE${NC}"
    echo ""
fi

# Step 1: Check Python
echo -e "${YELLOW}[1/4] Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 is not installed${NC}"
    echo "Install with: brew install python"
    exit 1
fi
python3 --version
echo ""

# Step 2: Install dependencies
echo -e "${YELLOW}[2/4] Installing/upgrading build dependencies...${NC}"
pip3 install --user --upgrade pyinstaller PyQt6
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to install dependencies${NC}"
    exit 1
fi
echo ""

# Step 3: Clean previous builds
echo -e "${YELLOW}[3/4] Cleaning previous builds...${NC}"
rm -rf build dist
echo -e "${GREEN}  ✓ Cleaned build directories${NC}"
echo ""

# Step 3.5: Create .icns if iconset exists but .icns doesn't
if [ -d "JobDocs.iconset" ] && [ ! -f "icon.icns" ]; then
    if command -v iconutil &> /dev/null; then
        echo -e "${YELLOW}Creating icon.icns from iconset...${NC}"
        iconutil -c icns JobDocs.iconset -o icon.icns
        echo -e "${GREEN}  ✓ Created icon.icns${NC}"
    fi
fi

# Step 4: Build application bundle
echo -e "${YELLOW}[4/4] Building application bundle with PyInstaller...${NC}"

# Check for icon
ICON_ARG=""
if [ -f "icon.icns" ]; then
    ICON_ARG="--icon=icon.icns"
    echo -e "${GREEN}  ✓ Using icon.icns${NC}"
fi

python3 -m PyInstaller \
    --name=JobDocs \
    --onefile \
    --windowed \
    --noconsole \
    --clean \
    --osx-bundle-identifier=com.i-machine-things.jobdocs \
    --add-data="README.md:." \
    --add-data="LICENSE:." \
    --hidden-import=PyQt6 \
    --hidden-import=PyQt6.QtCore \
    --hidden-import=PyQt6.QtGui \
    --hidden-import=PyQt6.QtWidgets \
    $ICON_ARG \
    JobDocs-qt.py

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Build failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}✓ BUILD COMPLETE!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "Application: ${GREEN}dist/JobDocs.app${NC}"

if [ -d "dist/JobDocs.app" ]; then
    SIZE=$(du -sh "dist/JobDocs.app" | cut -f1)
    echo -e "Size: ${GREEN}${SIZE}${NC}"
fi

echo ""
echo -e "${CYAN}To run:${NC} open dist/JobDocs.app"
echo -e "${CYAN}To install:${NC} cp -r dist/JobDocs.app /Applications/"
echo ""
echo -e "${YELLOW}Note:${NC} First launch may show security warning."
echo -e "${YELLOW}      Go to System Preferences → Security & Privacy to allow.${NC}"
echo -e "${GREEN}============================================================${NC}"
