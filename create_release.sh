#!/bin/bash
# Create GitHub Release for JobDocs Testing
#
# This script helps create a GitHub release with the built binary.
# Run this after building with PyInstaller.

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}JobDocs Release Helper${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Read version from VERSION file
VERSION=$(cat VERSION)
echo -e "${GREEN}Version: v${VERSION}${NC}"

# Get current git branch
BRANCH=$(git branch --show-current)
echo -e "${GREEN}Branch: ${BRANCH}${NC}"

# Determine suffix based on branch
case "$BRANCH" in
    main)
        SUFFIX=""
        RELEASE_NAME="JobDocs v${VERSION}"
        IS_PRERELEASE="false"
        ;;
    stable)
        SUFFIX="-stable"
        RELEASE_NAME="JobDocs Stable v${VERSION}"
        IS_PRERELEASE="false"
        ;;
    testing|develop|dev)
        SUFFIX="-testing"
        RELEASE_NAME="JobDocs Testing v${VERSION}"
        IS_PRERELEASE="true"
        ;;
    *)
        SUFFIX="-${BRANCH}"
        RELEASE_NAME="JobDocs ${BRANCH} v${VERSION}"
        IS_PRERELEASE="true"
        ;;
esac

# Define release tag
if [ -z "$SUFFIX" ]; then
    RELEASE_TAG="v${VERSION}"
    BINARY_NAME="JobDocs-v${VERSION}-linux-x86_64.tar.gz"
else
    RELEASE_TAG="v${VERSION}${SUFFIX}"
    BINARY_NAME="JobDocs${SUFFIX}-v${VERSION}-linux-x86_64.tar.gz"
fi

# Check if binary exists
BINARY_PATH="dist/${BINARY_NAME}"
if [ ! -f "$BINARY_PATH" ]; then
    echo -e "${YELLOW}Warning: Binary not found at ${BINARY_PATH}${NC}"
    echo "Please build the binary first with:"
    echo "  1. pyinstaller jobdocs.spec --clean"
    echo "  2. cd dist && tar -czf ${BINARY_NAME} jobdocs"
    exit 1
fi

echo -e "${GREEN}✓ Binary found: ${BINARY_PATH}${NC}"
echo -e "  Size: $(du -h "$BINARY_PATH" | cut -f1)"
echo ""

# Check if gh CLI is installed
if command -v gh &> /dev/null; then
    echo -e "${GREEN}✓ GitHub CLI detected${NC}"
    echo ""

    # Check if already logged in
    if gh auth status &> /dev/null; then
        echo -e "${GREEN}✓ Already logged in to GitHub${NC}"
        echo ""

        # Ask for confirmation
        echo -e "${YELLOW}Ready to create release:${NC}"
        echo "  Tag: ${RELEASE_TAG}"
        echo "  Name: ${RELEASE_NAME}"
        echo "  File: ${BINARY_PATH}"
        echo ""
        read -p "Create release? [y/N] " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo -e "${BLUE}Creating release...${NC}"

            # Create release with file attachment
            if [ "$IS_PRERELEASE" = "true" ]; then
                gh release create "$RELEASE_TAG" \
                    "$BINARY_PATH" \
                    --title "$RELEASE_NAME" \
                    --notes-file RELEASE_NOTES.md \
                    --prerelease \
                    --repo i-machine-things/JobDocs
            else
                gh release create "$RELEASE_TAG" \
                    "$BINARY_PATH" \
                    --title "$RELEASE_NAME" \
                    --notes-file RELEASE_NOTES.md \
                    --repo i-machine-things/JobDocs
            fi

            echo ""
            echo -e "${GREEN}✓ Release created successfully!${NC}"
            echo ""
            echo "View release at:"
            echo "https://github.com/i-machine-things/JobDocs/releases/tag/${RELEASE_TAG}"
        else
            echo "Release creation cancelled"
        fi
    else
        echo -e "${YELLOW}Not logged in to GitHub CLI${NC}"
        echo "Please run: gh auth login"
    fi
else
    echo -e "${YELLOW}GitHub CLI not installed${NC}"
    echo ""
    echo -e "${BLUE}Manual Release Instructions:${NC}"
    echo ""
    echo "1. Go to: https://github.com/i-machine-things/JobDocs/releases/new"
    echo ""
    echo "2. Create new release with:"
    echo "   Tag: ${RELEASE_TAG}"
    echo "   Title: ${RELEASE_NAME}"
    echo "   Description: Copy from RELEASE_NOTES.md"
    if [ "$IS_PRERELEASE" = "true" ]; then
        echo "   Check: ☑ This is a pre-release"
    fi
    echo ""
    echo "3. Upload file: ${BINARY_PATH}"
    echo ""
    echo "4. Publish release"
    echo ""
    echo -e "${BLUE}Or install GitHub CLI:${NC}"
    echo "  Ubuntu/Debian: sudo apt install gh"
    echo "  Arch: sudo pacman -S github-cli"
    echo "  Then run: gh auth login"
    echo "  Then run this script again"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
