# JobDocs

A modular tool for managing blueprint files and customer job directories with support for file linking, ITAR compliance, and comprehensive job tracking.

## Screenshots

| Quote | Job |
|---|---|
| ![Quote tab](docs/screenshots/quote_create_new.png) | ![Job tab](docs/screenshots/job_create_new.png) |

| Search | Import Blueprints |
|---|---|
| ![Search tab](docs/screenshots/search.png) | ![Import Blueprints tab](docs/screenshots/import_blueprints.png) |

![Setup wizard](docs/screenshots/setup_wizard.png)

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
- **Email Drag-and-Drop** - Drag emails directly onto any drop zone and attachments are extracted automatically. Supports Outlook / O365 (saves as `.msg`, requires `pywin32` on Windows), classic Outlook desktop, and Betterbird / Thunderbird on Linux (attachments extracted from the `.eml`). Image attachments (jpg, png, etc.) are skipped by default and can be toggled in Settings. Zip attachments are automatically extracted — the files inside are added directly to the file list.
- **PDF Preview** - Drop zone file list shows a live preview of PDF files (requires `pymupdf`)
- **Cross-Platform** - Works on Windows and Linux
- **CLI Pre-fill** - Launch with `--j_no`, `--desc`, `--customer` etc. to open with fields already populated — useful for integrating with external systems

## Installation

### Windows

The [latest release](https://github.com/i-machine-things-org/JobDocs/releases/latest) has
two Windows installers — download whichever fits the machine:

- **`JobDocs-<version>-windows-setup.exe`** — the full app: Job, Quote, Bulk Create,
  Search, Settings, plugins, everything.
- **`JobDocs-Kiosk-<version>-windows-setup.exe`** — **JobDocs Kiosk**, a search-only
  build for shared/shop-floor machines that should look up jobs but not create, edit, or
  browse the filesystem. Only the Search tab's module code is on disk (the Job, Quote,
  and Bulk tabs are never installed, not merely hidden); the Settings dialog is present
  but any changes made there don't persist. It never indexes or searches ITAR-controlled
  directories, and its Search tab offers no "open folder" / "copy path" — only printing
  and viewing individual files. It installs and updates independently of the full app
  (separate Start Menu entry, separate uninstall) and can coexist with it on the same
  machine.

Each installer offers:

- **Install for me only** — installs to `%LOCALAPPDATA%\Programs\<app>` (no admin required)
- **Install for all users** — installs to `C:\Program Files\<app>` (requires admin/UAC)

Both options add the app's exe to `PATH` so it is callable from any terminal.

JobDocs Kiosk's file-level restriction is a UI/footprint measure, not account-level access
control — the same Windows account running it could still install the full app itself
alongside it (there are no write-capable modules present in the Kiosk install to load
either way, and Kiosk detection is a marker baked into the installer payload at build
time, not a file it writes and a user could delete afterward). To actually restrict what
a shared machine's user can do, run it under a separately managed Windows account with
the installation directory locked down.

JobDocs Kiosk has no first-run setup wizard (a write-capable admin tool, so it isn't
installed) — the JobDocs Kiosk installer itself prompts for the customer files, ITAR
customer files, blueprints, and ITAR blueprints directories instead. Leave the ITAR
fields blank if the site doesn't use them. Re-run the installer to change these later;
it pre-fills your previous answers. The Settings dialog is present (File → Settings),
but its changes are blocked from persisting, the same way the rest of the app's writes
are — see the read-only note above.

### Linux (Flatpak)

Add the JobDocs repository and install:

```bash
flatpak remote-add --user --from jobdocs \
  https://i-machine-things-org.github.io/JobDocs/jobdocs.flatpakrepo
flatpak install jobdocs io.github.i_machine_things.JobDocs
```

Or download the `.flatpak` bundle directly from the [latest release](https://github.com/i-machine-things-org/JobDocs/releases/latest) and install it:

```bash
flatpak install JobDocs-linux.flatpak
```

### From Source (Development)

Requires Python 3.12+ and PyQt6.

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

#### Optional dependencies:
```bash
pip install pywin32            # Windows — enables Outlook/O365 drag-and-drop
pip install pymupdf            # All platforms — enables PDF preview in file lists
pip install pandas openpyxl    # enables Report Fixer plugin (if installed)
```

Run from source:
```bash
python main.py
```

## Usage

### First Time Setup

On first launch a setup wizard walks you through configuration. You can re-run it anytime via **Help → Run Setup Wizard**.

1. Go to **File → Settings**
2. Configure your directories:
   - **Blueprints Directory** — central storage for all blueprint files
   - **Customer Files Directory** — where job folders will be created
   - **ITAR Directories** — optional separate directories for ITAR-controlled projects
3. Choose your link type (Hard Link recommended to save disk space)
4. Set blueprint file extensions (default: `.pdf`, `.dwg`, `.dxf`)
5. Toggle **Skip image attachments** to filter out images when dragging emails from Outlook (enabled by default)

### Command-Line Pre-fill

External programs can launch JobDocs with form fields pre-populated. The app opens normally and the specified fields are filled in automatically.

**Windows:**
```powershell
JobDocs.exe --j_no 12345 --desc "flange machining" --customer "Acme Corp" --po_no PO-9876
JobDocs.exe --q_no Q10042 --desc "shaft assembly" --customer "Acme Corp"
```

You may need to open a new terminal after installing for `PATH` to take effect. External programs can also call the exe directly by full path:
- Per-user install: `%LOCALAPPDATA%\Programs\JobDocs\JobDocs.exe`
- All-users install: `%ProgramFiles%\JobDocs\JobDocs.exe`

**Linux (Flatpak):**
```bash
flatpak run io.github.i_machine_things.JobDocs --j_no 12345 --desc "flange machining"
flatpak run io.github.i_machine_things.JobDocs --q_no Q10042 --desc "shaft assembly"
```

**From source:**
```bash
python main.py --j_no 12345 --desc "flange machining"
```

**Available arguments:**

| Argument | Tab | Field |
|---|---|---|
| `--customer NAME` | Job / Quote | Customer name |
| `--j_no NUMBER` | Job | Job number |
| `--q_no NUMBER` | Quote | Quote number |
| `--po_no NUMBER` | Job | PO number |
| `--po_line LINE` | Job | PO line |
| `--desc TEXT` | Job / Quote | Description |
| `--drawings NUMS` | Job / Quote | Drawing numbers (comma-separated) |
| `--revision REV` | Job | Revision |

- If `--j_no` is present the app opens on the **Job** tab; if `--q_no` is present (and no `--j_no`) it opens on the **Quote** tab.
- Unrecognised arguments are forwarded to Qt (e.g. `--platform`, `--style`).

#### Integration examples

**Python**

```python
import subprocess
import os

exe = os.path.expandvars(r"%LOCALAPPDATA%\Programs\JobDocs\JobDocs.exe")

# Open Job tab with all fields pre-filled
subprocess.Popen([
    exe,
    "--customer", "Acme Corp",
    "--j_no",     "12345",
    "--po_no",    "PO-9876",
    "--po_line",  "1",
    "--desc",     "flange machining",
    "--drawings", "DWG-001,DWG-002",
    "--revision", "A",
])
```

**VBA (Excel / Access / JobBOSS)**

```vba
Sub OpenInJobDocs()
    Dim wsh As Object
    Dim exePath As String

    Set wsh = CreateObject("WScript.Shell")
    exePath = wsh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\JobDocs\JobDocs.exe")

    ' Pull values from the current JobBOSS Job Entry record
    wsh.Run """" & exePath & """" & _
             " --customer """ & Forms!Jobs!Customer_ID    & """" & _
             " --j_no """     & Forms!Jobs!Job_Number     & """" & _
             " --po_no """    & Forms!Jobs!Cust_PO        & """" & _
             " --po_line """  & Forms!Jobs!PO_Line        & """" & _
             " --desc """     & Forms!Jobs!Description    & """" & _
             " --revision """ & Forms!Jobs!Revision       & """", _
             1, False

    Set wsh = Nothing
End Sub
```

Both callers launch JobDocs as a non-blocking GUI process and return immediately.
For an all-users install replace `%LOCALAPPDATA%\Programs` with `%ProgramFiles%`.

### Creating Quotes

1. Go to the **Quote** tab → **Create New**
2. Enter customer name (auto-completes from existing customers)
3. Enter quote number(s):
   - Click **Auto** to generate the next sequential number (starts at 10000)
   - Or enter manually — supports ranges like `Q12345-Q12350`
4. Enter description
5. Optionally add drawing numbers (comma-separated)
6. Add files by dragging/dropping
7. Click **Create Quote**
8. Use **Copy From...** to copy details from an existing quote or job
9. Use **Link Drawings** to link drawing files directly to the quote

### Creating Jobs

#### Single Job Creation
1. Go to the **Job** tab → **Create New**
2. Enter customer name (auto-completes from history)
3. Enter job number(s):
   - Click **Auto** to generate the next sequential number (starts at 10000)
   - Or enter manually — supports:
     - Single: `12345`
     - Multiple: `12345, 12346, 12347`
     - Range: `12345-12350`
4. Enter description
5. Optionally add drawing numbers (comma-separated)
6. Optionally add a PO number
7. Add files by dragging/dropping or browsing
8. Click **Create Job**
9. Use **Copy From...** to copy details from an existing quote or job
10. Use **Link Drawings** to link drawing files directly to the job

#### Bulk Job Creation
1. Go to the **Bulk Create** tab
2. Enter jobs in CSV format (one per line):
   ```
   Customer Name, Job Number, Description, Drawing1, Drawing2...
   ```
3. Click **Validate** to check for errors
4. Click **Create All Jobs** — duplicates are detected and skipped automatically

Or import from a CSV file using the **Import CSV** button.

### Managing Existing Jobs

Use the **Job** tab → **Add to Existing** to:
- Browse existing job folders
- Add files to existing jobs
- Filter by customer or ITAR status
- Choose destination (blueprints only, job folder only, or both)

### Importing Blueprints

Use the **Import Blueprints** tab to:
- Import blueprint files directly to the blueprints directory
- Select customer name
- Choose ITAR or standard blueprints directory
- Customer folders are created automatically

### Searching

The **Search** tab provides powerful search capabilities:
- Search by customer name, job number, description, or drawing number
- Two search modes:
  - **Search All Folders** (Legacy mode) — full recursive search; handles inconsistent folder structures from legacy files; slower but comprehensive
  - **Strict Format** (Faster) — only searches properly formatted job folders; filter by specific fields (customer, job #, description, drawings)
- Click column headers to sort results
- Double-click a result to open the job folder
- Right-click for context menu (copy path, open location, print)

## File Structure

JobDocs creates the following directory structure:

```
Customer Files Directory/
├── Customer Name/
│   ├── 12345_Job Description/
│   │   └── job documents/
│   │       ├── blueprint1.pdf  (hard link)
│   │       └── other_file.doc  (copy)
│   ├── 12346_Another Job/
│   │   └── ...
│   └── Quotes/
│       └── Q12345_Quote Description/
│           ├── blueprint1.pdf  (hard link)
│           └── ...

Blueprints Directory/
└── Customer Name/
    ├── blueprint1.pdf  (original)
    ├── blueprint2.dwg
    └── ...
```

## Configuration

Configuration files are stored in platform-specific locations:

- **Windows**: `C:\Users\<Username>\AppData\Local\JobDocs`
- **Linux (Flatpak)**: `~/.var/app/io.github.i_machine_things.JobDocs/data/JobDocs`
- **Linux (source)**: `~/.local/share/JobDocs`
- **macOS**: `~/Library/Application Support/JobDocs`

Files stored:
- `settings.json` — application settings
- `history.json` — recent jobs and customer history

## Link Types

### Hard Link (Recommended)
- Same file appears in multiple locations
- Takes no extra disk space
- Files stay in sync automatically
- **Limitation**: only works on the same drive/partition

### Symbolic Link
- Creates a shortcut/reference to the original file
- Works across different drives
- Original file must not be moved

### Copy
- Duplicates the file
- Uses double disk space
- Files are independent

## Modular Architecture

JobDocs uses a plugin-based architecture:

### Built-in Modules
1. **Quote** — Quote creation and management
2. **Job** — Job folder creation with duplicate detection
3. **Bulk Create** — Bulk job creation from CSV
4. **Search** — Advanced job search with column sorting and folder tree
5. **Import Blueprints** — Import blueprints to customer folders
6. **History** — View recent job history

### Plugins
- **Report Fixer** — Transforms Excel job reports to match a template layout (separate plugin, install via **File → Install Plugin**)

### Creating Custom Modules

See [modules/_template/README.md](modules/_template/README.md) for details on creating custom modules.

## Development

### Project Structure
```
JobDocs/
├── main.py              # Application entry point
├── core/                # Core framework
│   ├── base_module.py   # Module base class
│   ├── app_context.py   # Shared application context
│   ├── module_loader.py # Dynamic module discovery
│   └── settings_dialog.py # Settings UI
├── shared/              # Shared utilities
│   ├── utils.py         # File operations, parsing
│   ├── widgets.py       # Custom UI widgets
│   └── remote_sync.py   # Remote settings synchronisation
├── modules/             # Built-in plugin modules
│   ├── quote/
│   ├── job/
│   ├── bulk/
│   ├── search/
│   ├── import_bp/
│   ├── history/
│   └── _template/       # Template for custom modules
├── launcher/            # Windows C launcher source
├── build_scripts/       # Inno Setup installer script
├── linux/flatpak/       # Flatpak manifest and metadata
└── .github/workflows/   # CI — build-release.yml produces Windows installer + Flatpak
```

### Building

Releases are built automatically by CI when a `v*` tag is pushed to `master`. To cut a release:

```bash
git tag v1.2.3
git push origin v1.2.3
```

The workflow produces:
- **Windows** — Inno Setup installer bundling the C launcher, embedded Python 3.12, and app source
- **Linux** — Flatpak bundle

Use `workflow_dispatch` on `build-release.yml` to test CI without tagging.

## License

GNU General Public License v3 (GPL v3) — see [LICENSE](LICENSE) for details.

## Support

For issues or questions: https://github.com/i-machine-things-org/JobDocs/issues

## Contributing

Contributions are welcome. Please submit issues or pull requests.

---

**Note**: ITAR (International Traffic in Arms Regulations) compliance is the user's responsibility. This tool only provides organisational separation of ITAR and non-ITAR files.

## Acknowledgments

This project was developed with assistance from Claude (Anthropic), an AI assistant that helped with code architecture, documentation, testing, and packaging solutions.
