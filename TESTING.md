# Testing the Modular Architecture

## Current Status

The modular architecture has 4 completed modules:
- Quote Module
- Job Module
- Add to Job Module
- Bulk Module

The main application (`main.py`) hasn't been created yet, but you can test the modules with the test script.

## How to Test

### Method 1: Test Script (Recommended)

Run the test script to load all completed modules in a simple tabbed interface:

```bash
python test_modular.py
```

or

```bash
./test_modular.py
```

**What it does:**
- Loads your existing `settings.json` if available
- Uses ModuleLoader to discover and load all modules
- Creates a simple tabbed window with each module
- Prints status messages showing which modules loaded successfully

**Expected output:**
```
============================================================
JobDocs Modular Architecture Test
============================================================
Project root: /home/allan/code/JobDocs
Modules dir: /home/allan/code/JobDocs/modules

Loading modules...

✓ Loaded module: Quote
✓ Loaded module: Job
✓ Loaded module: Add to Job
✓ Loaded module: Bulk Create

============================================================
Test window opened. Close the window to exit.
============================================================
```

### Method 2: Use Original Application

The original monolithic version still works:

```bash
python JobDocs-qt.py
```

This runs the old 2897-line version while we complete the migration.

## What You Can Test

With the test script, you can verify:

1. **Module Discovery**: All 4 modules are found and loaded
2. **UI Loading**: Each module's UI displays correctly
3. **Tab Ordering**: Modules appear in correct order (Quote, Job, Add to Job, Bulk)
4. **Settings Integration**: Modules can access your existing settings
5. **Basic Functionality**: Try basic operations in each tab

## Limitations of Test Script

The test script has stub implementations for some callbacks:
- `create_single_job()` - Just prints a message
- `refresh_history()` - Just prints a message
- `populate_customer_lists()` - Just prints a message

These will work properly once we create the full `main.py`.

## Prerequisites

### Required Packages

The modular system requires these Python packages:

```bash
# For Debian/Ubuntu
sudo apt install python3-pyqt6 python3-pyqt6.uic

# Or with pip
pip install PyQt6 PyQt6-tools
```

**Without `python3-pyqt6.uic`**, you'll see this error:
```
ERROR: Failed to load module quote: cannot import name 'uic' from 'PyQt6'
```

## Troubleshooting

### Error: "cannot import name 'uic' from 'PyQt6'"
**Solution**: Install the uic package:
```bash
sudo apt install python3-pyqt6.uic
```

### No modules loaded
- Check that `modules/` directory exists
- Verify each module has a `module.py` file
- Check console output for error messages

### UI file not found errors
- Ensure each module's `ui/` directory has the required .ui files
- Check paths in error messages

### Import errors
- Make sure you're in the project root directory
- Verify `core/` and `shared/` directories exist

## Next Steps

After testing confirms the modules work:
1. Migrate remaining 4 modules (Search, Import, History, Reporting)
2. Create production `main.py` with full functionality
3. Update build scripts for modular structure
4. Deprecate `JobDocs-qt.py`

## Checking Module Status

To see which modules are complete, check:
- [MODULAR_MIGRATION_STATUS.md](MODULAR_MIGRATION_STATUS.md) - Overall progress
- `modules/` directory - Each completed module has its own folder
