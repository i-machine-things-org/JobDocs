# JobDocs Modular Architecture Plan

## Overview
Refactoring JobDocs from a monolithic application to a modular, plugin-based architecture to support:
- Easier maintenance and testing
- Independent module development
- Future C++ conversion
- Dynamic module loading (n modules)

## Current Structure
- **Monolithic file**: JobDocs-qt.py (~2897 lines)
- **8 tabs** embedded in main class:
  1. Create Quote
  2. Create Job
  3. Add to Job
  4. Bulk Create
  5. Search
  6. Import Blueprints
  7. History
  8. Reports (Beta - experimental)

## New Directory Structure
```
JobDocs/
├── main.py                      # Main application entry point
├── core/                        # Core application framework
│   ├── __init__.py
│   ├── app.py                   # Main application class
│   ├── module_loader.py         # Dynamic module loader
│   ├── base_module.py           # Base module interface
│   └── config.py                # Configuration management
├── shared/                      # Shared utilities
│   ├── __init__.py
│   ├── utils.py                 # Common utility functions
│   ├── widgets.py               # Shared custom widgets (DropZone, etc.)
│   └── constants.py             # Shared constants
├── modules/                     # Individual tab modules
│   ├── __init__.py
│   ├── quote/                   # Quote creation module
│   │   ├── __init__.py
│   │   ├── module.py            # Module implementation
│   │   ├── ui/
│   │   │   └── quote_tab.ui
│   │   └── README.md
│   ├── job/                     # Job creation module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── job_tab.ui
│   │   └── README.md
│   ├── add_to_job/              # Add to job module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── add_to_job_tab.ui
│   │   └── README.md
│   ├── bulk/                    # Bulk operations module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── bulk_tab.ui
│   │   └── README.md
│   ├── search/                  # Search module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── search_tab.ui
│   │   └── README.md
│   ├── import_bp/               # Import blueprints module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── import_tab.ui
│   │   └── README.md
│   ├── history/                 # History module
│   │   ├── __init__.py
│   │   ├── module.py
│   │   ├── ui/
│   │   │   └── history_tab.ui
│   │   └── README.md
│   └── reporting/               # Reporting module
│       ├── __init__.py
│       ├── module.py
│       ├── ui/
│       │   └── reporting_tab.ui
│       └── README.md
├── ui/                          # Main UI files
│   └── mainwindow.ui            # Main window layout
├── build_linux.sh
├── build_macos.sh
├── build_windows.bat
├── requirements.txt
└── README.md
```

## Module Interface Contract

Each module must implement:

```python
class BaseModule(ABC):
    @abstractmethod
    def get_name(self) -> str:
        """Return the display name for the tab"""
        pass

    @abstractmethod
    def get_widget(self) -> QWidget:
        """Return the widget to display in the tab"""
        pass

    @abstractmethod
    def initialize(self, app_context):
        """Initialize module with application context"""
        pass

    def is_experimental(self) -> bool:
        """Return True if this is an experimental module"""
        return False

    def get_order(self) -> int:
        """Return display order (lower numbers appear first)"""
        return 100

    def cleanup(self):
        """Cleanup resources when module is unloaded"""
        pass
```

## Application Context

Shared context passed to all modules:

```python
class AppContext:
    settings: Dict[str, Any]          # Application settings
    history: Dict[str, Any]           # Application history
    config_dir: Path                  # Config directory path

    # Callbacks
    save_settings: Callable
    save_history: Callable
    log_message: Callable
    show_error: Callable
    show_info: Callable

    # Shared data access
    get_customer_list: Callable
    add_to_history: Callable
```

## Module Loading Process

1. Application starts
2. Core framework initializes
3. Module loader scans `modules/` directory
4. Each module is discovered and validated
5. Modules are initialized with AppContext
6. Tabs are added in order specified by `get_order()`
7. Experimental modules only loaded if enabled in settings

## Benefits

1. **Separation of Concerns**: Each module is self-contained
2. **Testing**: Modules can be tested independently
3. **Development**: Multiple developers can work on different modules
4. **C++ Conversion**: Convert modules one at a time
5. **Plugin System**: Easy to add/remove modules
6. **Build Flexibility**: Can build with subset of modules

## Migration Strategy

1. Create core framework and base module interface
2. Extract shared utilities
3. Convert one tab at a time to module format
4. Test each module independently
5. Update main application to use module loader
6. Update build scripts

## C++ Conversion Path

Once modular:
- Each Python module can be converted to C++ independently
- Use Qt C++ instead of PyQt
- Module interface remains the same
- Gradual migration: run Python and C++ modules together
- Eventually replace Python core with C++ core
