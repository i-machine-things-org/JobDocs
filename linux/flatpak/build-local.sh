#!/bin/bash
# Local Flatpak build script — mirrors CI workflow for testing before push.
# Run from the repo root: bash linux/flatpak/build-local.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo "==> Staging source files..."
mkdir -p "$SRC_DIR/wheels"
for item in main.py core modules shared requirements.txt; do
    if [ -e "$REPO_ROOT/$item" ]; then
        cp -r "$REPO_ROOT/$item" "$SRC_DIR/"
    fi
done
if [ -d "$REPO_ROOT/sample_files" ]; then
    cp -r "$REPO_ROOT/sample_files" "$SRC_DIR/"
fi

echo "==> Copying icon..."
cp "$REPO_ROOT/JobDocs.iconset/icon_256x256.png" "$SCRIPT_DIR/icon_256x256.png"

echo "==> Downloading wheels (abi3 + cp312 sip for Python 3.12 runtime)..."
pip download --only-binary :all: \
    -d "$SRC_DIR/wheels/" \
    -r "$REPO_ROOT/requirements.txt"

# PyQt6-sip ships cp-version-specific wheels; the freedesktop runtime uses
# Python 3.12 — download the cp312 wheel explicitly alongside the cp313 default.
pip download --only-binary :all: \
    --python-version 3.12 \
    --platform manylinux_2_28_x86_64 \
    -d "$SRC_DIR/wheels/" \
    PyQt6-sip 2>/dev/null || \
pip download --only-binary :all: \
    --python-version 3.12 \
    --platform manylinux1_x86_64 \
    -d "$SRC_DIR/wheels/" \
    PyQt6-sip || true

echo "==> Building Flatpak..."
cd "$SCRIPT_DIR"
flatpak-builder --user --install --force-clean \
    "$REPO_ROOT/flatpak-build" \
    io.github.i_machine_things.JobDocs.yml

echo ""
echo "Build complete. Run with:"
echo "  flatpak run io.github.i_machine_things.JobDocs"
