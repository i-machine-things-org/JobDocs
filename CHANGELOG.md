# Changelog

All notable changes to JobDocs will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Changed
- Improved .gitignore to exclude build artifacts
- Reduced minimum window size for better compatibility with smaller screens
- Compacted DropZone widgets (80px → 60px minimum height)
- Shortened labels and placeholders throughout UI

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
