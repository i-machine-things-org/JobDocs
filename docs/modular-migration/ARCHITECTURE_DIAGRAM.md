# JobDocs Modular Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        JobDocs Application                   │
│                          (main.py)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ creates
                           ↓
          ┌────────────────────────────────┐
          │       AppContext               │
          │  - settings                    │
          │  - history                     │
          │  - config_dir                  │
          │  - callbacks                   │
          └────────────────┬───────────────┘
                           │
                           │ passed to
                           ↓
          ┌────────────────────────────────┐
          │     ModuleLoader               │
          │  - discovers modules           │
          │  - loads module classes        │
          │  - initializes modules         │
          │  - sorts by order              │
          └────────────────┬───────────────┘
                           │
                           │ loads
                           ↓
     ┌─────────────────────────────────────────────┐
     │              Modules (8 total)              │
     └─────────────────────────────────────────────┘
       │       │       │       │       │       │
       ↓       ↓       ↓       ↓       ↓       ↓
    ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
    │Quote│Job│  │Add │ │Bulk│ │Srch│ │...│
    │ 10  │ 20│  │ 30 │ │ 40 │ │ 50 │ │   │
    └────┘ └────┘ └────┘ └────┘ └────┘ └────┘
```

## Module Structure

```
┌──────────────────────────────────────────────────────┐
│                  BaseModule                          │
│  (Abstract Base Class)                               │
│                                                       │
│  + get_name() → str                                  │
│  + get_widget() → QWidget                            │
│  + initialize(app_context)                           │
│  + get_order() → int                                 │
│  + is_experimental() → bool                          │
│  + cleanup()                                         │
│                                                       │
│  # app_context → AppContext                          │
│  # log_message(msg)                                  │
│  # show_error(title, msg)                            │
│  # show_info(title, msg)                             │
└──────────────────┬───────────────────────────────────┘
                   │
                   │ inherits
                   ↓
     ┌─────────────────────────────────┐
     │      QuoteModule                │
     │                                 │
     │  + get_name() → "Create Quote"  │
     │  + get_order() → 10             │
     │  + get_widget() → QWidget       │
     │  + initialize(ctx)              │
     │                                 │
     │  - create_quote()               │
     │  - add_files()                  │
     │  - clear_form()                 │
     │  - ...                          │
     └─────────────────────────────────┘
```

## Data Flow

```
User Interaction
      │
      ↓
┌──────────────┐
│ Module       │
│ Widget       │
└──────┬───────┘
       │
       │ calls
       ↓
┌──────────────┐         ┌─────────────┐
│ Module       │────────→│ AppContext  │
│ Methods      │ uses    │             │
└──────────────┘         │ - settings  │
       │                 │ - history   │
       │ uses            │ - callbacks │
       ↓                 └─────────────┘
┌──────────────┐
│ Shared       │
│ Utilities    │
│              │
│ - utils.py   │
│ - widgets.py │
└──────────────┘
```

## Module Loading Sequence

```
1. Application Start
   └→ Load settings.json
   └→ Load history.json

2. Create AppContext
   └→ Pass settings, history
   └→ Register callbacks

3. ModuleLoader.discover_modules()
   └→ Scan modules/ directory
   └→ Find module.py files

4. For each module:
   └→ Load module class
   └→ Check experimental flag
   └→ Instantiate module
   └→ Call initialize(app_context)

5. Sort modules by get_order()

6. Add tabs to UI
   └→ For each module:
       └→ widget = module.get_widget()
       └→ tabs.addTab(widget, module.get_name())

7. Application Ready
```

## File Dependencies

```
main.py
  │
  ├─→ core/
  │    ├─→ base_module.py
  │    ├─→ app_context.py
  │    └─→ module_loader.py
  │
  ├─→ shared/
  │    ├─→ utils.py
  │    └─→ widgets.py
  │
  └─→ modules/
       ├─→ quote/module.py
       │    ├─→ core.base_module
       │    ├─→ shared.widgets
       │    └─→ shared.utils
       │
       ├─→ job/module.py
       │    └─→ (same dependencies)
       │
       └─→ ... (other modules)
```

## Settings & History Flow

```
┌──────────────────────────────────────────────┐
│  ~/.local/share/JobDocs/ (Linux)             │
│  ~/Library/Application Support/JobDocs (Mac) │
│  %LOCALAPPDATA%\JobDocs (Windows)            │
└──────────────────┬───────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ↓                       ↓
┌─────────────┐         ┌─────────────┐
│settings.json│         │history.json │
└──────┬──────┘         └──────┬──────┘
       │                       │
       │ loaded by             │
       ↓                       ↓
┌──────────────────────────────────────┐
│           AppContext                 │
│  - settings dict                     │
│  - history dict                      │
│  - save_settings()                   │
│  - save_history()                    │
└──────────────┬───────────────────────┘
               │
               │ accessed by
               ↓
       ┌───────────────┐
       │    Modules    │
       │               │
       │  app_context. │
       │    settings   │
       │    .save_     │
       │     settings()│
       └───────────────┘
```

## Module Communication

```
┌──────────────┐                    ┌──────────────┐
│ Quote Module │                    │  Job Module  │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       │ convert_quote_to_job()            │
       │                                   │
       ├→ Get main_window ref              │
       │  from app_context                 │
       │                                   │
       ├→ Switch to Job tab                │
       │  main_window.tabs.setCurrentIndex │
       │                                   │
       └→ Call job module method           │
          via main_window reference        │
                  │                        │
                  └───────────────────────→│
                      populate_form(data)
```

## Build Process (Future)

```
PyInstaller
    │
    ├─→ Collect main.py
    ├─→ Collect core/
    ├─→ Collect shared/
    ├─→ Collect modules/
    │    ├─→ quote/
    │    ├─→ job/
    │    └─→ ... (all or subset)
    │
    └─→ Bundle into executable
         │
         ├─→ jobdocs-linux
         ├─→ jobdocs-macos
         └─→ jobdocs-windows.exe
```

## C++ Conversion Path

```
Current State (Python)          Future State (C++ + Python)
┌──────────────────┐            ┌──────────────────┐
│   main.py        │            │   main.cpp       │
│   (Python)       │            │   (C++)          │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         ↓                               ↓
┌──────────────────┐            ┌──────────────────┐
│  ModuleLoader.py │            │ ModuleLoader.cpp │
│  (Python)        │            │  (C++)           │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         ↓                               ↓
┌──────────────────┐            ┌──────────────────┐
│  Modules         │            │  Modules (Mixed) │
│  (Python)        │            │  - quote.cpp ✓   │
│  - quote.py      │   →        │  - job.cpp ✓     │
│  - job.py        │            │  - search.py     │
│  - search.py     │            │  - import.py     │
│  - ...           │            │  - ...           │
└──────────────────┘            └──────────────────┘
```

## Legend

- `→` : Dependency/Import
- `↓` : Flow/Sequence
- `┌─┐` : Component/File
- `...` : Continuation/More items
