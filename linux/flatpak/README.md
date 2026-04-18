# JobDocs Flatpak

This directory contains the files needed to build a Flatpak bundle for JobDocs.

## Files

- **`io.github.i_machine_things.JobDocs.yml`** — Flatpak manifest
- **`io.github.i_machine_things.JobDocs.desktop`** — XDG desktop entry
- **`io.github.i_machine_things.JobDocs.metainfo.xml`** — AppStream metadata

`src/` and `icon_256x256.png` are **not committed** — they are staged here by the
CI workflow (source tree + pre-downloaded wheels, and the icon from `JobDocs.iconset/`)
before `flatpak-builder` is invoked.

## Building locally

From the project root:

```bash
# 1. Stage source files and download wheels for the Flatpak build environment
mkdir -p linux/flatpak/src
for item in main.py core modules shared sample_files requirements.txt; do
    [ -e "$item" ] && cp -r "$item" linux/flatpak/src/
done
pip download --only-binary :all: -d linux/flatpak/src/wheels/ -r requirements.txt
cp JobDocs.iconset/icon_256x256.png linux/flatpak/icon_256x256.png

# 2. Build the Flatpak
flatpak-builder --user --repo=flatpak-repo --force-clean \
    flatpak-build linux/flatpak/io.github.i_machine_things.JobDocs.yml

# 3. Bundle for distribution
flatpak build-bundle \
    --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
    --default-branch=stable \
    flatpak-repo JobDocs-linux.flatpak io.github.i_machine_things.JobDocs

# 4. Install and run
flatpak install --user --bundle JobDocs-linux.flatpak
flatpak run io.github.i_machine_things.JobDocs
```

## Runtime

Uses `org.freedesktop.Platform//24.08`. Install via Flathub if not already present:

```bash
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.freedesktop.Platform//24.08 org.freedesktop.Sdk//24.08
```
