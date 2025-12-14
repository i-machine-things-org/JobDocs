# Version Management

The current version is defined in the `VERSION` file in the project root directory.

**Current Version:** `0.2.0-alpha`

## When Releasing a New Version

When you're ready to release a new version, you need to update the version number in the following locations:

### 1. Core Version Files
- [ ] `VERSION` - The single source of truth
- [ ] `linux/debian/DEBIAN/control` - Line 2: `Version: X.X.X`

### 2. Windows Installer Configurations
- [ ] `windows/installer.iss` - Lines around 7-8:
  - `#define MyAppVersion "X.X.X"`
  - `OutputBaseFilename=JobDocs-Setup-X.X.X`
- [ ] `windows/installer.nsi` - Lines around 12-14:
  - `!define VERSION "X.X.X"`
  - `OutFile "JobDocs-Setup-X.X.X.exe"`

### 3. Documentation Files
- [ ] `windows/INSTALL_GUIDE_WINDOWS.md` - References to installer filename
- [ ] `windows/README_FOR_USERS.txt` - References to version
- [ ] `windows/WINDOWS_INSTALLER.md` - Multiple references to installer filename
- [ ] `linux/PACKAGE_INFO.md` - References to .deb filename
- [ ] `linux/README.md` - References to .deb filename
- [ ] `windows/README.md` - References to version
- [ ] `build_scripts/README.md` - References to version
- [ ] `REVIEW_SUMMARY.md` - Package filenames
- [ ] `PROJECT_STRUCTURE.md` - Package filenames
- [ ] `PACKAGE_SUMMARY.md` - Download links and filenames
- [ ] `experimental/README.md` - Version references

### 4. Build Scripts
- [ ] `windows/build_windows_installer.bat` - Line 6: `set VERSION=X.X.X`
- [ ] `build_scripts/build_windows.bat` - Line 123: `echo Version: X.X.X`

## Quick Update Script (Future Enhancement)

In the future, you could create a script to automate version updates:

```bash
#!/bin/bash
# update_version.sh
NEW_VERSION=$1
OLD_VERSION=$(cat VERSION)

# Update VERSION file
echo "$NEW_VERSION" > VERSION

# Use sed to replace in all files
find . -type f \( -name "*.md" -o -name "*.bat" -o -name "*.iss" -o -name "*.nsi" -o -name "control" \) \
  -exec sed -i "s/$OLD_VERSION/$NEW_VERSION/g" {} +

echo "Version updated from $OLD_VERSION to $NEW_VERSION"
echo "Please review changes with: git diff"
```

## Version Numbering Scheme

JobDocs uses semantic versioning: `MAJOR.MINOR.PATCH[-STAGE]`

- **MAJOR**: Breaking changes (e.g., 1.0.0 → 2.0.0)
- **MINOR**: New features, backwards compatible (e.g., 0.2.0 → 0.3.0)
- **PATCH**: Bug fixes (e.g., 0.2.0 → 0.2.1)
- **STAGE**: Development stage (alpha, beta, rc1, etc.)

**Important:** The version must be in "major.minor.patch" format or "major.minor.patch-stage" format.
Do not use 4-part versions like "1.2.3.4" as this will cause build failures in the Windows installer.

### Examples
- `0.2.0-alpha` - Second minor version, alpha stage
- `0.2.1-alpha` - Alpha with bug fixes
- `0.2.0-beta` - Beta release
- `1.0.0` - First stable release

## Pre-Release Checklist

Before releasing a new version:

1. Update all version numbers using the checklist above
2. Update `CHANGELOG.md` with changes
3. Test on clean systems (both Windows and Linux)
4. Build both installers
5. Create git tag: `git tag -a vX.X.X -m "Version X.X.X"`
6. Push with tags: `git push origin main --tags`
7. Create GitHub release with built packages
8. Update README.md if necessary

## Notes

- The `VERSION` file is the authoritative source
- Documentation files use the version in example filenames and commands
- Build scripts and installer configs must match exactly
- Always update `CHANGELOG.md` before releasing
