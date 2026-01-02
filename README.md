# JobDocs

A modular tool for managing blueprint files and customer job directories with support for file linking, ITAR compliance, and comprehensive job tracking.

## Features

- **Modular Plugin Architecture** - Extensible system with drop-in modules
- **Auto-Generate Numbers** - Automatically generate next sequential job/quote number (starting at 10000)
- **Single and Bulk Job Creation** - Create individual jobs or import multiple jobs from CSV
- **Quote Management** - Create quotes that can be converted to jobs
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

#### On Debian/Ubuntu:
```bash
sudo apt install python3-pyqt6
```

#### On Arch Linux:
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
python main.py
```

### First Time Setup

1. Go to **File → Settings**
2. Configure your directories:
   - **Blueprints Directory**: Central storage for all blueprint files
   - **Customer Files Directory**: Where job folders will be created
   - **ITAR Directories**: Optional separate directories for ITAR-controlled projects
3. Choose your link type (Hard Link recommended to save disk space)
4. Set blueprint file extensions (default: .pdf, .dwg, .dxf)

### Creating Quotes

1. Go to the **Create Quote** tab
2. Enter customer name (auto-completes from existing customers)
3. Enter quote number(s):
   - Click **Auto** button to auto-generate next number (starts at 10000)
   - Or manually enter - supports ranges like Q12345-Q12350
4. Enter description
5. Optionally add drawing numbers (comma-separated)
6. Add files by dragging/dropping
7. Click **Create Quote**
8. Use **Copy From...** to copy information from existing quotes or jobs

### Creating Jobs

#### Single Job Creation
1. Go to the **Create Job** tab
2. Enter customer name (auto-completes from history)
3. Enter job number(s):
   - Click **Auto** button to auto-generate next number (starts at 10000)
   - Or manually enter - supports:
     - Single: `12345`
     - Multiple: `12345, 12346, 12347`
     - Range: `12345-12350`
4. Enter description
5. Optionally add drawing numbers (comma-separated)
6. Add files by dragging/dropping or browsing
7. Click **Create Job**
8. Use **Copy From...** to copy information from existing quotes or jobs

#### Bulk Job Creation
1. Go to the **Bulk Create** tab
2. Enter jobs in CSV format (one per line):
   ```
   Customer Name, Job Number, Description, Drawing1, Drawing2...
   ```
3. Click **Validate** to check for errors
4. Click **Create All Jobs**
   - Automatically detects and skips duplicate jobs
   - Shows warning if duplicates are found

Or import from CSV file using the **Import CSV** button.

### Managing Existing Jobs

Use the **Add to Job** tab to:
- Browse existing job folders
- Add files to existing jobs
- Filter by customer or ITAR status
- Choose destination (blueprints only, job folder only, or both)

### Importing Blueprints

Use the **Import Blueprints** tab to:
- Import blueprint files directly to the blueprints directory
- Select customer name
- Choose ITAR or standard blueprints directory
- Automatically creates customer folders

### Searching

The **Search** tab provides powerful search capabilities:
- Search by customer name, job number, description, or drawing
- Two search modes:
  - **Search All Folders** (Legacy mode): Full recursive search through all folders
    - Handles inconsistent folder structures from legacy files
    - Optional: Also search blueprints directories
    - Slower but comprehensive
  - **Strict Format** (Faster): Only searches properly formatted job folders
    - Filter by specific fields (customer, job #, description, drawings)
    - Much faster for well-organized structures
- Double-click results to open job folders
- Right-click for context menu (copy path, open location)

## File Structure

JobDocs creates the following directory structure:

```
Customer Files Directory/
├── Customer Name/
│   ├── 12345_Job Description/
│   │   └── job documents/
│   │       ├── blueprint1.pdf (hard link)
│   │       └── other_file.doc (copy)
│   ├── 12346_Another Job/
│   │   └── ...
│   └── Quotes/
│       └── Q12345_Quote Description/
│           ├── blueprint1.pdf (hard link)
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

## Modular Architecture

JobDocs uses a plugin-based architecture:

### Available Modules
1. **Create Quote** - Quote creation and management
2. **Create Job** - Job folder creation with duplicate detection
3. **Add to Job** - Add files to existing jobs
4. **Bulk Create** - Bulk job creation from CSV
5. **Search** - Advanced job search
6. **Import Blueprints** - Import blueprints to customer folders
7. **History** - View recent job history
8. **Reporting** (Experimental) - Generate and export reports

### Creating Custom Modules

See [MODULAR_SYSTEM.md](MODULAR_SYSTEM.md) for details on creating custom modules.

## Development

### Project Structure
```
JobDocs/
├── main.py              # Main application
├── core/                # Core framework
│   ├── base_module.py   # Module base class
│   ├── app_context.py   # Shared application context
│   └── module_loader.py # Auto module discovery
├── shared/              # Shared utilities
│   ├── utils.py         # File operations, parsing
│   └── widgets.py       # Custom UI widgets
├── modules/             # Plugin modules
│   ├── quote/           # Quote module
│   ├── job/             # Job module
│   ├── bulk/            # Bulk creation module
│   └── ...
├── settings_dialog.py   # Settings UI
├── docs/                # Documentation
├── old/                 # Legacy code (archived)
└── README.md            # This file
```

### Building

See [BUILD.md](BUILD.md) for instructions on creating standalone executables.

### Testing

See [TESTING.md](TESTING.md) for testing instructions.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

For issues or questions, please visit:
https://github.com/i-machine-things/JobDocs

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

### Development Notes
- The modular architecture allows for easy extension and customization
- Each module is self-contained and can be developed independently
- Use `modules/_template/` as a starting point for new modules

---

**Note**: ITAR (International Traffic in Arms Regulations) compliance is the user's responsibility. This tool only provides organizational separation of ITAR and non-ITAR files.

## Acknowledgments

This project was developed with assistance from Claude (Anthropic), an AI assistant that helped with code architecture, documentation, testing, and packaging solutions.
