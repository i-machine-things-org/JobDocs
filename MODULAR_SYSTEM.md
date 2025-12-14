# JobDocs Modular System

## Quick Start

### Running the Application
```bash
python3 main.py              # Production modular version
python3 test_modular.py      # Test without full features
```

### Prerequisites
```bash
# Debian/Ubuntu
sudo apt install python3-pyqt6 python3-pyqt6.uic

# Or with pip
pip install PyQt6 PyQt6-tools
```

## Architecture

### Plugin System
All modules are automatically discovered from the `modules/` directory:
- **No main program edits needed**
- Just drop a module folder in `modules/`
- Follows the BaseModule interface

### Creating a New Module

1. Copy the template:
   ```bash
   cp -r modules/_template modules/my_feature
   ```

2. Edit `modules/my_feature/module.py`:
   ```python
   class MyFeatureModule(BaseModule):
       def get_name(self) -> str:
           return "My Feature"
       
       def get_order(self) -> int:
           return 100  # Tab position
       
       def get_widget(self) -> QWidget:
           # Build your UI
           pass
   ```

3. That's it! Auto-loaded on startup.

## Current Modules

1. **Quote** - Quote creation and management
2. **Job** - Job folder creation
3. **Add to Job** - Add files to existing jobs
4. **Bulk** - Bulk job creation from CSV
5. **Search** - Search across all jobs
6. **Import** - Import blueprints to customer folders
7. **History** - View recent job history
8. **Reporting** - Generate and export reports (experimental)

## Documentation

- [README.md](README.md) - Main project readme
- [TESTING.md](TESTING.md) - Testing instructions
- [MIGRATION_COMPLETE.md](MIGRATION_COMPLETE.md) - Migration details
- [docs/modular-migration/](docs/modular-migration/) - Detailed guides

## Files

### Essential
- `main.py` - Production application
- `test_modular.py` - Test script
- `core/` - Framework (BaseModule, AppContext, ModuleLoader)
- `shared/` - Utilities and widgets
- `modules/` - All plugin modules

### Legacy
- `JobDocs-qt.py` - Original monolithic version (still functional)

### Configuration
- Settings stored in `~/.config/JobDocs/settings.json`
- History stored in `~/.config/JobDocs/history.json`
