# JobDocs

A tool for managing blueprint files and customer job directories with support for file linking, ITAR compliance, and comprehensive job tracking.

## Features

- **Single and Bulk Job Creation** - Create individual jobs or import multiple jobs from CSV
- **Blueprint File Management** - Centralized blueprint storage with hard linking to save disk space
- **ITAR Support** - Separate directories and workflows for ITAR-controlled projects
- **Advanced Search** - Find jobs by customer, job number, description, or drawing number
- **File Organization** - Automatic folder structure creation and file management
- **Import Tools** - Direct import of files to blueprint folders
- **History Tracking** - Keep track of recent jobs and customer information
- **Cross-Platform** - Works on Windows, macOS, and Linux

## Installation

### Requirements
- Python 3.8 or higher
- PyQt6

### Install Dependencies

#### On Arch Linux (recommended):
```bash
sudo pacman -S python-pyqt6
```

#### Using pip:
```bash
pip install -r requirements.txt
```

Or install PyQt6 directly:
```bash
pip install PyQt6
```

## Usage

Run the application:

```bash
python JobDocs-qt.py
```

### First Time Setup

1. Go to **File → Settings**
2. Configure your directories:
   - **Blueprints Directory**: Central storage for all blueprint files
   - **Customer Files Directory**: Where job folders will be created
   - **ITAR Directories**: Optional separate directories for ITAR-controlled projects
3. Choose your link type (Hard Link recommended to save disk space)
4. Set blueprint file extensions (default: .pdf, .dwg, .dxf)

### Creating Jobs

#### Single Job Creation
1. Go to the **Create Job** tab
2. Enter customer name (auto-completes from history)
3. Enter job number(s) - supports:
   - Single: `12345`
   - Multiple: `12345, 12346, 12347`
   - Range: `12345-12350`
4. Enter description
5. Optionally add drawing numbers (comma-separated)
6. Add files by dragging/dropping or browsing
7. Click **Create Job**

#### Bulk Job Creation
1. Go to the **Bulk Create** tab
2. Enter jobs in CSV format (one per line):
   ```
   Customer Name, Job Number, Description, Drawing1, Drawing2...
   ```
3. Click **Validate** to check for errors
4. Click **Create All Jobs**

Or import from CSV file using the **Import CSV** button.

### Managing Existing Jobs

Use the **Add to Job** tab to:
- Browse existing job folders
- Add files to existing jobs
- Filter by customer or ITAR status
- Choose destination (blueprints only, job folder only, or both)

### Searching

The **Search** tab provides powerful search capabilities:
- Search by customer name, job number, description, or drawing
- Filter by search criteria checkboxes
- Choose between:
  - **All Folders**: Comprehensive search (slower)
  - **Strict Mode**: Only numbered job folders (faster)
- Double-click results to open job folders

## File Structure

JobDocs creates the following directory structure:

```
Customer Files Directory/
├── Customer Name/
│   └── job documents/
│       ├── 12345_Job Description/
│       │   ├── blueprint1.pdf (hard link)
│       │   └── other_file.doc (copy)
│       └── 12346_Another Job/
│           └── ...

Blueprints Directory/
└── Customer Name/
    ├── blueprint1.pdf (original)
    ├── blueprint2.dwg
    └── ...
```

## Configuration

Configuration files are stored in platform-specific locations:
- **Windows**: `C:\Users\<Username>\AppData\Local\JobDocs`
- **macOS**: `~/Library/Application Support/JobDocs`
- **Linux**: `~/.local/share/JobDocs`

Files stored:
- `settings.json` - Application settings
- `history.json` - Recent jobs and customer history

## Link Types

### Hard Link (Recommended)
- Same file appears in multiple locations
- Takes no extra disk space
- Files stay in sync automatically
- **Limitation**: Only works on same drive/partition

### Symbolic Link
- Creates a shortcut/reference to original file
- Works across different drives
- Original file must not be moved

### Copy
- Duplicates the file
- Uses double disk space
- Files are independent

## License

MIT License - see [LICENSE](LICENSE) file for details.

**Note on PyQt6 Licensing:**
- PyQt6 is dual-licensed under GPL v3 and commercial license
- For **internal company use** (not distributing to others): GPL is fine and free
- For **commercial distribution**: Purchase commercial PyQt6 license from Riverbank Computing
- Alternative: Switch to PySide6 (LGPL) for free commercial distribution rights

## Support

For issues or questions, please visit:
https://github.com/i-machine-things/JobDocs

## Development

### Project Structure
- `JobDocs-qt.py` - Main application file
- `LICENSE` - MIT License
- `requirements.txt` - Python dependencies
- `README.md` - This file

### Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

---

**Note**: ITAR (International Traffic in Arms Regulations) compliance is the user's responsibility. This tool only provides organizational separation of ITAR and non-ITAR files.
