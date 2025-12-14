# Getting Started with JobDocs

This guide will help you get up and running with JobDocs quickly.

## Installation

### 1. Install Python Dependencies

#### On Debian/Ubuntu:
```bash
sudo apt install python3-pyqt6
```

#### On Arch Linux:
```bash
sudo pacman -S python-pyqt6
```

#### Using pip (all platforms):
```bash
pip install PyQt6
```

### 2. Run the Application

```bash
python main.py
```

## Initial Configuration

When you first run JobDocs, you'll need to configure your directories:

### Step 1: Open Settings

1. Click **File → Settings** in the menu bar

### Step 2: Configure Directories

**Required Settings:**
- **Blueprints Directory**: Where all blueprint files will be stored centrally
  - Example: `/path/to/blueprints` or `C:\Blueprints`

- **Customer Files Directory**: Where job folders will be created
  - Example: `/path/to/customer-files` or `C:\CustomerFiles`

**Optional Settings (for ITAR compliance):**
- **ITAR Blueprints Directory**: Separate storage for ITAR blueprints
- **ITAR Customer Files Directory**: Separate job folders for ITAR jobs

### Step 3: Choose Link Type

**Hard Link (Recommended)**
- Saves disk space - blueprint appears in both locations but only uses space once
- Files automatically stay in sync
- **Requirement**: Both directories must be on the same drive/partition

**Symbolic Link**
- Works across different drives
- Original file must not be moved or renamed

**Copy**
- Duplicates files (uses double space)
- Safest option if unsure

### Step 4: Set Blueprint Extensions

Default blueprint file extensions:
- `.pdf`
- `.dwg`
- `.dxf`

Files with these extensions will be:
1. Copied to the blueprints directory
2. Linked to job folders

Files with other extensions will be copied directly to job folders only.

## Your First Quote

Let's create a sample quote:

### 1. Go to Create Quote Tab

Click on the **Create Quote** tab at the top.

### 2. Fill in Quote Information

- **Customer**: Enter a customer name (e.g., "Acme Corporation")
- **Quote #**: Enter a quote number (e.g., "Q12345")
- **Description**: Brief description (e.g., "Widget Assembly")
- **Drawings** (optional): Comma-separated drawing numbers (e.g., "DWG-001, DWG-002")

### 3. Add Files (Optional)

You can drag and drop files into the drop zone, or leave it empty for now.

### 4. Create the Quote

Click **Create Quote && Link Files**

JobDocs will create:
```
Customer Files/
└── Acme Corporation/
    └── Quotes/
        └── Q12345_Widget Assembly_DWG-001-DWG-002/
            └── (any files you added)
```

## Your First Job

Now let's create a job:

### 1. Go to Create Job Tab

Click on the **Create Job** tab.

### 2. Fill in Job Information

- **Customer**: Select "Acme Corporation" (now appears in dropdown!)
- **Job #**: Enter job number (e.g., "12345")
  - You can also use ranges: "12345-12350" creates 6 jobs
- **Description**: Brief description (e.g., "Final Assembly")
- **Drawings** (optional): Drawing numbers (e.g., "DWG-001, DWG-002")

### 3. Add Files (Optional)

Drag and drop files:
- **Blueprint files** (.pdf, .dwg, .dxf): Copied to blueprints folder and linked to job
- **Other files**: Copied directly to job folder

### 4. Create the Job

Click **Create Job && Link Files**

JobDocs will create:
```
Customer Files/
└── Acme Corporation/
    └── 12345_Final Assembly_DWG-001-DWG-002/
        └── job documents/
            ├── blueprint.pdf (linked from blueprints)
            └── other_file.doc (copied)

Blueprints/
└── Acme Corporation/
    └── blueprint.pdf (original)
```

## Using Copy From

The **Copy From...** button lets you copy information from existing quotes or jobs:

1. Click **Copy From...** button
2. Type to search for existing quotes/jobs
3. Double-click a result
4. The form fills in automatically with that quote/job's information
5. Modify as needed and create

## Bulk Creation

To create multiple jobs at once:

### 1. Go to Bulk Create Tab

### 2. Enter CSV Data

Format: `Customer, Job Number, Description, Drawing1, Drawing2...`

Example:
```
Acme Corporation, 12346, Machined Part, DWG-003
Acme Corporation, 12347, Welded Assembly, DWG-004, DWG-005
Boeing Aerospace, 20001, Wing Bracket, DWG-101
```

### 3. Validate

Click **Validate** to check for:
- Missing required fields
- Duplicate job numbers
- Formatting errors

### 4. Create All

Click **Create All Jobs** to create all valid jobs.

You can also use **Import CSV** to load from a .csv file.

## Common Tasks

### Adding Files to Existing Jobs

1. Go to **Add to Job** tab
2. Select customer from dropdown
3. Navigate to the job in the tree
4. Drag and drop files
5. Choose destination:
   - **Blueprints Only**: Adds to blueprints folder
   - **Job Folder Only**: Adds to job folder
   - **Both**: Copies to blueprints and links to job

### Searching for Jobs

1. Go to **Search** tab
2. Enter search term (customer name, job number, description, or drawing)
3. Choose search mode:
   - **Strict Format**: Fast search for properly formatted jobs
   - **Search All Folders**: Comprehensive search (slower)
4. Double-click results to open job folder
5. Right-click for options (copy path, open location)

### Importing Blueprints

If you just want to add blueprints without creating a job:

1. Go to **Import Blueprints** tab
2. Select or enter customer name
3. Drag and drop blueprint files
4. Click **Import Files**

Files are copied to the blueprints folder and can be linked to jobs later.

### Viewing History

The **History** tab shows:
- Recent jobs created
- Recent quotes created
- Quick access to job folders
- Double-click to open

## Tips

### Best Practices

1. **Use consistent naming**: Job numbers should follow a pattern
2. **Add drawings**: Including drawing numbers helps with search
3. **Link, don't copy**: Use hard links to save disk space
4. **Validate bulk data**: Always click Validate before creating bulk jobs

### Keyboard Shortcuts

- **Tab through fields**: Use Tab key to move between form fields
- **Enter to submit**: Press Enter in most forms to create job/quote
- **Ctrl+C**: Copy selected search result path

### Duplicate Detection

JobDocs automatically prevents duplicate job numbers:
- Checks history before creation
- Searches file system for existing jobs
- Shows clear warning with existing job location
- Useful for preventing accidental overwrites

### ITAR Jobs

To create ITAR-controlled jobs:

1. Check the **ITAR Job** checkbox
2. Job will be created in ITAR directories (must be configured)
3. ITAR jobs appear with **[ITAR]** prefix in search results
4. Kept completely separate from non-ITAR jobs

## Troubleshooting

### "Directories not configured" error

**Solution**: Go to **File → Settings** and configure your directories.

### Hard links fail

**Cause**: Directories are on different drives/partitions.

**Solution**:
- Move directories to same drive, OR
- Change link type to "Symbolic Link" or "Copy" in settings

### Customer not showing in dropdown

**Cause**: Customer list is populated from existing customer folders.

**Solution**:
- Type the customer name manually (dropdown is editable)
- Or create the first job/quote, then customer appears in dropdown

### Can't find a job in search

**Try**:
1. Use **Search All Folders** mode for comprehensive search
2. Check ITAR checkbox if it's an ITAR job
3. Search for partial terms (e.g., "123" finds "12345")

## Next Steps

- Explore the modular system: See [MODULAR_SYSTEM.md](MODULAR_SYSTEM.md)
- Create custom modules: See `modules/_template/`
- Learn about the architecture: See `docs/modular-migration/`
- Build standalone app: See [BUILD.md](BUILD.md)

## Getting Help

- **GitHub Issues**: https://github.com/i-machine-things/JobDocs/issues
- **Documentation**: See `docs/` folder
- **Examples**: See `sample_files/` and `test_jobs.csv`

---

Happy organizing! 🎉
