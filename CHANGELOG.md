# Changelog

All notable changes to JobDocs will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Modular Plugin Architecture**: Complete refactor to plugin-based system
  - Drop-in module support with automatic discovery
  - BaseModule interface for extensibility
  - AppContext for shared application state
  - ModuleLoader with auto-discovery
  - Template module for creating new plugins
  - 8 core modules (Quote, Job, Add to Job, Bulk, Search, Import, History, Reporting)
- **Quote Module**: Full quote creation and management
  - Quote creation with ITAR support
  - File linking and management
  - Copy From dialog for reusing quote/job data
  - Quote folders organized in customer/Quotes/ subdirectory
- **Copy From Dialog**: Unified search dialog for copying job/quote information
  - Search across all jobs and quotes
  - ITAR labeling in search results
  - Double-click to populate form
  - Filters by job folders (with "job documents") and quote folders
- **Customer List Auto-Population**: All customer dropdowns now populate automatically
  - Scans both ITAR and non-ITAR directories
  - Updates after creating new customers
  - Consistent across all modules
- **Getting Started Guide**: Comprehensive getting started documentation
- **Experimental**: Database integration framework for JobBOSS/ERP systems
  - Database connection settings in Advanced Settings
  - Placeholder code for database connectivity
  - Reporting tab with sample data and CSV export
  - Database integration module (`db_integration.py`)
  - Comprehensive documentation (DATABASE_INTEGRATION.md)
  - Implementation TODO tracker (TODO_DATABASE_INTEGRATION.md)
- Compact UI mode - reduced window size from 1000x750 to 900x700
- Tighter spacing and margins throughout UI
- Smaller component heights for better screen fit
- Windows installer build system
- Automatic icon generation
- Enhanced build scripts with progress indicators
- Version information in executable
- Settings dialog with UI style selector
- Sample file generator for testing
- **Legacy Search Mode**: Full recursive search through all customer directories
  - Handles inconsistent folder structures from legacy files
  - Optional blueprints directory search
  - Smart folder name parsing for job numbers and descriptions
- **Import Blueprints ITAR Support**: Import tab now has ITAR checkbox to import to ITAR blueprints directory
- **Duplicate Job Protection**: Bulk job creation now detects and skips duplicate jobs
  - Shows warning dialog listing duplicates before creation
  - Respects allow_duplicate_jobs setting

### Changed
- **Main Application**: Now uses modular system (main.py instead of JobDocs-qt.py)
- **BUILD.md**: Completely rewritten for modular architecture
  - Updated all build commands to use main.py
  - Added PyInstaller spec file example
  - Included module data packaging instructions
  - Removed references to deleted build scripts
- **UI Organization**: Removed inline search from Quote/Job tabs in favor of popup dialog
- **Module Loading**: All customer lists now populated centrally after module load
- **Architecture**: 2897-line monolith → ~300 lines per module
- Improved .gitignore to exclude build artifacts, test directories, and Claude workspace
- Reduced minimum window size for better compatibility with smaller screens
- Compacted DropZone widgets (80px → 60px minimum height)
- Shortened labels and placeholders throughout UI
- Job and Quote modules now use consistent populate_*_customer_list naming

### Fixed
- **Bulk Create**: Now properly creates jobs instead of just adding to history
  - Fixed by calling actual Job module's create_single_job method
  - Module references now stored in main window for inter-module communication
- **Customer Dropdowns**: All modules now show all customers from both ITAR and non-ITAR directories
  - Fixed populate_customer_lists() to actually call module methods
  - Removed redundant QTimer.singleShot calls
  - Customer lists refresh after module load
- **Copy From Dialog**: Fixed button box widget type error
- **Search Dialog**: Now properly filters by job folders and quote folders only
- Dead space in Add to Job tab - added proper vertical stretch
- Search functionality now properly differentiates between legacy and strict modes
- Legacy search options now show/hide based on selected mode

### Removed
- **JobDocs-qt.py**: Legacy monolithic version archived to `old/legacy/`
  - Was broken due to refactored imports
  - All functionality replaced by modular main.py
  - Kept in git history for reference
- Inline search UI from Quote and Job tabs (replaced with popup dialog)
- QSplitter widgets from Quote and Job tabs
- Redundant timer-based customer list population
- Temporary test files and cleanup summaries

## [1.0.0] - 2025-12-06

### Added
- Initial release
- Job creation with automatic folder structure
- Bulk job creation from CSV
- File linking (hard link, symbolic link, or copy)
- Blueprint file management
- Customer file organization
- ITAR directory support
- Search functionality across jobs
- Import tool for blueprints
- Job history tracking
- Cross-platform support (Windows, macOS, Linux)
- Qt-based modern UI
- Drag-and-drop file support
- Context menus for quick actions

### Features
- **Create Job Tab**: Single or batch job creation
- **Add to Job Tab**: Add files to existing jobs
- **Bulk Create Tab**: CSV import for multiple jobs
- **Search Tab**: Fast job and file search
- **Import Tab**: Direct blueprint imports
- **History Tab**: Track recent jobs
- **Settings**: Configurable directories and options

### Technical
- Built with PyQt6
- Cross-platform configuration storage
- Hard link support for space efficiency
- Duplicate job detection
- File extension-based routing
