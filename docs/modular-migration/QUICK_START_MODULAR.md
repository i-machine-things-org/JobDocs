# Quick Start: Modular JobDocs Development

## What Changed?

JobDocs is now modular! Instead of one giant file, each tab is now a separate module that can be developed, tested, and eventually converted to C++ independently.

## Project Structure

```
JobDocs/
├── core/                # Framework for loading and managing modules
├── shared/              # Common utilities and widgets
├── modules/             # Each tab is now a module
│   ├── quote/
│   ├── job/
│   ├── add_to_job/
│   ├── bulk/
│   ├── search/
│   ├── import_bp/
│   ├── history/
│   └── reporting/
└── main.py              # New modular entry point (to be created)
```

## Key Files

| File | Purpose |
|------|---------|
| `core/base_module.py` | Base class all modules inherit from |
| `core/app_context.py` | Shared application state and callbacks |
| `core/module_loader.py` | Discovers and loads modules automatically |
| `shared/utils.py` | Common functions used across modules |
| `shared/widgets.py` | Custom UI widgets (DropZone, etc.) |

## Creating a New Module

1. Create directory: `modules/my_module/`
2. Create `modules/my_module/module.py`:

```python
from core.base_module import BaseModule
from PyQt6.QtWidgets import QWidget

class MyModule(BaseModule):
    def get_name(self) -> str:
        return "My Tab Name"

    def get_order(self) -> int:
        return 100  # Lower = further left

    def initialize(self, app_context):
        super().initialize(app_context)
        # Setup code here

    def get_widget(self) -> QWidget:
        widget = QWidget()
        # Build your UI here
        return widget
```

3. Create `modules/my_module/ui/my_tab.ui` (optional, using Qt Designer)
4. Create `modules/my_module/README.md` documenting your module

That's it! The module loader will automatically discover and load it.

## Accessing Application State

Modules access shared application state through `self.app_context`:

```python
# Get settings
blueprint_dir = self.app_context.settings['blueprints_dir']

# Modify settings
self.app_context.settings['some_key'] = 'some_value'
self.app_context.save_settings()

# Access history
recent = self.app_context.history['recent_jobs']

# Show dialogs
self.show_error("Error", "Something went wrong")
self.show_info("Success", "Operation completed")

# Log messages
self.log_message("Processing started")

# Get customer list
customers = self.app_context.get_customer_list()
```

## Module Loading

Modules are loaded automatically based on:
- Presence in `modules/` directory
- Containing a `module.py` file
- Having a class that inherits from `BaseModule`
- Order specified by `get_order()`
- Experimental flag (only loaded if enabled in settings)

## Disabling a Module

To disable a module temporarily:
- Rename the `module.py` file (e.g., to `module.py.disabled`)
- Or move the module directory outside `modules/`

## Running Modules in Parallel with Original

During migration, you can run both:
- **Original**: `python JobDocs-qt.py` (monolithic version)
- **Modular**: `python main.py` (new version, when complete)

Both use the same settings and history files.

## Development Workflow

1. **Working on a module?**
   - Edit `modules/module_name/module.py`
   - Test by running the main application
   - Module is automatically reloaded on app restart

2. **Need shared functionality?**
   - Add to `shared/utils.py` (functions)
   - Or add to `AppContext` (needs app state)

3. **Creating new UI?**
   - Use Qt Designer to create `.ui` file
   - Save to `modules/module_name/ui/`
   - Load with `uic.loadUi()` in your module

## Building

Build scripts will be updated to include all modules:

```bash
# Linux
./build_linux.sh

# macOS
./build_macos.sh

# Windows
build_windows.bat
```

## Benefits

1. **Smaller files**: Each module is ~150-400 lines instead of one 2897-line file
2. **Parallel development**: Work on different modules simultaneously
3. **Easier testing**: Test modules independently
4. **Flexible builds**: Include only needed modules
5. **C++ migration**: Convert one module at a time

## Migration Status

See [MODULAR_REFACTOR_STATUS.md](MODULAR_REFACTOR_STATUS.md) for current progress.

## Full Documentation

- [MODULAR_ARCHITECTURE.md](MODULAR_ARCHITECTURE.md) - Architecture design
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Detailed migration instructions
- [MODULAR_REFACTOR_STATUS.md](MODULAR_REFACTOR_STATUS.md) - Current status

## Questions?

Check the existing modules in `modules/` directory for examples, or refer to the migration guide for detailed patterns.
