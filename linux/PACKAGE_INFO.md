# JobDocs Debian Package

A `.deb` package has been created for JobDocs v0.2.0-alpha.

## Package Details

- **File**: `jobdocs_0.2.0-alpha_all.deb`
- **Size**: 58 KB
- **Architecture**: all (platform-independent)
- **Dependencies**: python3 (>= 3.8), python3-pyqt6

## Installation

To install the package:

```bash
sudo dpkg -i jobdocs_0.2.0-alpha_all.deb
sudo apt-get install -f  # Install any missing dependencies
```

Or using apt (automatically handles dependencies):

```bash
sudo apt install ./jobdocs_0.2.0-alpha_all.deb
```

## Usage

After installation, you can run JobDocs in two ways:

1. From the command line:
   ```bash
   jobdocs
   ```

2. From the application menu:
   - Look for "JobDocs" in your applications menu under Office/Database

## Package Contents

The package installs:

- Application files: `/opt/jobdocs/`
- Launcher script: `/usr/bin/jobdocs`
- Desktop entry: `/usr/share/applications/jobdocs.desktop`
- Icon: `/usr/share/pixmaps/jobdocs.png`

## Uninstallation

To remove the package:

```bash
sudo apt remove jobdocs
```

Or:

```bash
sudo dpkg -r jobdocs
```

## Notes

- User configuration and data are stored in `~/.local/share/JobDocs/`
- Uninstalling the package does not remove user data
- The package follows Debian packaging standards
