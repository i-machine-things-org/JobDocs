# JobDocs Flatpak

This directory contains the files needed to build a Flatpak bundle for JobDocs.

## Files

- **`io.github.i_machine_things.JobDocs.yml`** — Flatpak manifest
- **`io.github.i_machine_things.JobDocs.desktop`** — XDG desktop entry
- **`io.github.i_machine_things.JobDocs.metainfo.xml`** — AppStream metadata

The `JobDocs` binary and `icon_256x256.png` are **not committed** — they are staged
here by the CI workflow (from `build_dist/` and `JobDocs.iconset/`) before
`flatpak-builder` is invoked.

## Building locally

From the project root:

```bash
# 1. Build the PyInstaller binary
python3 -m PyInstaller --distpath build_dist --workpath build_temp build_scripts/JobDocs.spec

# 2. Stage the binary and icon
cp build_dist/JobDocs linux/flatpak/JobDocs
cp JobDocs.iconset/icon_256x256.png linux/flatpak/icon_256x256.png

# 3. Build the Flatpak
flatpak-builder --user --repo=flatpak-repo --force-clean \
    flatpak-build linux/flatpak/io.github.i_machine_things.JobDocs.yml

# 4. Bundle for distribution
flatpak build-bundle \
    --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
    flatpak-repo JobDocs-linux.flatpak io.github.i_machine_things.JobDocs

# 5. Install and run
flatpak install --user --bundle JobDocs-linux.flatpak
flatpak run io.github.i_machine_things.JobDocs
```

## Runtime

Uses `org.freedesktop.Platform//24.08`. Install via Flathub if not already present:

```bash
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.freedesktop.Platform//24.08 org.freedesktop.Sdk//24.08
```
