# Template Module - Creating Your Own JobDocs Modules

This template demonstrates how to create new JobDocs modules using the **drop-in plugin system**.

## Quick Start

1. **Copy this template:**
   ```bash
   cp -r modules/_template modules/my_module
   ```

2. **Edit `modules/my_module/module.py`:**
   - Rename the class from `TemplateModule` to `MyModule`
   - Update `get_name()` to return your tab name
   - Update `get_order()` to control tab position
   - Implement your functionality

3. **That's it!** The module will be automatically discovered and loaded.

## Module Auto-Discovery

JobDocs modules are automatically discovered at runtime:

- The `ModuleLoader` scans the `modules/` directory
- Any directory with a `module.py` file is loaded
- Classes inheriting from `BaseModule` are automatically registered
- No need to edit `main.py` or any configuration files!

## Module Structure

```
modules/my_module/
├── __init__.py          # Empty or simple imports
├── module.py            # Your module class (inherits BaseModule)
├── ui/                  # Optional: Qt Designer .ui files
│   └── my_tab.ui
└── README.md            # Module documentation
```

## Required Methods

Every module must implement:

```python
def get_name(self) -> str:
    """Tab display name"""
    return "My Module"

def get_order(self) -> int:
    """Tab position (lower = left)"""
    return 100

def get_widget(self) -> QWidget:
    """Return the tab widget"""
    # Build and return your UI

def initialize(self, app_context):
    """Initialize with app context"""
    super().initialize(app_context)
```

## Optional Methods

```python
def is_experimental(self) -> bool:
    """Return True if experimental"""
    return False

def cleanup(self):
    """Clean up resources"""
    pass
```

## Available Through app_context

Your module has access to:

### Settings & History
```python
self.app_context.settings              # Dict of all settings
self.app_context.history               # Dict of history data
self.app_context.save_settings()       # Save settings
self.app_context.save_history()        # Save history
self.app_context.get_setting(key, default)
self.app_context.set_setting(key, value)
```

### Directories
```python
self.app_context.get_directories(is_itar)  # Get bp/cf dirs
self.app_context.build_job_path(base, customer, job)
self.app_context.find_job_folders(customer_path)
```

### User Interaction
```python
self.show_error(title, message)
self.show_info(title, message)
self.log_message(message)
```

### Data Access
```python
self.app_context.get_customer_list()
self.app_context.add_to_history(type, data)
```

### Main Window (use sparingly)
```python
self.app_context.main_window  # Reference to main window
```

## Shared Utilities

Import from `shared.utils`:
```python
from shared.utils import (
    parse_job_numbers,          # Parse "1-5,7" -> ['1','2','3','4','5','7']
    is_blueprint_file,          # Check if file is blueprint
    create_file_link,           # Create hard/sym link or copy
    sanitize_filename,          # Remove invalid path characters
    open_folder,                # Open folder in OS browser
    get_os_type,                # Get 'windows'/'macos'/'linux'
    get_os_text                 # Get OS-specific text
)
```

Import from `shared.widgets`:
```python
from shared.widgets import (
    DropZone,                   # File drag-and-drop widget
    ScrollableMessageDialog     # Large scrollable dialogs
)
```

## Example Modules

Look at existing modules for examples:
- **Quote Module** (`modules/quote/`) - File management, search, conversion
- **Job Module** (`modules/job/`) - Duplicate checking, folder shortcuts
- **Template Module** (`modules/_template/`) - This template with examples!

## Tab Ordering

Suggested order values:
- 10: Quote
- 20: Job
- 30: Add to Job
- 40: Bulk
- 50: Search
- 60: Import
- 70: History
- 80: Reporting
- **100+: Your custom modules**

## Experimental Modules

To make a module experimental (only loads when enabled in settings):

```python
def is_experimental(self) -> bool:
    return True
```

## Distribution

When distributing your module:
1. Package the module directory
2. Users drop it in their `modules/` folder
3. It's automatically loaded on next startup!

## C++ Conversion

Each module can be independently converted to C++:
1. Keep the same BaseModule interface
2. Use Qt C++ instead of PyQt
3. Modules can be Python or C++ (mixed)
4. Gradual migration path

## Tips

1. **Keep it focused**: Each module should do one thing well
2. **Use shared utilities**: Don't duplicate common code
3. **Document**: Add a README.md to your module
4. **Test independently**: Modules should be testable in isolation
5. **Respect conventions**: Follow the patterns in existing modules

## Support

- See main documentation: `docs/modular-migration/`
- Check existing modules for patterns
- Template has extensive inline comments
