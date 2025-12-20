# JobDocs Testing Release v0.3.0

**Release Date:** December 18, 2024
**Version:** 0.3.0
**Status:** Testing Release

## 🚀 What's New

### Major Features

#### Auto-Setup Wizard
- **One-Click Team Deployment**: Complete setup in 5 simple steps
- **Automatic Directory Creation**: Creates standard folder structure automatically
- **Network Configuration**: Auto-configures shared settings, history, and users files
- **Admin Account Creation**: Sets up initial admin user during setup
- **Pre-configured Defaults**: Applies all recommended settings automatically

#### Enhanced User Management
- **Admin Privileges**: Create admin users through User Management dialog
- **Role-Based Access Control**: Separate admin and regular user permissions
- **Restricted Settings**: Regular users can't modify critical paths and configurations
- **Settings Access Control**: Admin-only sections hidden from regular users

#### Version Management Tools
- **Semantic Versioning**: Full SemVer 2.0.0 support
- **Cross-Platform Scripts**: Linux/macOS (bash), Windows (batch), Python
- **Version Bumping**: Easy major/minor/patch version updates
- **Pre-release Support**: Alpha, beta, RC tags

### Improvements

#### UI/UX
- **Height Constraints**: All dialogs limited to 700px with scroll bars
- **Scroll Areas**: OOBE wizard pages scroll when content exceeds height
- **Better Organization**: Clean root directory, organized documentation

#### Documentation
- **Consolidated Docs**: All documentation in `/docs` directory
- **Version Tools**: Organized in `/version` directory
- **Comprehensive Index**: Easy navigation with README files
- **Updated Guides**: Network setup, user auth, version management

#### OOBE (Out-of-Box Experience)
- **Auto-Setup Option**: Select root folder and auto-create entire structure
- **Network Users**: Creates initial admin user in shared users file
- **Skip Manual Steps**: Automatically enables team features and completes wizard
- **Improved Flow**: Streamlined first-run experience

### Bug Fixes
- Fixed user list not populating in User Management dialog
- Fixed network users file fallback behavior
- Fixed OOBE wizard height exceeding screen limits
- Corrected settings priority for network users path

## 📦 Installation

### Linux

1. Download `JobDocs-testing-v0.3.0-linux-x86_64.tar.gz`
2. Extract the archive:
   ```bash
   tar -xzf JobDocs-testing-v0.3.0-linux-x86_64.tar.gz
   ```
3. Run JobDocs:
   ```bash
   ./jobdocs
   ```

### First Run Setup

When you first launch JobDocs, you'll see the OOBE wizard:

**Option 1: Auto-Setup (Recommended for Teams)**
1. Click "🔍 Select Root Folder & Auto-Setup"
2. Choose your network share location
3. Confirm the directory structure
4. Enter admin username and password
5. Done! Everything is configured automatically

**Option 2: Manual Setup**
1. Configure directories manually
2. Set up network sharing (optional)
3. Enable user authentication (optional)
4. Complete the wizard

## ⚠️ Important Notes

### Testing Release
This is a **testing release** for evaluation purposes:
- Test all features thoroughly
- Report any bugs or issues
- Provide feedback on the auto-setup experience
- **Do not use in production** until stable release

### Network Setup
For team deployments:
1. Admin runs auto-setup on first machine
2. Creates network share structure (blueprints, customer files, .jobdocs)
3. Creates admin and user accounts
4. Other users can auto-search for shared users file in OOBE

### Upgrading
If upgrading from a previous version:
- Backup your settings: `~/.local/share/JobDocs/`
- Settings format is compatible
- User auth must be configured via OOBE or manual setup

## 🔧 Configuration

### Admin Module
The admin module is **disabled by default** (`_admin`).

To enable admin features:
```bash
mv modules/_admin modules/admin
```

Admin features include:
- Setup Wizard
- User Management
- Team Settings
- Full configuration access

### User Authentication
Enable via OOBE wizard or manual configuration:
```json
{
  "user_auth_enabled": true,
  "network_users_path": "\\\\server\\shared\\.jobdocs\\shared_users.json"
}
```

## 📋 System Requirements

- **OS**: Linux (x86_64)
- **Python**: Not required (standalone binary)
- **Display**: Minimum 1024x768 resolution
- **Network**: Required for team sharing features
- **Disk**: 200MB free space

## 🐛 Known Issues

None reported for this release.

## 📝 Changelog

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for detailed version history.

## 📖 Documentation

- **Quick Start**: [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)
- **User Auth**: [docs/USER_AUTH_ARCHITECTURE.md](docs/USER_AUTH_ARCHITECTURE.md)
- **Network Sharing**: [docs/NETWORK_SHARED_SETTINGS.md](docs/NETWORK_SHARED_SETTINGS.md)
- **Version Tools**: [docs/VERSION_MANAGEMENT.md](docs/VERSION_MANAGEMENT.md)
- **All Docs**: [docs/README.md](docs/README.md)

## 🤝 Feedback & Support

- **Issues**: Report at https://github.com/i-machine-things/JobDocs/issues
- **Questions**: Open a discussion on GitHub
- **Testing**: Please test auto-setup feature and report results

---

**Download**: [JobDocs-testing-v0.3.0-linux-x86_64.tar.gz](../../releases/download/v0.3.0-testing/JobDocs-testing-v0.3.0-linux-x86_64.tar.gz)
