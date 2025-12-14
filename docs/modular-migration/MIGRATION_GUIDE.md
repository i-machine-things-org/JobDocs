# JobDocs Modular Migration Guide

This guide explains how to migrate the monolithic JobDocs-qt.py to the new modular architecture.

## Architecture Overview

The new modular architecture consists of:

1. **Core Framework** (`core/`)
   - `base_module.py` - Abstract base class for all modules
   - `app_context.py` - Shared application context
   - `module_loader.py` - Dynamic module discovery and loading

2. **Shared Utilities** (`shared/`)
   - `utils.py` - Common functions (get_config_dir, get_os_text, etc.)
   - `widgets.py` - Custom widgets (DropZone, ScrollableMessageDialog)

3. **Modules** (`modules/`)
   - Each tab becomes a self-contained module in its own directory
   - Each module has its own `module.py`, `ui/` directory, and `README.md`

## Module Structure

Each module directory should contain:

```
modules/module_name/
├── __init__.py           # Empty or imports
├── module.py             # Module implementation
├── ui/
│   └── tab_name.ui       # UI file
└── README.md             # Module documentation
```

## Creating a Module

### Step 1: Extract Tab Creation Method

Find the `create_XXX_tab()` method in [JobDocs-qt.py](JobDocs-qt.py). For example:
```python
def create_quote_tab(self) -> QWidget:
    widget = QWidget()
    ui_file = self.get_ui_path('tabs/quote_tab.ui')
    uic.loadUi(ui_file, widget)
    # ... setup code ...
    return widget
```

### Step 2: Extract Related Methods

Find all methods that are called from the tab. For quote tab:
- `add_quote_files()`
- `browse_quote_files()`
- `clear_quote_files()`
- `remove_quote_file()`
- `create_quote()`
- `create_single_quote()`
- `clear_quote_form()`
- `convert_current_quote_to_job()`
- `search_for_quote_copy()`
- `copy_quote_to_form()`
- `link_files_from_quote()`

### Step 3: Extract Instance Variables

Find all instance variables used by the tab:
- `self.quote_files`
- `self.quote_customer_combo`
- `self.quote_number_edit`
- etc.

### Step 4: Create Module Class

Create `modules/module_name/module.py`:

```python
"""
Module Name Tab Module
"""

import os
import sys
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QWidget, QMessageBox, QFileDialog
from PyQt6 import uic

from core.base_module import BaseModule
from shared.widgets import DropZone


class ModuleNameModule(BaseModule):
    """Module description"""

    def __init__(self):
        super().__init__()
        # Instance variables specific to this module
        self.module_files = []
        # Widget references
        self._widget = None

    def get_name(self) -> str:
        return "Tab Display Name"

    def get_order(self) -> int:
        return 10  # Adjust based on desired position

    def initialize(self, app_context):
        super().initialize(app_context)
        # Any initialization needed

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('module_name/ui/tab_name.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.some_control = widget.some_control

        # Setup custom widgets (like DropZone)
        # ...

        # Connect signals
        # widget.some_btn.clicked.connect(self.some_method)

        return widget

    def _get_ui_path(self, relative_path: str) -> Path:
        """Get path to UI file"""
        if getattr(sys, 'frozen', False):
            application_path = Path(sys._MEIPASS)
        else:
            application_path = Path(__file__).parent.parent.parent

        ui_file = application_path / 'modules' / relative_path
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")
        return ui_file

    # Migrated methods from main class
    def some_method(self):
        # Access settings via self.app_context.settings
        # Access history via self.app_context.history
        # Save settings via self.app_context.save_settings()
        # Show errors via self.show_error(title, message)
        pass
```

### Step 5: Update Method Calls

When migrating methods:

**Replace:**
- `self.settings` → `self.app_context.settings`
- `self.history` → `self.app_context.history`
- `self.save_settings()` → `self.app_context.save_settings()`
- `self.save_history()` → `self.app_context.save_history()`
- `QMessageBox.warning(self, ...)` → `self.show_error(...)`
- `QMessageBox.information(self, ...)` → `self.show_info(...)`

**For methods in other modules:**
- Store reference to main window in app_context if needed
- Or create shared services/utilities

### Step 6: Handle Shared Methods

Some methods are used by multiple tabs. These should be:

1. Moved to `shared/utils.py` if they're pure functions
2. Added to AppContext as callbacks if they need app state
3. Left in main application if they coordinate between modules

Examples of shared methods:
- `get_directories(is_itar)` - Could be in AppContext
- `is_blueprint_file(filename)` - Could be in shared/utils.py
- `create_link(source, dest)` - Could be in shared/utils.py
- `parse_job_numbers(text)` - Could be in shared/utils.py
- `populate_customer_lists()` - Needs to be in AppContext

## Module Loading in Main Application

The new main application will:

```python
from core import ModuleLoader, AppContext
from shared.utils import get_config_dir

class JobDocs(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load settings and history
        self.config_dir = get_config_dir()
        self.settings = self.load_settings()
        self.history = self.load_history()

        # Create application context
        self.app_context = AppContext(
            settings=self.settings,
            history=self.history,
            config_dir=self.config_dir,
            save_settings_callback=self.save_settings,
            save_history_callback=self.save_history,
            log_message_callback=self.log_message,
            show_error_callback=self.show_error_dialog,
            show_info_callback=self.show_info_dialog,
            get_customer_list_callback=self.get_customer_list,
            add_to_history_callback=self.add_to_history,
            main_window=self
        )

        # Load modules
        self.module_loader = ModuleLoader(Path(__file__).parent / 'modules')
        experimental_enabled = self.settings.get('experimental_features', False)
        self.modules = self.module_loader.load_all_modules(
            self.app_context,
            experimental_enabled
        )

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("JobDocs")

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Add module tabs
        for module in self.modules:
            widget = module.get_widget()
            self.tabs.addTab(widget, module.get_name())

        # Setup menu, etc.
        self.setup_menu()
```

## Migration Checklist

For each module:

- [ ] Create module directory structure
- [ ] Copy UI file to module's ui/ directory
- [ ] Create module.py with class inheriting from BaseModule
- [ ] Implement required methods (get_name, get_order, get_widget, initialize)
- [ ] Migrate create_XXX_tab() method
- [ ] Migrate all related methods
- [ ] Update method calls to use app_context
- [ ] Test module independently
- [ ] Create README.md documenting the module

## Modules to Migrate

1. **quote** (Create Quote) - Order: 10
2. **job** (Create Job) - Order: 20
3. **add_to_job** (Add to Job) - Order: 30
4. **bulk** (Bulk Create) - Order: 40
5. **search** (Search) - Order: 50
6. **import_bp** (Import Blueprints) - Order: 60
7. **history** (History) - Order: 70
8. **reporting** (Reports Beta) - Order: 80, Experimental: true

## Benefits

Once migrated:

1. **Easier testing** - Each module can be tested independently
2. **Parallel development** - Multiple developers can work on different modules
3. **Cleaner code** - Smaller, focused classes instead of one 2897-line file
4. **Flexible deployment** - Can build with subset of modules
5. **C++ migration path** - Convert one module at a time to C++

## Shared Methods to Extract

These methods are used by multiple modules and should be moved to shared utilities or AppContext:

### Move to shared/utils.py:
- `is_blueprint_file(filename)`
- `parse_job_numbers(text)`
- `sanitize_path_component(text)`

### Add to AppContext callbacks:
- `get_directories(is_itar)`
- `create_link(source, dest)`
- `populate_customer_lists()`
- `refresh_history()`
- `add_to_history(type, data)`
- `get_customer_list()`

## Next Steps

1. Finish extracting shared methods to utilities
2. Create one complete example module (quote)
3. Update main application to use module loader
4. Test with one module working
5. Migrate remaining modules one by one
6. Update build scripts
7. Remove old JobDocs-qt.py (or rename to JobDocs-qt.py.old)
