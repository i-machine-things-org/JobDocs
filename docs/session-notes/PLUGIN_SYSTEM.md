# JobDocs Plugin System

## Drop-In Module Architecture

JobDocs uses a **drop-in plugin system** where modules are automatically discovered and loaded at runtime.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    JobDocs Application                       │
│                         (main.py)                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
                   ┌────────────────┐
                   │  ModuleLoader  │  ← Scans modules/ folder
                   └────────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │   Auto-discovers modules  │
              │   No configuration needed │
              └─────────────┬─────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │                                     │
         ↓                                     ↓
    ┌─────────┐                          ┌─────────┐
    │ Quote   │                          │  Job    │
    │ Module  │                          │ Module  │
    └─────────┘                          └─────────┘
         ↓                                     ↓
    ┌─────────┐                          ┌─────────┐
    │  Tab    │                          │  Tab    │
    │ Widget  │                          │ Widget  │
    └─────────┘                          └─────────┘
```

## Creating a Plugin (Module)

### Step 1: Copy the Template
```bash
cp -r modules/_template modules/my_awesome_feature
```

### Step 2: Edit module.py
```python
from core.base_module import BaseModule
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class MyAwesomeFeature(BaseModule):
    def get_name(self):
        return "My Awesome Feature"

    def get_order(self):
        return 110  # Tabs are sorted by this number

    def initialize(self, app_context):
        super().initialize(app_context)
        # Access settings, history, etc.

    def get_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Hello from my plugin!"))
        return widget
```

### Step 3: That's It!
Restart JobDocs. Your module appears as a new tab!

## Plugin Discovery

```python
# In ModuleLoader
def discover_modules():
    for directory in modules/:
        if exists('module.py'):
            load_module(directory)
            # Finds class inheriting from BaseModule
            # Calls initialize(app_context)
            # Gets widget and adds to tabs
```

**No registration, no config files, no editing main.py!**

## What Your Plugin Gets

### Through app_context

```python
# In your module methods:
def my_method(self):
    # Settings
    value = self.app_context.get_setting('key', 'default')
    self.app_context.set_setting('key', 'new_value')
    self.app_context.save_settings()

    # Directories
    bp_dir, cf_dir = self.app_context.get_directories(is_itar=False)

    # History
    recent_jobs = self.app_context.history.get('recent_jobs', [])
    self.app_context.add_to_history('my_type', {'data': 'value'})
    self.app_context.save_history()

    # User interaction
    self.show_info("Title", "Message")
    self.show_error("Title", "Error message")
    self.log_message("Log entry")

    # Data access
    customers = self.app_context.get_customer_list()

    # Main window (use sparingly)
    main_window = self.app_context.main_window
```

### Through shared utilities

```python
from shared.utils import (
    parse_job_numbers,      # "1-5,7" -> ['1','2','3','4','5','7']
    is_blueprint_file,      # Check if file is blueprint
    create_file_link,       # Create hard/sym link or copy
    sanitize_filename,      # Remove invalid characters
    open_folder             # Open in OS file browser
)

from shared.widgets import (
    DropZone,               # Drag-and-drop file widget
    ScrollableMessageDialog # Large scrollable dialogs
)
```

## Plugin Lifecycle

```
1. Application Start
   └→ ModuleLoader.discover_modules()

2. For Each Module
   ├→ Import module.py
   ├→ Find BaseModule subclass
   ├→ Instantiate class
   ├→ Call initialize(app_context)
   ├→ Check is_experimental()
   ├→ Get order via get_order()
   └→ Store for later

3. Sort modules by order

4. Create UI
   └→ For each module:
       ├→ widget = module.get_widget()
       ├→ name = module.get_name()
       └→ tabs.addTab(widget, name)

5. Application Running
   └→ Modules work independently

6. Application Close
   └→ For each module:
       └→ module.cleanup()
```

## Plugin Distribution

### As Developer
```bash
# Package your module
tar -czf my_awesome_feature.tar.gz modules/my_awesome_feature/

# Share the archive
```

### As User
```bash
# Download module archive
# Extract to modules/ folder
tar -xzf my_awesome_feature.tar.gz -C /path/to/JobDocs/

# Restart JobDocs
# Module automatically appears!
```

## Experimental Modules

```python
class MyExperimentalModule(BaseModule):
    def is_experimental(self):
        return True  # Only loads if experimental features enabled
```

## Module Examples

### Simple Module (No UI File)
```python
class SimpleModule(BaseModule):
    def get_name(self):
        return "Simple"

    def get_order(self):
        return 100

    def get_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        button = QPushButton("Click Me!")
        button.clicked.connect(lambda: self.show_info("Hi!", "Button clicked"))
        layout.addWidget(button)
        return widget
```

### Complex Module (With UI File)
```python
class ComplexModule(BaseModule):
    def get_widget(self):
        widget = QWidget()
        ui_file = self._get_ui_path('my_module/ui/main.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.my_button = widget.my_button
        self.my_table = widget.my_table

        # Connect signals
        self.my_button.clicked.connect(self.on_button_click)

        return widget
```

## Tab Ordering

Modules are sorted by `get_order()`:

```
Order 10:  Quote
Order 20:  Job
Order 30:  Add to Job
Order 40:  Bulk
Order 50:  Search
Order 60:  Import
Order 70:  History
Order 80:  Reporting
Order 100: Your Custom Module 1
Order 110: Your Custom Module 2
Order 120: Third-Party Module 1
...
```

## Benefits

### 1. Easy Development
- Copy template
- Edit one file
- Done!

### 2. Easy Distribution
- Package module folder
- Users extract to modules/
- No installation required

### 3. Easy Customization
- Users enable/disable modules
- No code editing needed
- Mix and match features

### 4. Easy Maintenance
- Each module is independent
- Update one without affecting others
- Clear boundaries

### 5. Community Friendly
- Third parties can create modules
- Share modules easily
- No core code changes needed

## C++ Conversion

Modules can be converted to C++ one at a time:

```
Phase 1: All Python
   modules/quote/module.py       ← Python
   modules/job/module.py         ← Python

Phase 2: Mixed
   modules/quote/module.cpp      ← C++
   modules/job/module.py         ← Python

Phase 3: All C++ (optional)
   modules/quote/module.cpp      ← C++
   modules/job/module.cpp        ← C++
```

The BaseModule interface stays the same!

## Future Possibilities

1. **Module Marketplace**: Browse and install modules
2. **Module Manager**: GUI for enabling/disabling modules
3. **Module Dependencies**: Modules can depend on other modules
4. **Module Settings**: Each module can have its own settings page
5. **Hot Reload**: Reload modules without restarting
6. **Module Templates**: Multiple templates for different use cases

## Getting Started

1. Read [Template Module README](modules/_template/README.md)
2. Examine [Quote Module](modules/quote/module.py)
3. Copy template: `cp -r modules/_template modules/my_module`
4. Edit and test!

## Questions?

- Check `modules/_template/module.py` - extensive inline documentation
- Look at `modules/quote/` and `modules/job/` for examples
- Read `docs/modular-migration/QUICK_START_MODULAR.md`
