# Release Checklist for JobDocs

Use this checklist when preparing a new release.

## Pre-Build

- [ ] Update version number in `version_info.py`
- [ ] Update version in `JobDocs-installer.iss` (line 5: `#define MyAppVersion`)
- [ ] Update CHANGELOG.md with release notes
- [ ] Test application thoroughly on development machine
- [ ] Run all manual tests (create job, bulk create, search, import)
- [ ] Test ITAR functionality
- [ ] Verify hard links, symbolic links, and copy modes work

## Build Process

- [ ] Ensure you're on a clean Windows machine or VM
- [ ] Pull latest code from repository
- [ ] Run `build_installer.bat` or `build_installer.ps1`
- [ ] Verify no errors during build
- [ ] Check that icon.ico was created/used
- [ ] Verify executable size is reasonable (< 150 MB)

## Testing the Executable

- [ ] Run `dist\JobDocs.exe` directly
- [ ] Test on a machine WITHOUT Python installed
- [ ] Verify all tabs work (Create Job, Add to Job, Bulk Create, Search, Import, History)
- [ ] Test Settings dialog
- [ ] Create a test job
- [ ] Add files to existing job
- [ ] Search for jobs
- [ ] Check that config is saved correctly in AppData

## Testing the Installer

- [ ] Run the installer on a clean Windows machine
- [ ] Verify installation to Program Files
- [ ] Check Start Menu shortcut works
- [ ] Check Desktop shortcut (if selected)
- [ ] Launch application from shortcuts
- [ ] Test the initial directory setup wizard
- [ ] Verify directories are created
- [ ] Run the application and create a test job
- [ ] Test uninstaller
- [ ] Verify all files are removed after uninstall
- [ ] Check that user data is preserved in AppData

## Distribution

- [ ] Create GitHub Release
- [ ] Upload installer to GitHub Releases
- [ ] Add release notes
- [ ] Tag the release in git
- [ ] Update README.md with download link
- [ ] Test download link
- [ ] Announce release (if applicable)

## Post-Release

- [ ] Monitor for bug reports
- [ ] Test installer downloads from different sources
- [ ] Check Windows SmartScreen warnings
- [ ] Document any known issues
- [ ] Plan next release features

## Version Numbering

Use Semantic Versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes, major features
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, small improvements

Examples:
- `1.0.0` - Initial release
- `1.0.1` - Bug fix
- `1.1.0` - New feature added
- `2.0.0` - Major overhaul

## Files to Update for New Version

1. `version_info.py` - `__version__` variable
2. `JobDocs-installer.iss` - `MyAppVersion` define
3. `CHANGELOG.md` - Add release notes
4. `README.md` - Update version badges (if any)

## Code Signing (Optional but Recommended)

If you have a code signing certificate:
- [ ] Sign the executable with `signtool`
- [ ] Sign the installer
- [ ] This reduces Windows SmartScreen warnings

Example:
```cmd
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist\JobDocs.exe
```
