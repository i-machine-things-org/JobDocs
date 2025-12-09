"""
JobDocs - A tool for managing blueprint links and customer files
Qt version for modern UI

Copyright (c) 2025 JobDocs Contributors
Licensed under the MIT License - see LICENSE file for details

This software is provided "as is" without warranty of any kind.
See LICENSE file for full terms and conditions.
"""

import os
import sys
import json
import shutil
import platform
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import re
import csv
from io import StringIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTabWidget, QLabel, QLineEdit, QComboBox, QPushButton,
    QCheckBox, QRadioButton, QButtonGroup, QGroupBox, QListWidget,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QTextEdit, QPlainTextEdit, QProgressBar, QSplitter, QFrame,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QMenu,
    QHeaderView, QAbstractItemView, QSizePolicy, QScrollArea, QStyleFactory
)
from PyQt6.QtCore import Qt, QTimer, QMimeData, pyqtSignal, QStandardPaths
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon


def get_config_dir() -> Path:
    """Get the appropriate config directory for the current OS"""
    if platform.system() == "Windows":
        # Windows: C:\Users\<Username>\AppData\Local\JobDocs
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        config_dir = base / 'JobDocs'
    elif platform.system() == "Darwin":
        # macOS: ~/Library/Application Support/JobDocs
        config_dir = Path.home() / 'Library' / 'Application Support' / 'JobDocs'
    else:
        # Linux/other: ~/.local/share/JobDocs
        xdg_data = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
        config_dir = Path(xdg_data) / 'JobDocs'
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_os_type() -> str:
    """Get simplified OS type"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    else:
        return "linux"


def get_os_text(key: str) -> str:
    """Get OS-specific text for various UI elements"""
    os_type = get_os_type()

    text_map = {
        # Terminology
        'folder_term': {
            'windows': 'folder',
            'macos': 'folder',
            'linux': 'directory'
        },
        'file_browser': {
            'windows': 'File Explorer',
            'macos': 'Finder',
            'linux': 'file manager'
        },

        # Link type info (FILES only - no admin needed!)
        'hard_link_note': {
            'windows': 'Hard Link (recommended - files must be on same volume)',
            'macos': 'Hard Link (recommended)',
            'linux': 'Hard Link (recommended)'
        },
        'symlink_note': {
            'windows': 'Symbolic Link (requires admin/Developer Mode)',
            'macos': 'Symbolic Link',
            'linux': 'Symbolic Link'
        },

        # Path separators
        'path_sep': {
            'windows': '\\',
            'macos': '/',
            'linux': '/'
        },
        'path_example': {
            'windows': '{customer}\\{job_folder}\\job documents',
            'macos': '{customer}/{job_folder}/job documents',
            'linux': '{customer}/{job_folder}/job documents'
        }
    }

    if key in text_map:
        return text_map[key].get(os_type, text_map[key]['linux'])
    return ""


class ScrollableMessageDialog(QDialog):
    """A custom dialog with scrollable content and defined size"""

    def __init__(self, parent, title: str, content: str, width: int = 600, height: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, height)

        # Create layout
        layout = QVBoxLayout(self)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Create content label
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setStyleSheet("padding: 10px;")

        # Set label as scroll area widget
        scroll_area.setWidget(content_label)

        # Add scroll area to layout
        layout.addWidget(scroll_area)

        # Add OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class DropZone(QFrame):
    """A widget that accepts file drops"""
    files_dropped = pyqtSignal(list)

    def __init__(self, label: str = "Drop files here", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(60)
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 6px;
            }
            DropZone:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.label = QLabel(f"{label} or click Browse")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_files)
        self.browse_btn.setMaximumWidth(90)
        self.browse_btn.setMaximumHeight(22)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                DropZone {
                    background-color: #e3f2fd;
                    border: 2px dashed #2196f3;
                    border-radius: 8px;
                }
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
        """)
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.files_dropped.emit(files)
    
    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", "All Files (*.*)"
        )
        if files:
            self.files_dropped.emit(files)


class SettingsDialog(QDialog):
    """Settings dialog"""
    
    def __init__(self, settings: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setup_ui()
    
    def setup_ui(self):
        # Main dialog layout
        main_layout = QVBoxLayout(self)

        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)  # Remove border

        # Container for scrollable content
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Directories group
        dir_group = QGroupBox("Directories")
        dir_layout = QGridLayout(dir_group)
        
        # Blueprints
        dir_layout.addWidget(QLabel("Blueprints Directory:"), 0, 0)
        self.blueprints_edit = QLineEdit(self.settings.get('blueprints_dir', ''))
        dir_layout.addWidget(self.blueprints_edit, 0, 1)
        bp_btn = QPushButton("Browse...")
        bp_btn.clicked.connect(lambda: self.browse_dir(self.blueprints_edit))
        dir_layout.addWidget(bp_btn, 0, 2)
        
        # Customer files
        dir_layout.addWidget(QLabel("Customer Files Directory:"), 1, 0)
        self.customer_files_edit = QLineEdit(self.settings.get('customer_files_dir', ''))
        dir_layout.addWidget(self.customer_files_edit, 1, 1)
        cf_btn = QPushButton("Browse...")
        cf_btn.clicked.connect(lambda: self.browse_dir(self.customer_files_edit))
        dir_layout.addWidget(cf_btn, 1, 2)

        scroll_layout.addWidget(dir_group)

        # ITAR directories group
        itar_group = QGroupBox("ITAR Directories (optional)")
        itar_layout = QGridLayout(itar_group)
        
        itar_layout.addWidget(QLabel("ITAR Blueprints:"), 0, 0)
        self.itar_blueprints_edit = QLineEdit(self.settings.get('itar_blueprints_dir', ''))
        itar_layout.addWidget(self.itar_blueprints_edit, 0, 1)
        itar_bp_btn = QPushButton("Browse...")
        itar_bp_btn.clicked.connect(lambda: self.browse_dir(self.itar_blueprints_edit))
        itar_layout.addWidget(itar_bp_btn, 0, 2)
        
        itar_layout.addWidget(QLabel("ITAR Customer Files:"), 1, 0)
        self.itar_customer_files_edit = QLineEdit(self.settings.get('itar_customer_files_dir', ''))
        itar_layout.addWidget(self.itar_customer_files_edit, 1, 1)
        itar_cf_btn = QPushButton("Browse...")
        itar_cf_btn.clicked.connect(lambda: self.browse_dir(self.itar_customer_files_edit))
        itar_layout.addWidget(itar_cf_btn, 1, 2)

        scroll_layout.addWidget(itar_group)

        # Link type group
        link_group = QGroupBox("Link Type")
        link_layout = QHBoxLayout(link_group)
        
        self.link_type_group = QButtonGroup(self)
        self.hard_radio = QRadioButton("Hard Link")
        self.symbolic_radio = QRadioButton("Symbolic Link")
        self.copy_radio = QRadioButton("Copy")
        
        self.link_type_group.addButton(self.hard_radio, 0)
        self.link_type_group.addButton(self.symbolic_radio, 1)
        self.link_type_group.addButton(self.copy_radio, 2)
        
        link_type = self.settings.get('link_type', 'hard')
        if link_type == 'hard':
            self.hard_radio.setChecked(True)
        elif link_type == 'symbolic':
            self.symbolic_radio.setChecked(True)
        else:
            self.copy_radio.setChecked(True)
        
        link_layout.addWidget(self.hard_radio)
        link_layout.addWidget(self.symbolic_radio)
        link_layout.addWidget(self.copy_radio)
        link_layout.addStretch()

        # Add OS-specific tooltips
        if get_os_type() == "windows":
            self.hard_radio.setToolTip("Creates a hard link to blueprint files. Saves disk space. Files must be on the same volume (e.g., same drive letter).")
            self.symbolic_radio.setToolTip("Creates a symbolic link. Requires administrator privileges or Windows Developer Mode.")
            self.copy_radio.setToolTip("Creates an independent copy of the file. Use if blueprints are on different drives.")
        else:
            self.hard_radio.setToolTip("Creates a hard link to blueprint files. Recommended - saves disk space.")
            self.symbolic_radio.setToolTip("Creates a symbolic link to blueprint files.")
            self.copy_radio.setToolTip("Creates an independent copy of the file.")

        scroll_layout.addWidget(link_group)

        # Blueprint extensions
        ext_group = QGroupBox("Blueprint File Types")
        ext_layout = QVBoxLayout(ext_group)
        
        ext_layout.addWidget(QLabel("Files with these extensions go to blueprints folder:"))
        self.extensions_edit = QLineEdit(
            ', '.join(self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf']))
        )
        ext_layout.addWidget(self.extensions_edit)
        ext_layout.addWidget(QLabel("(comma-separated, e.g., .pdf, .dwg, .dxf)"))

        scroll_layout.addWidget(ext_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.allow_duplicates_check = QCheckBox("Allow duplicate job numbers (not recommended)")
        self.allow_duplicates_check.setChecked(self.settings.get('allow_duplicate_jobs', False))
        options_layout.addWidget(self.allow_duplicates_check)

        # Default tab setting
        default_tab_layout = QHBoxLayout()
        default_tab_layout.addWidget(QLabel("Default opening tab:"))
        self.default_tab_combo = QComboBox()
        self.default_tab_combo.addItems([
            "Create Quote",
            "Create Job",
            "Add to Job",
            "Bulk Create",
            "Search",
            "Import Blueprints",
            "History"
        ])
        current_default = self.settings.get('default_tab', 0)
        if 0 <= current_default < self.default_tab_combo.count():
            self.default_tab_combo.setCurrentIndex(current_default)
        default_tab_layout.addWidget(self.default_tab_combo)
        default_tab_layout.addStretch()
        options_layout.addLayout(default_tab_layout)

        scroll_layout.addWidget(options_group)

        # Appearance
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QGridLayout(appearance_group)

        appearance_layout.addWidget(QLabel("UI Style:"), 0, 0)
        self.style_combo = QComboBox()
        available_styles = QStyleFactory.keys()
        self.style_combo.addItems(available_styles)
        current_style = self.settings.get('ui_style', 'Fusion')
        if current_style in available_styles:
            self.style_combo.setCurrentText(current_style)
        appearance_layout.addWidget(self.style_combo, 0, 1)
        appearance_layout.addWidget(QLabel("(restart required)"), 0, 2)

        scroll_layout.addWidget(appearance_group)

        # Advanced Settings (collapsible)
        self.advanced_group = QGroupBox("Advanced Settings")
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        advanced_layout = QVBoxLayout(self.advanced_group)

        # Create container widget for collapsible content
        self.advanced_content = QWidget()
        advanced_content_layout = QVBoxLayout(self.advanced_content)
        advanced_content_layout.setContentsMargins(0, 0, 0, 0)

        # Use OS-specific path separator for examples
        path_example = get_os_text('path_example')
        path_sep = get_os_text('path_sep')
        legacy_example = f"{{customer}}{path_sep}job documents{path_sep}{{job_folder}}"

        advanced_content_layout.addWidget(QLabel("Job Folder Structure:"))
        advanced_content_layout.addWidget(QLabel("Define the directory structure for job folders"))
        advanced_content_layout.addWidget(QLabel("Available placeholders: {customer}, {job_folder}"))

        structure_examples = QHBoxLayout()
        structure_examples.addWidget(QLabel(f"Default: {path_example}"))
        structure_examples.addStretch()
        advanced_content_layout.addLayout(structure_examples)

        structure_examples2 = QHBoxLayout()
        structure_examples2.addWidget(QLabel(f"Legacy: {legacy_example}"))
        structure_examples2.addStretch()
        advanced_content_layout.addLayout(structure_examples2)

        self.job_structure_edit = QLineEdit(
            self.settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')
        )
        advanced_content_layout.addWidget(self.job_structure_edit)

        # Spacer
        advanced_content_layout.addWidget(QLabel(""))

        # Legacy mode toggle
        self.legacy_mode_check = QCheckBox("Enable legacy mode (shows 'Search All Folders' option)")
        self.legacy_mode_check.setChecked(self.settings.get('legacy_mode', True))
        self.legacy_mode_check.toggled.connect(self.on_legacy_mode_toggled)
        advanced_content_layout.addWidget(self.legacy_mode_check)

        # Spacer
        advanced_content_layout.addWidget(QLabel(""))

        # Experimental features
        self.experimental_check = QCheckBox("Enable experimental features (Database integration, Reporting)")
        self.experimental_check.setChecked(self.settings.get('experimental_features', False))
        self.experimental_check.setToolTip("Enables experimental features like database integration and reporting. Requires restart.")
        advanced_content_layout.addWidget(self.experimental_check)

        advanced_layout.addWidget(self.advanced_content)

        # Hide content by default and connect toggle
        self.advanced_content.setVisible(False)
        self.advanced_group.toggled.connect(self.advanced_content.setVisible)

        scroll_layout.addWidget(self.advanced_group)

        # Experimental Settings (collapsible, shown only when experimental features enabled)
        self.experimental_group = QGroupBox("Experimental: Database Settings")
        self.experimental_group.setCheckable(True)
        self.experimental_group.setChecked(False)
        experimental_layout = QVBoxLayout(self.experimental_group)

        # Create container widget for collapsible content
        self.experimental_content = QWidget()
        experimental_content_layout = QVBoxLayout(self.experimental_content)
        experimental_content_layout.setContentsMargins(0, 0, 0, 0)

        experimental_content_layout.addWidget(QLabel("Configure database connection for JobBOSS/ERP integration:"))

        # Database type
        db_type_layout = QHBoxLayout()
        db_type_layout.addWidget(QLabel("Database Type:"))
        self.db_type_combo = QComboBox()
        self.db_type_combo.addItems(["mssql", "mysql", "postgresql", "sqlite"])
        self.db_type_combo.setCurrentText(self.settings.get('db_type', 'mssql'))
        db_type_layout.addWidget(self.db_type_combo)
        db_type_layout.addStretch()
        experimental_content_layout.addLayout(db_type_layout)

        # Database connection settings
        db_grid = QGridLayout()

        db_grid.addWidget(QLabel("Host:"), 0, 0)
        self.db_host_edit = QLineEdit(self.settings.get('db_host', 'localhost'))
        db_grid.addWidget(self.db_host_edit, 0, 1)

        db_grid.addWidget(QLabel("Port:"), 0, 2)
        self.db_port_edit = QLineEdit(str(self.settings.get('db_port', 1433)))
        self.db_port_edit.setMaximumWidth(80)
        db_grid.addWidget(self.db_port_edit, 0, 3)

        db_grid.addWidget(QLabel("Database:"), 1, 0)
        self.db_name_edit = QLineEdit(self.settings.get('db_name', ''))
        db_grid.addWidget(self.db_name_edit, 1, 1, 1, 3)

        db_grid.addWidget(QLabel("Username:"), 2, 0)
        self.db_username_edit = QLineEdit(self.settings.get('db_username', ''))
        db_grid.addWidget(self.db_username_edit, 2, 1, 1, 3)

        db_grid.addWidget(QLabel("Password:"), 3, 0)
        self.db_password_edit = QLineEdit(self.settings.get('db_password', ''))
        self.db_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        db_grid.addWidget(self.db_password_edit, 3, 1, 1, 3)

        experimental_content_layout.addLayout(db_grid)

        # Test connection button
        test_btn_layout = QHBoxLayout()
        self.test_db_btn = QPushButton("Test Connection")
        self.test_db_btn.clicked.connect(self.test_database_connection)
        test_btn_layout.addWidget(self.test_db_btn)
        test_btn_layout.addStretch()
        experimental_content_layout.addLayout(test_btn_layout)

        experimental_layout.addWidget(self.experimental_content)

        # Hide content by default and connect toggle
        self.experimental_content.setVisible(False)
        self.experimental_group.toggled.connect(self.experimental_content.setVisible)

        # Only show experimental group if experimental features are enabled
        self.experimental_group.setVisible(self.settings.get('experimental_features', False))

        scroll_layout.addWidget(self.experimental_group)

        # Set scroll widget and add to main layout
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Buttons (stay outside scroll area - always visible)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def browse_dir(self, line_edit: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            line_edit.setText(dir_path)

    def on_legacy_mode_toggled(self, checked: bool):
        """Update settings when legacy mode is toggled"""
        # Legacy mode only controls search UI visibility, not job folder structure
        # Job folder structure is either default or user-defined
        self.settings['legacy_mode'] = checked

    def test_database_connection(self):
        """Test database connection with current settings"""
        db_type = self.db_type_combo.currentText()
        host = self.db_host_edit.text()
        port = self.db_port_edit.text()
        database = self.db_name_edit.text()
        username = self.db_username_edit.text()
        password = self.db_password_edit.text()

        if not all([host, database, username]):
            QMessageBox.warning(self, "Missing Information", "Please fill in Host, Database, and Username fields.")
            return

        # Placeholder - actual implementation would use pyodbc, pymysql, etc.
        QMessageBox.information(
            self,
            "Test Connection",
            f"Database connection test (placeholder):\n\n"
            f"Type: {db_type}\n"
            f"Host: {host}:{port}\n"
            f"Database: {database}\n"
            f"Username: {username}\n\n"
            f"To implement:\n"
            f"- Install driver: pip install pyodbc (for MSSQL)\n"
            f"- Install driver: pip install pymysql (for MySQL)\n"
            f"- Install driver: pip install psycopg2 (for PostgreSQL)\n\n"
            f"See db_integration.py for implementation details."
        )

    def save(self):
        self.settings['blueprints_dir'] = self.blueprints_edit.text()
        self.settings['customer_files_dir'] = self.customer_files_edit.text()
        self.settings['itar_blueprints_dir'] = self.itar_blueprints_edit.text()
        self.settings['itar_customer_files_dir'] = self.itar_customer_files_edit.text()

        if self.hard_radio.isChecked():
            self.settings['link_type'] = 'hard'
        elif self.symbolic_radio.isChecked():
            self.settings['link_type'] = 'symbolic'
        else:
            self.settings['link_type'] = 'copy'

        extensions = [ext.strip().lower() for ext in self.extensions_edit.text().split(',') if ext.strip()]
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        self.settings['blueprint_extensions'] = extensions

        self.settings['job_folder_structure'] = self.job_structure_edit.text().strip()
        self.settings['legacy_mode'] = self.legacy_mode_check.isChecked()
        self.settings['allow_duplicate_jobs'] = self.allow_duplicates_check.isChecked()
        self.settings['ui_style'] = self.style_combo.currentText()
        self.settings['default_tab'] = self.default_tab_combo.currentIndex()

        # Experimental settings
        self.settings['experimental_features'] = self.experimental_check.isChecked()
        self.settings['db_type'] = self.db_type_combo.currentText()
        self.settings['db_host'] = self.db_host_edit.text()
        self.settings['db_port'] = int(self.db_port_edit.text()) if self.db_port_edit.text().isdigit() else 1433
        self.settings['db_name'] = self.db_name_edit.text()
        self.settings['db_username'] = self.db_username_edit.text()
        self.settings['db_password'] = self.db_password_edit.text()

        self.accept()


class JobDocs(QMainWindow):
    """Main application window"""
    
    DEFAULT_SETTINGS = {
        'blueprints_dir': '',
        'customer_files_dir': '',
        'itar_blueprints_dir': '',
        'itar_customer_files_dir': '',
        'link_type': 'hard',
        'blueprint_extensions': ['.pdf', '.dwg', '.dxf'],
        'allow_duplicate_jobs': False,
        'ui_style': 'Fusion',
        'job_folder_structure': '{customer}/{job_folder}/job documents',  # New default structure
        'legacy_mode': True,  # Default to TRUE to show both search options
        'default_tab': 0,  # Default opening tab (0=Create Quote, 1=Create Job, etc.)
        'experimental_features': False,  # Enable experimental features like database integration
        'db_type': 'mssql',  # Database type: mssql, mysql, postgresql
        'db_host': 'localhost',
        'db_port': 1433,
        'db_name': '',
        'db_username': '',
        'db_password': ''  # Note: Store securely in production
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JobDocs")
        self.setMinimumSize(900, 700)
        
        # Config
        self.config_dir = get_config_dir()
        self.settings_file = self.config_dir / 'settings.json'
        self.history_file = self.config_dir / 'history.json'
        
        self.settings = self.load_settings()
        self.history = self.load_history()
        
        # Data storage
        self.job_files: List[str] = []
        self.add_files: List[str] = []
        self.import_files: List[str] = []
        self.search_results: List[Dict[str, Any]] = []
        self.quotes: List[Dict[str, Any]] = []  # Store quotes
        
        self.setup_ui()
        self.setup_menu()
        self.populate_customer_lists()

        # Initialize UI visibility based on legacy mode setting
        self.update_legacy_mode_ui()
    
    def load_settings(self) -> Dict[str, Any]:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    merged = self.DEFAULT_SETTINGS.copy()
                    merged.update(settings)
                    return merged
            except (json.JSONDecodeError, IOError) as e:
                self.log_message(f"Warning: Could not load settings: {e}")
        return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def load_history(self) -> Dict[str, Any]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.log_message(f"Warning: Could not load history: {e}")
        return {'customers': {}, 'recent_jobs': []}
    
    def save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def setup_ui(self):
        # Create scroll area for main content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll_area)

        # Container widget for scrollable content
        central = QWidget()
        scroll_area.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self.tabs.addTab(self.create_quote_tab(), "Create Quote")
        self.tabs.addTab(self.create_job_tab(), "Create Job")
        self.tabs.addTab(self.create_add_to_job_tab(), "Add to Job")
        self.tabs.addTab(self.create_bulk_tab(), "Bulk Create")
        self.tabs.addTab(self.create_search_tab(), "Search")
        self.tabs.addTab(self.create_import_tab(), "Import Blueprints")
        self.tabs.addTab(self.create_history_tab(), "History")

        # Add experimental reporting tab if enabled
        if self.settings.get('experimental_features', False):
            self.tabs.addTab(self.create_reporting_tab(), "Reports (Beta)")

        # Set default tab
        default_tab = self.settings.get('default_tab', 0)
        if 0 <= default_tab < self.tabs.count():
            self.tabs.setCurrentIndex(default_tab)
    
    def setup_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()

        getting_started_action = QAction("Getting started", self)
        getting_started_action.triggered.connect(self.show_getting_started)
        help_menu.addAction(getting_started_action)

    # ==================== Create Quote Tab ====================

    def create_quote_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Quote info group
        info_group = QGroupBox("Quote Information")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(5, 5, 5, 5)

        info_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.quote_customer_combo = QComboBox()
        self.quote_customer_combo.setEditable(True)
        self.quote_customer_combo.setPlaceholderText("Customer name")
        self.quote_customer_combo.setMinimumWidth(200)
        info_layout.addWidget(self.quote_customer_combo, 0, 1)

        info_layout.addWidget(QLabel("Quote #:"), 1, 0)
        self.quote_number_edit = QLineEdit()
        self.quote_number_edit.setPlaceholderText("Quote number")
        info_layout.addWidget(self.quote_number_edit, 1, 1)

        info_layout.addWidget(QLabel("Description:"), 2, 0)
        self.quote_description_edit = QLineEdit()
        self.quote_description_edit.setPlaceholderText("Quote description")
        info_layout.addWidget(self.quote_description_edit, 2, 1)

        info_layout.addWidget(QLabel("Drawings:"), 3, 0)
        self.quote_drawings_edit = QLineEdit()
        self.quote_drawings_edit.setPlaceholderText("Drawing numbers (comma-separated)")
        info_layout.addWidget(self.quote_drawings_edit, 3, 1)

        info_layout.addWidget(QLabel("Notes:"), 4, 0)
        self.quote_notes_edit = QTextEdit()
        self.quote_notes_edit.setPlaceholderText("Quote notes, pricing, delivery dates, etc.")
        self.quote_notes_edit.setMaximumHeight(80)
        info_layout.addWidget(self.quote_notes_edit, 4, 1)

        layout.addWidget(info_group)

        # Buttons
        button_layout = QHBoxLayout()

        save_quote_btn = QPushButton("Save Quote")
        save_quote_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        save_quote_btn.clicked.connect(self.save_quote)
        button_layout.addWidget(save_quote_btn)

        clear_quote_btn = QPushButton("Clear")
        clear_quote_btn.clicked.connect(self.clear_quote_form)
        button_layout.addWidget(clear_quote_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Saved quotes list
        quotes_group = QGroupBox("Saved Quotes")
        quotes_layout = QVBoxLayout(quotes_group)
        quotes_layout.setSpacing(3)
        quotes_layout.setContentsMargins(5, 5, 5, 5)

        self.quotes_table = QTableWidget()
        self.quotes_table.setColumnCount(5)
        self.quotes_table.setHorizontalHeaderLabels(["Customer", "Quote #", "Description", "Drawings", "Notes"])
        self.quotes_table.horizontalHeader().setStretchLastSection(True)
        self.quotes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.quotes_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.quotes_table.customContextMenuRequested.connect(self.show_quote_context_menu)
        quotes_layout.addWidget(self.quotes_table)

        layout.addWidget(quotes_group, 1)

        self.quote_status_label = QLabel("")
        layout.addWidget(self.quote_status_label)

        return widget

    def save_quote(self):
        customer = self.quote_customer_combo.currentText().strip()
        quote_number = self.quote_number_edit.text().strip()
        description = self.quote_description_edit.text().strip()
        drawings_text = self.quote_drawings_edit.text().strip()
        notes = self.quote_notes_edit.toPlainText().strip()

        if not customer or not quote_number:
            QMessageBox.warning(self, "Error", "Customer and Quote # are required")
            return

        drawings = [d.strip() for d in drawings_text.split(',') if d.strip()]

        quote = {
            'customer': customer,
            'quote_number': quote_number,
            'description': description,
            'drawings': drawings,
            'notes': notes,
            'date': datetime.now().isoformat()
        }

        self.quotes.append(quote)
        self.refresh_quotes_table()
        self.clear_quote_form()
        self.quote_status_label.setText(f"Quote {quote_number} saved successfully")
        QTimer.singleShot(3000, lambda: self.quote_status_label.setText(""))

    def clear_quote_form(self):
        self.quote_customer_combo.setCurrentText("")
        self.quote_number_edit.clear()
        self.quote_description_edit.clear()
        self.quote_drawings_edit.clear()
        self.quote_notes_edit.clear()

    def refresh_quotes_table(self):
        self.quotes_table.setRowCount(0)
        for quote in reversed(self.quotes):  # Show newest first
            row = self.quotes_table.rowCount()
            self.quotes_table.insertRow(row)
            self.quotes_table.setItem(row, 0, QTableWidgetItem(quote['customer']))
            self.quotes_table.setItem(row, 1, QTableWidgetItem(quote['quote_number']))
            self.quotes_table.setItem(row, 2, QTableWidgetItem(quote['description']))
            self.quotes_table.setItem(row, 3, QTableWidgetItem(', '.join(quote['drawings'])))
            self.quotes_table.setItem(row, 4, QTableWidgetItem(quote['notes'][:50] + '...' if len(quote['notes']) > 50 else quote['notes']))

    def show_quote_context_menu(self, pos):
        row = self.quotes_table.currentRow()
        if row < 0:
            return

        menu = QMenu(self)

        convert_action = menu.addAction("Convert to Job")
        delete_action = menu.addAction("Delete Quote")

        action = menu.exec(self.quotes_table.viewport().mapToGlobal(pos))

        if action == convert_action:
            self.convert_quote_to_job(row)
        elif action == delete_action:
            self.delete_quote(row)

    def convert_quote_to_job(self, row):
        # Get the quote (reversed list, so adjust index)
        quote = self.quotes[len(self.quotes) - 1 - row]

        # Switch to Create Job tab and populate fields
        self.tabs.setCurrentIndex(1)  # Create Job is now tab 1
        self.customer_combo.setCurrentText(quote['customer'])
        self.job_number_edit.setText(quote['quote_number'])
        self.description_edit.setText(quote['description'])
        self.drawings_edit.setText(', '.join(quote['drawings']))

        QMessageBox.information(self, "Quote Loaded", f"Quote {quote['quote_number']} loaded into Create Job tab")

    def delete_quote(self, row):
        if QMessageBox.question(self, "Delete Quote", "Delete this quote?") == QMessageBox.StandardButton.Yes:
            # Remove from list (reversed display)
            del self.quotes[len(self.quotes) - 1 - row]
            self.refresh_quotes_table()

    # ==================== Create Job Tab ====================

    def create_job_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Job info group
        info_group = QGroupBox("Job Information")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(5, 5, 5, 5)
        
        # Customer
        info_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setEditable(True)
        self.customer_combo.setMinimumWidth(250)
        info_layout.addWidget(self.customer_combo, 0, 1)
        
        # Job number
        info_layout.addWidget(QLabel("Job #:"), 1, 0)
        self.job_number_edit = QLineEdit()
        self.job_number_edit.setPlaceholderText("e.g., 12345 or 12345-12350")
        info_layout.addWidget(self.job_number_edit, 1, 1)
        self.job_status_label = QLabel("")
        info_layout.addWidget(self.job_status_label, 1, 2)

        # Description
        info_layout.addWidget(QLabel("Description:"), 2, 0)
        self.description_edit = QLineEdit()
        info_layout.addWidget(self.description_edit, 2, 1)

        # Drawings
        info_layout.addWidget(QLabel("Drawings:"), 3, 0)
        self.drawings_edit = QLineEdit()
        self.drawings_edit.setPlaceholderText("comma-separated")
        info_layout.addWidget(self.drawings_edit, 3, 1)
        
        # ITAR
        self.itar_check = QCheckBox("ITAR Job (uses separate directories)")
        info_layout.addWidget(self.itar_check, 4, 1)
        
        layout.addWidget(info_group)
        
        # Files group
        files_group = QGroupBox("Job Files (Optional)")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(3)
        files_layout.setContentsMargins(5, 5, 5, 5)

        files_layout.addWidget(QLabel("Blueprints → blueprints folder, others → job folder"))

        self.job_drop_zone = DropZone("Drop files")
        self.job_drop_zone.files_dropped.connect(self.handle_job_files)
        self.job_drop_zone.setMinimumHeight(60)
        files_layout.addWidget(self.job_drop_zone)

        self.job_files_list = QListWidget()
        self.job_files_list.setMaximumHeight(70)
        files_layout.addWidget(self.job_files_list)
        
        files_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_job_file)
        files_btn_layout.addWidget(remove_btn)
        files_btn_layout.addStretch()
        files_layout.addLayout(files_btn_layout)
        
        layout.addWidget(files_group)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        create_btn = QPushButton("Create Job && Link Files")
        #create_btn.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        create_btn.clicked.connect(self.create_job)
        btn_layout.addWidget(create_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_job_form)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        
        open_bp_btn = QPushButton("Open Blueprints")
        open_bp_btn.clicked.connect(self.open_blueprints_folder)
        btn_layout.addWidget(open_bp_btn)
        
        open_cf_btn = QPushButton("Open Customer Files")
        open_cf_btn.clicked.connect(self.open_customer_files_folder)
        btn_layout.addWidget(open_cf_btn)
        
        layout.addLayout(btn_layout)
        
        # Log
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(5, 5, 5, 5)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
        
        return widget
    
    def create_add_to_job_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        layout.addWidget(QLabel("Add documents to existing job"))

        # Splitter for left/right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left - Job browser
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 3, 0)
        left_layout.setSpacing(3)

        browser_group = QGroupBox("Select Job")
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.setSpacing(3)
        browser_layout.setContentsMargins(5, 5, 5, 5)
        
        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Customer:"))
        self.add_customer_combo = QComboBox()
        self.add_customer_combo.setMinimumWidth(150)
        self.add_customer_combo.currentTextChanged.connect(self.refresh_job_tree)
        filter_layout.addWidget(self.add_customer_combo)

        # ITAR filter radio buttons
        self.add_filter_group = QButtonGroup()
        self.add_all_radio = QRadioButton("All Jobs")
        self.add_standard_radio = QRadioButton("Standard Only")
        self.add_itar_radio = QRadioButton("ITAR Only")
        self.add_all_radio.setChecked(True)

        self.add_filter_group.addButton(self.add_all_radio)
        self.add_filter_group.addButton(self.add_standard_radio)
        self.add_filter_group.addButton(self.add_itar_radio)

        self.add_all_radio.toggled.connect(self.refresh_job_tree)
        self.add_standard_radio.toggled.connect(self.refresh_job_tree)
        self.add_itar_radio.toggled.connect(self.refresh_job_tree)

        filter_layout.addWidget(self.add_all_radio)
        filter_layout.addWidget(self.add_standard_radio)
        filter_layout.addWidget(self.add_itar_radio)
        filter_layout.addStretch()
        browser_layout.addLayout(filter_layout)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.add_search_edit = QLineEdit()
        self.add_search_edit.setPlaceholderText("job number or customer...")
        self.add_search_edit.returnPressed.connect(self.search_jobs)
        search_layout.addWidget(self.add_search_edit)
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search_jobs)
        search_layout.addWidget(search_btn)
        
        clear_search_btn = QPushButton("Clear")
        clear_search_btn.clicked.connect(self.clear_job_search)
        search_layout.addWidget(clear_search_btn)
        browser_layout.addLayout(search_layout)
        
        # Tree
        self.job_tree = QTreeWidget()
        self.job_tree.setHeaderLabels(["Customer / Job"])
        self.job_tree.setColumnCount(1)
        self.job_tree.itemSelectionChanged.connect(self.on_job_tree_select)
        browser_layout.addWidget(self.job_tree)
        
        self.selected_job_label = QLabel("No job selected")
        self.selected_job_label.setStyleSheet("color: gray;")
        browser_layout.addWidget(self.selected_job_label)

        left_layout.addWidget(browser_group, 1)
        splitter.addWidget(left_widget)
        
        # Right - Add files
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(3, 0, 0, 0)
        right_layout.setSpacing(3)

        add_group = QGroupBox("Add Files")
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(3)
        add_layout.setContentsMargins(5, 5, 5, 5)
        
        # Destination options
        dest_group = QGroupBox("Destination")
        dest_layout = QVBoxLayout(dest_group)
        dest_layout.setSpacing(2)
        dest_layout.setContentsMargins(5, 5, 5, 5)

        self.dest_button_group = QButtonGroup(self)
        self.dest_both_radio = QRadioButton("Blueprints + Job")
        self.dest_both_radio.setChecked(True)
        self.dest_blueprints_radio = QRadioButton("Blueprints only")
        self.dest_job_radio = QRadioButton("Job only")

        self.dest_button_group.addButton(self.dest_both_radio)
        self.dest_button_group.addButton(self.dest_blueprints_radio)
        self.dest_button_group.addButton(self.dest_job_radio)

        dest_layout.addWidget(self.dest_both_radio)
        dest_layout.addWidget(self.dest_blueprints_radio)
        dest_layout.addWidget(self.dest_job_radio)
        add_layout.addWidget(dest_group)
        
        # Drop zone
        self.add_drop_zone = DropZone("Drop files")
        self.add_drop_zone.files_dropped.connect(self.handle_add_files)
        self.add_drop_zone.setMinimumHeight(60)
        add_layout.addWidget(self.add_drop_zone)

        # File list
        self.add_files_list = QListWidget()
        self.add_files_list.setMaximumHeight(90)
        add_layout.addWidget(self.add_files_list)
        
        # Buttons
        add_btn_layout = QHBoxLayout()
        remove_add_btn = QPushButton("Remove Selected")
        remove_add_btn.clicked.connect(self.remove_add_file)
        add_btn_layout.addWidget(remove_add_btn)
        
        clear_add_btn = QPushButton("Clear All")
        clear_add_btn.clicked.connect(self.clear_add_files)
        add_btn_layout.addWidget(clear_add_btn)
        add_btn_layout.addStretch()
        add_layout.addLayout(add_btn_layout)
        
        # Add button
        add_files_btn = QPushButton("Add Files to Job")
        add_files_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        add_files_btn.clicked.connect(self.add_files_to_job)
        add_layout.addWidget(add_files_btn)
        
        self.add_status_label = QLabel("")
        add_layout.addWidget(self.add_status_label)

        right_layout.addWidget(add_group, 1)
        splitter.addWidget(right_widget)

        splitter.setSizes([450, 450])
        layout.addWidget(splitter, 1)
        
        # Initialize
        QTimer.singleShot(100, self.populate_add_customer_list)
        
        return widget
    
    def create_bulk_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Instructions
        inst_group = QGroupBox("Bulk Job Creation")
        inst_layout = QVBoxLayout(inst_group)
        inst_layout.setSpacing(2)
        inst_layout.setContentsMargins(5, 5, 5, 5)
        inst_layout.addWidget(QLabel("Format: customer, job#, description, drawings..."))
        inst_layout.addWidget(QLabel("Example: Acme Corp, 12345, Widget Assembly, DWG-001"))

        self.bulk_itar_check = QCheckBox("All jobs are ITAR")
        inst_layout.addWidget(self.bulk_itar_check)
        layout.addWidget(inst_group)
        
        # Text input
        text_group = QGroupBox("Job Data (CSV Format)")
        text_layout = QVBoxLayout(text_group)
        text_layout.setSpacing(3)
        text_layout.setContentsMargins(5, 5, 5, 5)

        toolbar = QHBoxLayout()
        import_btn = QPushButton("Import CSV")
        import_btn.clicked.connect(self.import_bulk_csv)
        toolbar.addWidget(import_btn)

        clear_bulk_btn = QPushButton("Clear")
        clear_bulk_btn.clicked.connect(lambda: self.bulk_text.clear())
        toolbar.addWidget(clear_bulk_btn)

        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self.validate_bulk_data)
        toolbar.addWidget(validate_btn)
        toolbar.addStretch()
        text_layout.addLayout(toolbar)

        self.bulk_text = QPlainTextEdit()
        self.bulk_text.setPlaceholderText(
            "# CSV format (# = comments)\n"
            "Acme Corp, 12345, Widget Assembly, DWG-001\n"
            "Beta Inc, 54321, Custom Part"
        )
        self.bulk_text.setMaximumHeight(150)
        text_layout.addWidget(self.bulk_text)
        layout.addWidget(text_group)

        # Preview table
        preview_group = QGroupBox("Preview / Validation")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(5, 5, 5, 5)

        self.bulk_table = QTableWidget()
        self.bulk_table.setColumnCount(5)
        self.bulk_table.setHorizontalHeaderLabels(["Status", "Customer", "Job #", "Description", "Drawings"])
        self.bulk_table.horizontalHeader().setStretchLastSection(True)
        self.bulk_table.setMaximumHeight(150)
        preview_layout.addWidget(self.bulk_table)
        layout.addWidget(preview_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        create_bulk_btn = QPushButton("Create All Jobs")
        create_bulk_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        create_bulk_btn.clicked.connect(self.create_bulk_jobs)
        btn_layout.addWidget(create_bulk_btn)
        
        self.bulk_status_label = QLabel("")
        btn_layout.addWidget(self.bulk_status_label)
        btn_layout.addStretch()
        
        self.bulk_progress = QProgressBar()
        self.bulk_progress.setMaximumWidth(200)
        self.bulk_progress.hide()
        btn_layout.addWidget(self.bulk_progress)
        layout.addLayout(btn_layout)
        
        return widget
    
    def create_search_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Search controls
        search_group = QGroupBox("Search Criteria")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(3)
        search_layout.setContentsMargins(5, 5, 5, 5)
        
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Enter search term...")
        self.search_edit.returnPressed.connect(self.perform_search)
        top_row.addWidget(self.search_edit)
        
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        top_row.addWidget(search_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_search)
        top_row.addWidget(clear_btn)
        search_layout.addLayout(top_row)
        
        # Checkboxes
        check_row = QHBoxLayout()
        check_row.addWidget(QLabel("Search in:"))
        self.search_customer_check = QCheckBox("Customer")
        self.search_customer_check.setChecked(True)
        check_row.addWidget(self.search_customer_check)
        
        self.search_job_check = QCheckBox("Job #")
        self.search_job_check.setChecked(True)
        check_row.addWidget(self.search_job_check)
        
        self.search_desc_check = QCheckBox("Description")
        self.search_desc_check.setChecked(True)
        check_row.addWidget(self.search_desc_check)
        
        self.search_drawing_check = QCheckBox("Drawings")
        self.search_drawing_check.setChecked(True)
        check_row.addWidget(self.search_drawing_check)
        check_row.addStretch()
        search_layout.addLayout(check_row)
        
        # Mode (wrapped in container widget for show/hide control)
        self.mode_row_widget = QWidget()
        mode_row = QHBoxLayout(self.mode_row_widget)
        mode_row.setContentsMargins(0, 0, 0, 0)

        mode_row.addWidget(QLabel("Mode:"))

        self.search_mode_group = QButtonGroup(self)
        self.search_all_radio = QRadioButton("Search All Folders")
        self.search_strict_radio = QRadioButton("Strict Format (faster)")

        # Set default based on legacy_mode setting
        is_legacy = self.settings.get('legacy_mode', True)
        if is_legacy:
            self.search_all_radio.setChecked(True)
        else:
            self.search_strict_radio.setChecked(True)

        self.search_mode_group.addButton(self.search_all_radio)
        self.search_mode_group.addButton(self.search_strict_radio)

        mode_row.addWidget(self.search_all_radio)
        mode_row.addWidget(self.search_strict_radio)
        mode_row.addStretch()

        search_layout.addWidget(self.mode_row_widget)

        # Legacy search options (shown only in "Search All Folders" mode)
        self.legacy_options_widget = QWidget()
        legacy_options_row = QHBoxLayout(self.legacy_options_widget)
        legacy_options_row.setContentsMargins(0, 0, 0, 0)

        legacy_options_row.addWidget(QLabel("Also search:"))
        self.search_blueprints_check = QCheckBox("Blueprints directories")
        self.search_blueprints_check.setChecked(False)
        legacy_options_row.addWidget(self.search_blueprints_check)
        legacy_options_row.addStretch()

        search_layout.addWidget(self.legacy_options_widget)

        # Connect mode change to update checkbox states
        self.search_all_radio.toggled.connect(self.update_search_field_checkboxes)
        self.search_strict_radio.toggled.connect(self.update_search_field_checkboxes)

        # Initialize checkbox states and visibility based on legacy mode
        self.update_search_field_checkboxes()

        layout.addWidget(search_group)

        # Note: update_legacy_mode_ui() will be called after all tabs are created
        
        # Results
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(5, 5, 5, 5)

        self.search_table = QTableWidget()
        self.search_table.setColumnCount(5)
        self.search_table.setHorizontalHeaderLabels(["Date", "Customer", "Job #", "Description", "Drawings"])
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.search_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_table.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_table.doubleClicked.connect(self.open_selected_search_job)
        results_layout.addWidget(self.search_table)
        
        self.search_status_label = QLabel("")
        results_layout.addWidget(self.search_status_label)
        
        self.search_progress = QProgressBar()
        self.search_progress.hide()
        results_layout.addWidget(self.search_progress)
        
        layout.addWidget(results_group)
        
        return widget
    
    def create_import_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        layout.addWidget(QLabel("Import files to blueprints folder"))

        # Customer selection
        select_group = QGroupBox("Customer")
        select_layout = QVBoxLayout(select_group)
        select_layout.setContentsMargins(5, 5, 5, 5)

        customer_row = QHBoxLayout()
        customer_row.addWidget(QLabel("Customer:"))
        self.import_customer_combo = QComboBox()
        self.import_customer_combo.setEditable(True)
        self.import_customer_combo.setMinimumWidth(200)
        customer_row.addWidget(self.import_customer_combo)
        customer_row.addStretch()
        select_layout.addLayout(customer_row)

        self.import_itar_check = QCheckBox("ITAR (uses ITAR blueprints directory)")
        select_layout.addWidget(self.import_itar_check)

        layout.addWidget(select_group)

        # Drop zone
        files_group = QGroupBox("Files to Import")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(3)
        files_layout.setContentsMargins(5, 5, 5, 5)

        self.import_drop_zone = DropZone("Drop files")
        self.import_drop_zone.files_dropped.connect(self.handle_import_files)
        self.import_drop_zone.setMinimumHeight(60)
        files_layout.addWidget(self.import_drop_zone)

        self.import_files_list = QListWidget()
        self.import_files_list.setMaximumHeight(120)
        files_layout.addWidget(self.import_files_list)
        
        btn_layout = QHBoxLayout()
        import_btn = QPushButton("Check && Import")
        import_btn.clicked.connect(self.check_and_import)
        btn_layout.addWidget(import_btn)
        
        clear_btn = QPushButton("Clear List")
        clear_btn.clicked.connect(self.clear_import_list)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        files_layout.addLayout(btn_layout)
        
        layout.addWidget(files_group)
        
        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(5, 5, 5, 5)
        self.import_log = QPlainTextEdit()
        self.import_log.setReadOnly(True)
        self.import_log.setMaximumHeight(120)
        results_layout.addWidget(self.import_log)
        layout.addWidget(results_group)
        
        return widget
    
    def create_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # History table
        history_group = QGroupBox("Recent Jobs")
        history_layout = QVBoxLayout(history_group)
        history_layout.setContentsMargins(5, 5, 5, 5)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Customer", "Job #", "Description", "Drawings"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        history_layout.addWidget(self.history_table)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_history)
        btn_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear History")
        clear_btn.clicked.connect(self.clear_history)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        history_layout.addLayout(btn_layout)
        
        layout.addWidget(history_group)
        
        self.refresh_history()

        return widget

    def create_reporting_tab(self) -> QWidget:
        """Create experimental reporting tab for database integration"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Info banner
        info_group = QGroupBox("Experimental Feature")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(5, 5, 5, 5)
        info_label = QLabel(
            "This is an experimental feature for database integration with JobBOSS and other ERP systems.\n"
            "Configure database connection in Settings > Advanced Settings > Experimental."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 5px;")
        info_layout.addWidget(info_label)
        layout.addWidget(info_group)

        # Database connection status
        status_group = QGroupBox("Database Connection")
        status_layout = QVBoxLayout(status_group)
        status_layout.setContentsMargins(5, 5, 5, 5)

        self.db_status_label = QLabel("Status: Not connected")
        self.db_status_label.setStyleSheet("color: #999;")
        status_layout.addWidget(self.db_status_label)

        db_btn_layout = QHBoxLayout()
        self.connect_db_btn = QPushButton("Connect to Database")
        self.connect_db_btn.clicked.connect(self.connect_to_database)
        db_btn_layout.addWidget(self.connect_db_btn)

        self.disconnect_db_btn = QPushButton("Disconnect")
        self.disconnect_db_btn.clicked.connect(self.disconnect_from_database)
        self.disconnect_db_btn.setEnabled(False)
        db_btn_layout.addWidget(self.disconnect_db_btn)

        db_btn_layout.addStretch()
        status_layout.addLayout(db_btn_layout)
        layout.addWidget(status_group)

        # Report selection
        report_group = QGroupBox("Generate Reports")
        report_layout = QVBoxLayout(report_group)
        report_layout.setContentsMargins(5, 5, 5, 5)
        report_layout.setSpacing(5)

        # Report type selection
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Report Type:"))
        self.report_type_combo = QComboBox()
        self.report_type_combo.addItems([
            "Job Statistics",
            "Jobs by Customer",
            "Jobs by Date Range",
            "Recent Jobs",
            "Top Customers"
        ])
        type_layout.addWidget(self.report_type_combo)
        type_layout.addStretch()
        report_layout.addLayout(type_layout)

        # Filter options
        filter_layout = QGridLayout()

        filter_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.report_customer_combo = QComboBox()
        self.report_customer_combo.setEditable(True)
        self.report_customer_combo.addItem("All Customers")
        filter_layout.addWidget(self.report_customer_combo, 0, 1)

        filter_layout.addWidget(QLabel("Start Date:"), 1, 0)
        self.report_start_date = QLineEdit()
        self.report_start_date.setPlaceholderText("YYYY-MM-DD")
        filter_layout.addWidget(self.report_start_date, 1, 1)

        filter_layout.addWidget(QLabel("End Date:"), 1, 2)
        self.report_end_date = QLineEdit()
        self.report_end_date.setPlaceholderText("YYYY-MM-DD")
        filter_layout.addWidget(self.report_end_date, 1, 3)

        report_layout.addLayout(filter_layout)

        # Generate button
        gen_btn_layout = QHBoxLayout()
        self.generate_report_btn = QPushButton("Generate Report")
        self.generate_report_btn.clicked.connect(self.generate_report)
        self.generate_report_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        gen_btn_layout.addWidget(self.generate_report_btn)

        self.export_report_btn = QPushButton("Export to CSV")
        self.export_report_btn.clicked.connect(self.export_report)
        gen_btn_layout.addWidget(self.export_report_btn)

        gen_btn_layout.addStretch()
        report_layout.addLayout(gen_btn_layout)

        layout.addWidget(report_group)

        # Results
        results_group = QGroupBox("Report Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(5, 5, 5, 5)

        self.report_table = QTableWidget()
        self.report_table.setColumnCount(5)
        self.report_table.setHorizontalHeaderLabels(["Date", "Customer", "Job #", "Description", "Status"])
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        results_layout.addWidget(self.report_table)

        self.report_status_label = QLabel("No data loaded. Connect to database and generate a report.")
        self.report_status_label.setStyleSheet("color: #666;")
        results_layout.addWidget(self.report_status_label)

        layout.addWidget(results_group)

        return widget

    # ==================== Helper Methods ====================

    def build_job_path(self, base_dir: str, customer: str, job_folder_name: str) -> Path:
        """Build job path based on the configured structure template"""
        structure = self.settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')

        # Replace placeholders
        path_str = structure.replace('{customer}', customer).replace('{job_folder}', job_folder_name)

        return Path(base_dir) / path_str

    def find_job_folders(self, customer_path: str) -> List[Tuple[str, str]]:
        """Find all job folders in a customer directory, returns list of (job_name, job_docs_path) tuples"""
        structure = self.settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')

        # Determine where job_folder appears in the structure relative to customer
        # Remove {customer}/ prefix and see what remains
        after_customer = structure.split('{customer}/', 1)[-1] if '{customer}/' in structure else structure

        jobs = []

        # Check if job_folder is at the root level after customer
        if after_customer.startswith('{job_folder}/'):
            # New structure: customer/job_folder/...
            suffix = after_customer.replace('{job_folder}/', '', 1)
            try:
                for item in os.listdir(customer_path):
                    item_path = os.path.join(customer_path, item)
                    if os.path.isdir(item_path):
                        expected_docs_path = os.path.join(item_path, suffix)
                        if os.path.exists(expected_docs_path):
                            jobs.append((item, expected_docs_path))
            except OSError:
                pass
        else:
            # Legacy or custom structure: might have intermediate folders
            # For legacy: customer/job documents/job_folder
            parts = after_customer.split('{job_folder}')
            if len(parts) == 2:
                prefix = parts[0].strip('/')
                suffix = parts[1].strip('/')

                prefix_path = os.path.join(customer_path, prefix) if prefix else customer_path

                if os.path.exists(prefix_path):
                    try:
                        for item in os.listdir(prefix_path):
                            item_path = os.path.join(prefix_path, item)
                            if os.path.isdir(item_path):
                                if suffix:
                                    expected_docs_path = os.path.join(item_path, suffix)
                                    if os.path.exists(expected_docs_path):
                                        jobs.append((item, expected_docs_path))
                                else:
                                    # No suffix, the item_path itself is the job docs
                                    jobs.append((item, item_path))
                    except OSError:
                        pass

        return jobs

    def _get_customers_from_dirs(self, dir_keys: List[str]) -> set:
        """Extract customer names from specified directory keys"""
        customers = set()
        for dir_key in dir_keys:
            dir_path = self.settings.get(dir_key, '')
            if dir_path and os.path.exists(dir_path):
                try:
                    for d in os.listdir(dir_path):
                        if os.path.isdir(os.path.join(dir_path, d)):
                            customers.add(d)
                except OSError:
                    pass
        return customers

    def _get_customer_files_dirs(self) -> List[Tuple[str, str]]:
        """Returns list of (prefix, path) tuples for customer file directories"""
        dirs = []
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs.append(('', cf_dir))
        itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            dirs.append(('ITAR', itar_cf_dir))
        return dirs

    def populate_customer_lists(self):
        customers = self._get_customers_from_dirs([
            'blueprints_dir', 'customer_files_dir',
            'itar_blueprints_dir', 'itar_customer_files_dir'
        ])

        # Add customers from history
        for customer in self.history.get('customers', {}).keys():
            customers.add(customer)

        sorted_customers = sorted(customers)

        self.quote_customer_combo.clear()
        self.quote_customer_combo.addItems(sorted_customers)

        self.customer_combo.clear()
        self.customer_combo.addItems(sorted_customers)

        self.import_customer_combo.clear()
        self.import_customer_combo.addItems(sorted_customers)
    
    def populate_add_customer_list(self):
        customers = self._get_customers_from_dirs([
            'customer_files_dir', 'itar_customer_files_dir'
        ])

        self.add_customer_combo.clear()
        self.add_customer_combo.addItem("(All Customers)")
        self.add_customer_combo.addItems(sorted(customers))

        self.refresh_job_tree()
    
    def log_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def get_directories(self, is_itar: bool) -> Tuple[Optional[str], Optional[str]]:
        if is_itar:
            return (
                self.settings.get('itar_blueprints_dir'),
                self.settings.get('itar_customer_files_dir')
            )
        return (
            self.settings.get('blueprints_dir'),
            self.settings.get('customer_files_dir')
        )
    
    def is_blueprint_file(self, filename: str) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
    
    def create_link(self, source: Path, dest: Path) -> bool:
        link_type = self.settings.get('link_type', 'hard')
        try:
            if link_type == 'hard':
                os.link(source, dest)
            elif link_type == 'symbolic':
                os.symlink(source, dest)
            else:
                shutil.copy2(source, dest)
            return True
        except OSError as e:
            self.log_message(f"Link error: {e}")
            return False
    
    def open_folder(self, path: str):
        import subprocess
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except FileNotFoundError:
            QMessageBox.warning(self, "Error", f"Folder not found: {path}")
        except PermissionError:
            QMessageBox.warning(self, "Error", f"Permission denied: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")
    
    def parse_job_numbers(self, job_input: str) -> List[str]:
        job_numbers = []
        for part in job_input.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    range_parts = part.split('-')
                    if len(range_parts) == 2:
                        start = int(range_parts[0].strip())
                        end = int(range_parts[1].strip())
                        if start <= end:
                            job_numbers.extend(str(n) for n in range(start, end + 1))
                            continue
                except ValueError:
                    pass
            job_numbers.append(part)
        return job_numbers
    
    def check_duplicate_job(self, customer: str, job_number: str) -> Tuple[bool, Optional[str]]:
        # Check for globally unique job numbers (across ALL customers)
        job_number_lower = job_number.lower()

        # Check history first (faster than file system)
        recent_jobs = self.history.get('recent_jobs', [])
        for job in recent_jobs:
            if job.get('job_number', '').lower() == job_number_lower:
                existing_customer = job.get('customer', 'Unknown')
                return True, f"{existing_customer}: {job.get('path', 'Unknown')}"

        # Check file system across all customers
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            cf_dir = self.settings.get(dir_key, '')
            if not cf_dir or not os.path.exists(cf_dir):
                continue

            try:
                # Check all customer directories
                for customer_dir in os.listdir(cf_dir):
                    customer_path = os.path.join(cf_dir, customer_dir)
                    if not os.path.isdir(customer_path):
                        continue

                    # Use helper method to find job folders
                    jobs = self.find_job_folders(customer_path)
                    for job_name, job_docs_path in jobs:
                        # Extract job number from directory name
                        parts = job_name.split('_', 1)
                        if parts and parts[0].lower() == job_number_lower:
                            return True, f"{customer_dir}: {job_name}"
            except OSError:
                pass

        return False, None
    
    # ==================== Create Job Tab ====================
    
    def handle_job_files(self, files: List[str]):
        for f in files:
            if f not in self.job_files:
                self.job_files.append(f)
                self.job_files_list.addItem(os.path.basename(f))
    
    def remove_job_file(self):
        row = self.job_files_list.currentRow()
        if row >= 0:
            self.job_files_list.takeItem(row)
            del self.job_files[row]
    
    def clear_job_form(self):
        self.customer_combo.setCurrentText("")
        self.job_number_edit.clear()
        self.description_edit.clear()
        self.drawings_edit.clear()
        self.itar_check.setChecked(False)
        self.job_files.clear()
        self.job_files_list.clear()
    
    def create_job(self):
        customer = self.customer_combo.currentText().strip()
        job_input = self.job_number_edit.text().strip()
        description = self.description_edit.text().strip()
        drawings_str = self.drawings_edit.text().strip()
        is_itar = self.itar_check.isChecked()
        
        if not all([customer, job_input, description]):
            QMessageBox.warning(self, "Error", "Please fill in customer, job number, and description")
            return
        
        bp_dir, cf_dir = self.get_directories(is_itar)
        
        if is_itar and (not bp_dir or not cf_dir):
            QMessageBox.warning(self, "Error", "ITAR directories not configured in Settings")
            return
        
        if not bp_dir or not cf_dir:
            QMessageBox.warning(self, "Error", "Please configure directories in Settings")
            return
        
        drawings = [d.strip() for d in drawings_str.split(',') if d.strip()] if drawings_str else []
        job_numbers = self.parse_job_numbers(job_input)

        if not job_numbers:
            QMessageBox.warning(self, "Error", "Invalid job number format")
            return

        # Check for duplicate job numbers
        duplicates = []
        for job_num in job_numbers:
            is_dup, dup_path = self.check_duplicate_job(customer, job_num)
            if is_dup:
                duplicates.append(f"Job #{job_num} already exists at: {dup_path}")

        if duplicates:
            dup_msg = "\n".join(duplicates)
            QMessageBox.warning(self, "Duplicate Job Numbers", f"The following job numbers already exist:\n\n{dup_msg}")
            return

        self.log_message(f"Creating job(s): {', '.join(job_numbers)}")

        # Track if this is a new customer
        existing_customers = self._get_customers_from_dirs([
            'blueprints_dir', 'customer_files_dir',
            'itar_blueprints_dir', 'itar_customer_files_dir'
        ])
        is_new_customer = customer not in existing_customers

        created = 0
        for job_num in job_numbers:
            if self.create_single_job(customer, job_num, description, drawings, is_itar, self.job_files):
                created += 1

        QMessageBox.information(self, "Success", f"Created {created}/{len(job_numbers)} job(s)")

        self.job_files.clear()
        self.job_files_list.clear()
        self.refresh_history()

        # Only refresh customer lists if a new customer was created
        if is_new_customer:
            self.populate_customer_lists()
    
    def create_single_job(self, customer: str, job_number: str, description: str,
                         drawings: List[str], is_itar: bool, files: List[str]) -> bool:
        try:
            bp_dir, cf_dir = self.get_directories(is_itar)
            
            if drawings:
                job_dir_name = f"{job_number}_{description}_{'-'.join(drawings)}"
            else:
                job_dir_name = f"{job_number}_{description}"
            
            job_dir_name = re.sub(r'[<>:"/\\|?*]', '_', job_dir_name)

            # Use the configured job folder structure
            job_path = self.build_job_path(cf_dir, customer, job_dir_name)
            job_path.mkdir(parents=True, exist_ok=True)
            
            customer_bp = Path(bp_dir) / customer
            customer_bp.mkdir(parents=True, exist_ok=True)
            
            for file_path in files:
                file_name = os.path.basename(file_path)

                if self.is_blueprint_file(file_name):
                    bp_dest = customer_bp / file_name
                    try:
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass  # File already exists

                    job_dest = job_path / file_name
                    if not job_dest.exists():
                        self.create_link(bp_dest, job_dest)
                else:
                    job_dest = job_path / file_name
                    try:
                        shutil.copy2(file_path, job_dest)
                    except FileExistsError:
                        pass  # File already exists
            
            # Link existing drawings
            if drawings:
                # Build blueprint file index once instead of globbing repeatedly
                exts = self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
                available_bps = {}
                try:
                    for bp_file in customer_bp.iterdir():
                        if bp_file.is_file() and bp_file.suffix.lower() in exts:
                            available_bps[bp_file.name.lower()] = bp_file
                except OSError:
                    pass

                # Now lookup drawings efficiently
                for drawing in drawings:
                    drawing_lower = drawing.lower()
                    for ext in exts:
                        # Check for exact matches and partial matches
                        for bp_name, bp_file in available_bps.items():
                            if drawing_lower in bp_name and bp_name.endswith(ext.lower()):
                                dest = job_path / bp_file.name
                                if not dest.exists():
                                    self.create_link(bp_file, dest)
            
            self.add_to_history(customer, job_number, description, drawings, str(job_path))
            self.log_message(f"Created: {job_path}")
            return True
            
        except Exception as e:
            self.log_message(f"Error: {e}")
            return False
    
    def add_to_history(self, customer: str, job_number: str, description: str,
                      drawings: List[str], path: str):
        if 'customers' not in self.history:
            self.history['customers'] = {}
        if customer not in self.history['customers']:
            self.history['customers'][customer] = {'jobs': []}
        
        if 'recent_jobs' not in self.history:
            self.history['recent_jobs'] = []
        
        self.history['recent_jobs'].insert(0, {
            'date': datetime.now().isoformat(),
            'customer': customer,
            'job_number': job_number,
            'description': description,
            'drawings': drawings,
            'path': path
        })
        
        self.history['recent_jobs'] = self.history['recent_jobs'][:100]
        self.save_history()
    
    def open_blueprints_folder(self):
        bp_dir = self.settings.get('blueprints_dir', '')
        if bp_dir and os.path.exists(bp_dir):
            self.open_folder(bp_dir)
        else:
            QMessageBox.warning(self, "Warning", "Blueprints directory not configured")
    
    def open_customer_files_folder(self):
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            self.open_folder(cf_dir)
        else:
            QMessageBox.warning(self, "Warning", "Customer files directory not configured")
    
    # ==================== Add to Job Tab ====================
    
    def refresh_job_tree(self):
        self.job_tree.clear()

        selected_customer = self.add_customer_combo.currentText()
        show_all_customers = selected_customer == "(All Customers)" or not selected_customer
        
        # Get directories based on filter selection
        dirs_to_search = []

        if self.add_all_radio.isChecked():
            # Show both standard and ITAR
            dirs_to_search = self._get_customer_files_dirs()
        elif self.add_standard_radio.isChecked():
            # Show only standard (non-ITAR) jobs
            cf_dir = self.settings.get('customer_files_dir', '')
            if cf_dir and os.path.exists(cf_dir):
                dirs_to_search.append(('', cf_dir))
        else:  # ITAR only
            # Show only ITAR jobs
            itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
            if itar_cf_dir and os.path.exists(itar_cf_dir):
                dirs_to_search.append(('ITAR', itar_cf_dir))
        
        for prefix, cf_dir in dirs_to_search:
            try:
                if show_all_customers:
                    customers = [d for d in os.listdir(cf_dir) if os.path.isdir(os.path.join(cf_dir, d))]
                else:
                    customers = [selected_customer] if os.path.isdir(os.path.join(cf_dir, selected_customer)) else []
                
                for customer in sorted(customers):
                    customer_path = os.path.join(cf_dir, customer)
                    if not os.path.exists(customer_path):
                        continue

                    display_name = f"[{prefix}] {customer}" if prefix else customer
                    customer_item = QTreeWidgetItem([display_name])
                    customer_item.setData(0, Qt.ItemDataRole.UserRole, customer_path)

                    # Use helper method to find job folders
                    jobs = self.find_job_folders(customer_path)

                    for job_name, job_docs_path in sorted(jobs):
                        job_item = QTreeWidgetItem([job_name])
                        job_item.setData(0, Qt.ItemDataRole.UserRole, job_docs_path)
                        customer_item.addChild(job_item)

                    if customer_item.childCount() > 0:
                        self.job_tree.addTopLevelItem(customer_item)
                        
            except OSError:
                pass
    
    def search_jobs(self):
        search_term = self.add_search_edit.text().strip().lower()

        if not search_term:
            self.refresh_job_tree()
            return

        self.job_tree.clear()

        # Use helper method for directory building
        dirs_to_search = self._get_customer_files_dirs()
        
        results = 0
        
        for prefix, cf_dir in dirs_to_search:
            try:
                customers = [d for d in os.listdir(cf_dir) if os.path.isdir(os.path.join(cf_dir, d))]
                
                for customer in sorted(customers):
                    customer_path = os.path.join(cf_dir, customer)
                    if not os.path.exists(customer_path):
                        continue

                    matching_jobs = []

                    # Use helper method to find job folders
                    jobs = self.find_job_folders(customer_path)
                    for job_name, job_docs_path in jobs:
                        if search_term in job_name.lower() or search_term in customer.lower():
                            matching_jobs.append((job_name, job_docs_path))

                    if matching_jobs:
                        display_name = f"[{prefix}] {customer}" if prefix else customer
                        customer_item = QTreeWidgetItem([display_name])
                        customer_item.setData(0, Qt.ItemDataRole.UserRole, customer_path)

                        for job, job_path in sorted(matching_jobs):
                            job_item = QTreeWidgetItem([job])
                            job_item.setData(0, Qt.ItemDataRole.UserRole, job_path)
                            customer_item.addChild(job_item)
                            results += 1

                        self.job_tree.addTopLevelItem(customer_item)
                        customer_item.setExpanded(True)
                        
            except OSError:
                pass
        
        self.selected_job_label.setText(f"Found {results} job(s)" if results else "No matches")
    
    def clear_job_search(self):
        self.add_search_edit.clear()
        self.refresh_job_tree()
    
    def on_job_tree_select(self):
        items = self.job_tree.selectedItems()
        if not items:
            self.selected_job_label.setText("No job selected")
            return
        
        item = items[0]
        if item.parent():
            self.selected_job_label.setText(f"Selected: {item.text(0)}")
            self.selected_job_label.setStyleSheet("color: green;")
        else:
            self.selected_job_label.setText("Select a job, not customer")
            self.selected_job_label.setStyleSheet("color: orange;")
    
    def handle_add_files(self, files: List[str]):
        for f in files:
            if f not in self.add_files:
                self.add_files.append(f)
                self.add_files_list.addItem(os.path.basename(f))
    
    def remove_add_file(self):
        row = self.add_files_list.currentRow()
        if row >= 0:
            self.add_files_list.takeItem(row)
            del self.add_files[row]
    
    def clear_add_files(self):
        self.add_files.clear()
        self.add_files_list.clear()
    
    def add_files_to_job(self):
        items = self.job_tree.selectedItems()
        if not items:
            QMessageBox.warning(self, "No Selection", "Please select a job folder")
            return
        
        item = items[0]
        if not item.parent():
            QMessageBox.warning(self, "Invalid Selection", "Please select a job, not a customer")
            return
        
        if not self.add_files:
            QMessageBox.warning(self, "No Files", "Please add files")
            return
        
        job_path = item.data(0, Qt.ItemDataRole.UserRole)
        job_name = item.text(0)
        
        customer_text = item.parent().text(0)
        if customer_text.startswith('[ITAR] '):
            customer = customer_text[7:]
            is_itar = True
        else:
            customer = customer_text
            itar_cf = self.settings.get('itar_customer_files_dir', '')
            is_itar = itar_cf and job_path.startswith(itar_cf)
        
        bp_dir, _ = self.get_directories(is_itar)
        if not bp_dir:
            QMessageBox.warning(self, "Error", "Blueprints directory not configured")
            return
        
        customer_bp = Path(bp_dir) / customer
        
        if self.dest_blueprints_radio.isChecked():
            dest = 'blueprints'
        elif self.dest_job_radio.isChecked():
            dest = 'job'
        else:
            dest = 'both'
        
        added = 0
        skipped = 0

        # Ensure blueprint directory exists if needed
        if dest in ('blueprints', 'both'):
            customer_bp.mkdir(parents=True, exist_ok=True)

        for file_path in self.add_files:
            file_name = os.path.basename(file_path)

            try:
                if dest == 'blueprints':
                    # Copy only to blueprints
                    bp_dest = customer_bp / file_name
                    try:
                        shutil.copy2(file_path, bp_dest)
                        added += 1
                    except FileExistsError:
                        skipped += 1

                elif dest == 'job':
                    # Copy only to job folder
                    job_dest = Path(job_path) / file_name
                    try:
                        shutil.copy2(file_path, job_dest)
                        added += 1
                    except FileExistsError:
                        skipped += 1

                else:  # both
                    # Copy to blueprints, then link to job
                    bp_dest = customer_bp / file_name
                    try:
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass  # File already exists in blueprints

                    job_dest = Path(job_path) / file_name
                    if not job_dest.exists():
                        self.create_link(bp_dest, job_dest)
                        added += 1
                    else:
                        skipped += 1

            except Exception as e:
                self.log_message(f"Error adding {file_name}: {e}")
                skipped += 1
        
        self.add_status_label.setText(f"Added: {added}, Skipped: {skipped}")
        
        if added > 0:
            QMessageBox.information(self, "Files Added", f"Added {added} file(s) to {job_name}")
            self.clear_add_files()
    
    # ==================== Bulk Tab ====================
    
    def import_bulk_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.bulk_text.setPlainText(f.read())
                self.validate_bulk_data()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to read file: {e}")
    
    def parse_bulk_data(self) -> List[Dict[str, Any]]:
        content = self.bulk_text.toPlainText().strip()
        jobs = []
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                reader = csv.reader(StringIO(line))
                parts = next(reader)
            except (csv.Error, StopIteration):
                # Fall back to string split if CSV parsing fails
                parts = [p.strip() for p in line.split(',')]
            
            if len(parts) < 3:
                jobs.append({'line': line_num, 'valid': False, 'error': 'Need customer, job#, description'})
                continue
            
            customer = parts[0].strip()
            job_number = parts[1].strip()
            description = parts[2].strip()
            drawings = [d.strip() for d in parts[3:] if d.strip()]
            
            errors = []
            if not customer: errors.append("Missing customer")
            if not job_number: errors.append("Missing job#")
            if not description: errors.append("Missing description")
            
            jobs.append({
                'line': line_num,
                'valid': len(errors) == 0,
                'error': '; '.join(errors) if errors else None,
                'customer': customer,
                'job_number': job_number,
                'description': description,
                'drawings': drawings
            })
        
        return jobs
    
    def validate_bulk_data(self) -> bool:
        self.bulk_table.setRowCount(0)
        jobs = self.parse_bulk_data()
        
        valid = 0
        invalid = 0
        
        for job in jobs:
            row = self.bulk_table.rowCount()
            self.bulk_table.insertRow(row)
            
            if job['valid']:
                status = "✓ Valid"
                dup, dup_location = self.check_duplicate_job(job['customer'], job['job_number'])
                if dup:
                    status = f"⚠ Duplicate ({dup_location})"
                valid += 1
            else:
                status = f"✗ {job.get('error', 'Invalid')}"
                invalid += 1
            
            self.bulk_table.setItem(row, 0, QTableWidgetItem(status))
            self.bulk_table.setItem(row, 1, QTableWidgetItem(job.get('customer', '')))
            self.bulk_table.setItem(row, 2, QTableWidgetItem(job.get('job_number', '')))
            self.bulk_table.setItem(row, 3, QTableWidgetItem(job.get('description', '')))
            self.bulk_table.setItem(row, 4, QTableWidgetItem(', '.join(job.get('drawings', []))))
        
        self.bulk_status_label.setText(f"Valid: {valid} | Invalid: {invalid}")
        return invalid == 0
    
    def job_exists(self, customer: str, job_number: str, is_itar: bool) -> bool:
        """Check if a job already exists in the system"""
        # Check if duplicates are allowed
        if self.settings.get('allow_duplicate_jobs', False):
            return False

        bp_dir, cf_dir = self.get_directories(is_itar)
        if not cf_dir:
            return False

        # Check customer directory for any job folder starting with this job number
        customer_path = Path(cf_dir) / customer
        if not customer_path.exists():
            return False

        # Find all job folders
        jobs = self.find_job_folders(str(customer_path))
        for job_name, _ in jobs:
            # Check if job folder name starts with the job number
            if job_name.startswith(f"{job_number}_") or job_name == job_number:
                return True

        return False

    def create_bulk_jobs(self):
        if not self.validate_bulk_data():
            if QMessageBox.question(self, "Warning", "Some jobs have errors. Create only valid jobs?") != QMessageBox.StandardButton.Yes:
                return

        jobs = [j for j in self.parse_bulk_data() if j['valid']]
        if not jobs:
            QMessageBox.warning(self, "No Jobs", "No valid jobs to create")
            return

        is_itar = self.bulk_itar_check.isChecked()
        bp_dir, cf_dir = self.get_directories(is_itar)

        if not bp_dir or not cf_dir:
            QMessageBox.warning(self, "Error", "Directories not configured")
            return

        # Check for duplicates
        duplicates = []
        for job in jobs:
            if self.job_exists(job['customer'], job['job_number'], is_itar):
                duplicates.append(f"{job['customer']} - Job #{job['job_number']}")

        if duplicates:
            dup_list = "\n".join(duplicates[:10])
            if len(duplicates) > 10:
                dup_list += f"\n... and {len(duplicates) - 10} more"
            msg = f"The following jobs already exist:\n\n{dup_list}\n\nSkip duplicates and create remaining jobs?"
            if QMessageBox.question(self, "Duplicate Jobs Found", msg) != QMessageBox.StandardButton.Yes:
                return

        self.bulk_progress.setMaximum(len(jobs))
        self.bulk_progress.setValue(0)
        self.bulk_progress.show()

        # Track existing customers before creating jobs
        existing_customers = self._get_customers_from_dirs([
            'blueprints_dir', 'customer_files_dir',
            'itar_blueprints_dir', 'itar_customer_files_dir'
        ])
        new_customers = set()

        created = 0
        skipped = 0
        for i, job in enumerate(jobs):
            customer = job['customer']
            if customer not in existing_customers and customer not in new_customers:
                new_customers.add(customer)

            # Skip if job already exists
            if self.job_exists(customer, job['job_number'], is_itar):
                skipped += 1
            elif self.create_single_job(customer, job['job_number'], job['description'], job['drawings'], is_itar, []):
                created += 1

            self.bulk_progress.setValue(i + 1)
            QApplication.processEvents()

        self.bulk_progress.hide()
        msg = f"Created {created}/{len(jobs)} jobs"
        if skipped > 0:
            msg += f" (Skipped {skipped} duplicates)"
        QMessageBox.information(self, "Complete", msg)
        self.refresh_history()

        # Only refresh customer lists if new customers were created
        if new_customers:
            self.populate_customer_lists()
    
    # ==================== Search Tab ====================

    def update_search_field_checkboxes(self):
        """Enable/disable field checkboxes based on search mode"""
        # In "Search All Folders" mode, disable checkboxes since we search everything
        # In "Strict Format" mode, enable checkboxes for field-specific searching
        is_strict_mode = self.search_strict_radio.isChecked()

        self.search_customer_check.setEnabled(is_strict_mode)
        self.search_job_check.setEnabled(is_strict_mode)
        self.search_desc_check.setEnabled(is_strict_mode)
        self.search_drawing_check.setEnabled(is_strict_mode)

        # Show/hide legacy search options
        self.legacy_options_widget.setVisible(not is_strict_mode)

    def update_legacy_mode_ui(self):
        """Show/hide UI elements based on legacy mode setting"""
        is_legacy = self.settings.get('legacy_mode', True)

        # Show/hide "Search All Folders" option
        if is_legacy:
            # Show both radio buttons
            self.mode_row_widget.setVisible(True)
        else:
            # Hide mode selection, force Strict Format
            self.mode_row_widget.setVisible(False)
            self.search_strict_radio.setChecked(True)

        # Update checkbox states
        self.update_search_field_checkboxes()


    def perform_search(self):
        search_term = self.search_edit.text().strip().lower()
        if not search_term:
            QMessageBox.warning(self, "Search", "Enter a search term")
            return

        self.search_table.setRowCount(0)
        self.search_results.clear()

        strict_mode = self.search_strict_radio.isChecked()

        # Build list of directories to search
        dirs_to_search = []

        # Always search customer files directories
        customer_dirs = self._get_customer_files_dirs()
        if not customer_dirs:
            cf_dir = self.settings.get('customer_files_dir', '')
            itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
            if not cf_dir and not itar_cf_dir:
                QMessageBox.warning(self, "Error", "No customer directories configured. Please go to File → Settings to configure directories.")
            else:
                QMessageBox.warning(self, "Error", "Configured directories do not exist. Please check File → Settings.")
            return

        dirs_to_search.extend(customer_dirs)

        # In legacy mode, optionally search blueprints directories
        if not strict_mode and self.search_blueprints_check.isChecked():
            bp_dir = self.settings.get('blueprints_dir', '')
            if bp_dir and os.path.exists(bp_dir):
                dirs_to_search.append(('BP', bp_dir))
            itar_bp_dir = self.settings.get('itar_blueprints_dir', '')
            if itar_bp_dir and os.path.exists(itar_bp_dir):
                dirs_to_search.append(('ITAR-BP', itar_bp_dir))

        self.search_progress.setMaximum(0)
        self.search_progress.show()
        self.search_status_label.setText("Searching...")
        QApplication.processEvents()

        # In "Search All Folders" mode, search everything regardless of checkboxes
        # In "Strict Format" mode, respect checkbox selections
        if strict_mode:
            search_customer = self.search_customer_check.isChecked()
            search_job = self.search_job_check.isChecked()
            search_desc = self.search_desc_check.isChecked()
            search_drawing = self.search_drawing_check.isChecked()
        else:
            # Legacy mode: search all fields
            search_customer = True
            search_job = True
            search_desc = True
            search_drawing = True

        try:
            if strict_mode:
                # Strict mode: use structured search
                for prefix, base_dir in dirs_to_search:
                    try:
                        customers = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
                    except OSError:
                        continue

                    for customer in customers:
                        customer_path = os.path.join(base_dir, customer)
                        display_customer = f"[ITAR] {customer}" if prefix else customer

                        # Check if searching by customer name
                        customer_match = search_customer and search_term in customer.lower()

                        # Use helper method to find job folders
                        jobs = self.find_job_folders(customer_path)

                        for dir_name, job_docs_path in jobs:
                            # Apply strict mode filter
                            if not dir_name or not dir_name[0].isdigit():
                                continue

                            # Parse folder name into components
                            parts = dir_name.split('_')
                            job_num = parts[0] if parts else ""
                            remaining_parts = parts[1:] if len(parts) > 1 else []

                            drawings = []
                            desc_parts = []

                            if remaining_parts:
                                if '-' in remaining_parts[-1]:
                                    drawings = [d.strip() for d in remaining_parts[-1].split('-') if d.strip()]
                                    desc_parts = remaining_parts[:-1]
                                else:
                                    desc_parts = remaining_parts

                            desc = ' '.join(desc_parts) if desc_parts else ""

                            # Check for matches
                            match = customer_match

                            if not match and search_job and search_term in job_num.lower():
                                match = True
                            if not match and search_desc and search_term in desc.lower():
                                match = True
                            if not match and search_drawing:
                                for drawing in drawings:
                                    if search_term in drawing.lower():
                                        match = True
                                        break

                            if match:
                                try:
                                    mod_time = datetime.fromtimestamp(Path(job_docs_path).stat().st_mtime)
                                except (OSError, FileNotFoundError):
                                    mod_time = datetime.now()

                                self.search_results.append({
                                    'date': mod_time,
                                    'customer': display_customer,
                                    'job_number': job_num,
                                    'description': desc,
                                    'drawings': drawings,
                                    'path': job_docs_path
                                })
            else:
                # Legacy mode: full recursive search of all directories
                for prefix, base_dir in dirs_to_search:
                    self._legacy_recursive_search(base_dir, prefix, search_term)

            self.search_results.sort(key=lambda x: x['date'], reverse=True)

            for result in self.search_results:
                row = self.search_table.rowCount()
                self.search_table.insertRow(row)
                self.search_table.setItem(row, 0, QTableWidgetItem(result['date'].strftime("%Y-%m-%d %H:%M")))
                self.search_table.setItem(row, 1, QTableWidgetItem(result['customer']))
                self.search_table.setItem(row, 2, QTableWidgetItem(result['job_number']))
                self.search_table.setItem(row, 3, QTableWidgetItem(result['description']))
                self.search_table.setItem(row, 4, QTableWidgetItem(', '.join(result['drawings'])))

            self.search_status_label.setText(f"Found {len(self.search_results)} result(s)")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Search error: {e}")

        self.search_progress.hide()

    def _legacy_recursive_search(self, base_dir: str, prefix: str, search_term: str):
        """Recursively search all folders in legacy mode"""
        try:
            for root, dirs, files in os.walk(base_dir):
                # Get folder name
                folder_name = os.path.basename(root)

                # Try to extract customer from path
                rel_path = os.path.relpath(root, base_dir)
                path_parts = rel_path.split(os.sep)
                customer = path_parts[0] if path_parts and path_parts[0] != '.' else "Unknown"

                # Check if folder name or any part of path contains search term
                if search_term in folder_name.lower() or search_term in rel_path.lower():
                    # Try to parse folder name for job info
                    parts = folder_name.split('_')
                    job_num = ""
                    desc = ""
                    drawings = []

                    # Try to extract job number (look for digits)
                    for part in parts:
                        if part and part[0].isdigit():
                            job_num = part
                            break

                    # If no structured format, use folder name as description
                    if not job_num:
                        # Check if folder name starts with digits
                        import re
                        match = re.match(r'^(\d+)', folder_name)
                        if match:
                            job_num = match.group(1)
                            desc = folder_name[len(job_num):].strip(' -_')
                        else:
                            desc = folder_name
                    else:
                        # Parse remaining parts
                        remaining_parts = [p for p in parts if p != job_num]
                        if remaining_parts:
                            if '-' in remaining_parts[-1]:
                                drawings = [d.strip() for d in remaining_parts[-1].split('-') if d.strip()]
                                desc = ' '.join(remaining_parts[:-1])
                            else:
                                desc = ' '.join(remaining_parts)

                    display_customer = f"[{prefix}] {customer}" if prefix else customer

                    try:
                        mod_time = datetime.fromtimestamp(Path(root).stat().st_mtime)
                    except (OSError, FileNotFoundError):
                        mod_time = datetime.now()

                    self.search_results.append({
                        'date': mod_time,
                        'customer': display_customer,
                        'job_number': job_num if job_num else "(no job #)",
                        'description': desc,
                        'drawings': drawings,
                        'path': root
                    })
        except Exception as e:
            # Skip directories that cause errors
            pass
    
    def clear_search(self):
        self.search_edit.clear()
        self.search_table.setRowCount(0)
        self.search_results.clear()
        self.search_status_label.setText("")
    
    def show_search_context_menu(self, pos):
        row = self.search_table.currentRow()
        if row < 0:
            return
        
        menu = QMenu(self)
        
        open_action = menu.addAction("Open Job Folder")
        open_action.triggered.connect(self.open_selected_search_job)
        
        open_bp_action = menu.addAction("Open Blueprints Folder")
        open_bp_action.triggered.connect(self.open_selected_blueprints)
        
        menu.addSeparator()
        
        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(self.copy_search_path)
        
        menu.exec(self.search_table.viewport().mapToGlobal(pos))
    
    def open_selected_search_job(self):
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            if os.path.exists(path):
                self.open_folder(path)
            else:
                QMessageBox.warning(self, "Not Found", f"Folder not found: {path}")
    
    def open_selected_blueprints(self):
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            customer = self.search_results[row]['customer'].replace('[ITAR] ', '')
            bp_dir = self.settings.get('blueprints_dir', '')
            if bp_dir:
                customer_bp = os.path.join(bp_dir, customer)
                if os.path.exists(customer_bp):
                    self.open_folder(customer_bp)
                else:
                    QMessageBox.warning(self, "Not Found", f"Blueprints for {customer} not found")
    
    def copy_search_path(self):
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            QApplication.clipboard().setText(path)
            self.search_status_label.setText("Path copied to clipboard")
    
    # ==================== Import Tab ====================
    
    def handle_import_files(self, files: List[str]):
        for f in files:
            if f not in self.import_files:
                self.import_files.append(f)
                self.import_files_list.addItem(os.path.basename(f))
    
    def clear_import_list(self):
        self.import_files.clear()
        self.import_files_list.clear()
    
    def check_and_import(self):
        customer = self.import_customer_combo.currentText().strip()
        if not customer:
            QMessageBox.warning(self, "Error", "Please enter a customer name")
            return

        if not self.import_files:
            QMessageBox.warning(self, "Error", "Please add files")
            return

        # Check if ITAR is selected
        is_itar = self.import_itar_check.isChecked()
        bp_dir = self.settings.get('itar_blueprints_dir' if is_itar else 'blueprints_dir', '')

        if not bp_dir:
            dir_type = "ITAR blueprints" if is_itar else "Blueprints"
            QMessageBox.warning(self, "Error", f"{dir_type} directory not configured")
            return

        customer_bp = Path(bp_dir) / customer
        customer_bp.mkdir(parents=True, exist_ok=True)
        
        self.import_log.clear()
        
        imported = 0
        skipped = 0
        
        for file_path in self.import_files:
            file_name = os.path.basename(file_path)
            dest = customer_bp / file_name
            
            if dest.exists():
                self.import_log.appendPlainText(f"Exists: {file_name}")
                skipped += 1
            else:
                try:
                    shutil.copy2(file_path, dest)
                    self.import_log.appendPlainText(f"Imported: {file_name}")
                    imported += 1
                except Exception as e:
                    self.import_log.appendPlainText(f"Error: {file_name} - {e}")
        
        self.import_log.appendPlainText(f"\nDone! Imported: {imported}, Skipped: {skipped}")
        QMessageBox.information(self, "Complete", f"Imported: {imported}, Skipped: {skipped}")
        
        self.populate_customer_lists()
    
    # ==================== History Tab ====================
    
    def refresh_history(self):
        self.history_table.setRowCount(0)
        
        for job in self.history.get('recent_jobs', []):
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            
            try:
                date = datetime.fromisoformat(job['date']).strftime("%Y-%m-%d %H:%M")
            except:
                date = "Unknown"
            
            self.history_table.setItem(row, 0, QTableWidgetItem(date))
            self.history_table.setItem(row, 1, QTableWidgetItem(job.get('customer', '')))
            self.history_table.setItem(row, 2, QTableWidgetItem(job.get('job_number', '')))
            self.history_table.setItem(row, 3, QTableWidgetItem(job.get('description', '')))
            self.history_table.setItem(row, 4, QTableWidgetItem(', '.join(job.get('drawings', []))))
    
    def clear_history(self):
        if QMessageBox.question(self, "Confirm", "Clear all history?") == QMessageBox.StandardButton.Yes:
            self.history = {'customers': {}, 'recent_jobs': []}
            self.save_history()
            self.refresh_history()
    
    # ==================== Settings & About ====================
    
    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.save_settings()
            self.populate_customer_lists()
            self.populate_add_customer_list()

            # Update search tab based on new legacy mode setting
            self.update_legacy_mode_ui()

            QMessageBox.information(self, "Settings", "Settings saved")

    def show_getting_started(self):
        folder_term = get_os_text('folder_term')
        os_type = get_os_type()
        path_example = get_os_text('path_example')

        # OS-specific link recommendation
        if os_type == "windows":
            link_info = "Hard Link recommended (saves space, works on same drive)"
        else:
            link_info = "Hard Link recommended (saves space)"

        content = f"""
<h2>GETTING STARTED</h2>

<p><b>1. Go to File → Settings</b><br>
<b>2. Configure directories:</b><br>
&nbsp;&nbsp;- Blueprints Directory: Central drawing storage<br>
&nbsp;&nbsp;- Customer Files Directory: Where job {folder_term}s are created<br>
<b>3. Choose link type ({link_info})</b><br>
<b>4. Set blueprint file extensions</b></p>

<p><b>Advanced (optional):</b><br>
Enable "Advanced Settings" in Settings to customize job {folder_term} structure<br>
&nbsp;&nbsp;- Default: {path_example}<br>

<h2>CREATE JOB TAB</h2>

<p><b>Enter job information:</b><br>
- Customer Name (auto-completes)<br>
- Job Number(s): single, comma-separated, or range (12345-12350)<br>
- Description<br>
- Drawing Numbers (optional)<br>
- ITAR checkbox for controlled jobs</p>

<p><b>Drop files or click browse to add files:</b><br>
- Blueprint files → saved to blueprints, linked to job<br>
- Other files → copied to job {folder_term}</p>

<h2>BULK CREATE TAB</h2>

<p><b>Create multiple jobs at once:</b><br>
1. Enter jobs in CSV format (one per line)<br>
2. Format: customer, job_number, description, drawings...<br>
3. Click Validate to check for errors<br>
4. Click Create All Jobs</p>

<p><b>Example:</b><br>
Acme Corp, 12345, Widget Assembly, DWG-001<br>
Acme Corp, 12346, Gadget Housing, DWG-002</p>

<h2>SEARCH TAB</h2>

<p>Find jobs by customer, job number, description, or drawing.</p>

<p><b>Search Modes:</b><br>
- All Folders: Searches everything (slower, finds legacy files)<br>
- Strict: Only numbered {folder_term}s (faster, new files only)</p>

<p>Double-click or right-click results to open {folder_term}s.</p>

<h2>IMPORT TAB</h2>

<p><b>Import files directly to blueprints {folder_term}:</b><br>
1. Select customer<br>
2. Drop/browse files<br>
3. Click Check & Import</p>

<h2>TIPS</h2>

<p>- Hard links save disk space (blueprints appear in multiple {folder_term}s)<br>
- ITAR jobs use separate directories<br>
- Autocomplete learns from history<br>
- Check for duplicates before creating</p>
"""
        dialog = ScrollableMessageDialog(self, "Getting Started", content, width=650, height=600)
        dialog.exec()

    # ==================== Experimental: Database/Reporting Methods ====================

    def connect_to_database(self):
        """Connect to database using settings (placeholder)"""
        db_type = self.settings.get('db_type', 'mssql')
        host = self.settings.get('db_host', 'localhost')
        port = self.settings.get('db_port', 1433)
        database = self.settings.get('db_name', '')

        if not database:
            QMessageBox.warning(
                self,
                "Database Not Configured",
                "Please configure database settings in Settings > Advanced > Experimental."
            )
            return

        # Placeholder - actual implementation would use db_integration.py
        self.db_status_label.setText(f"Status: Connected to {database} (placeholder)")
        self.db_status_label.setStyleSheet("color: green;")
        self.connect_db_btn.setEnabled(False)
        self.disconnect_db_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Database Connection",
            f"Placeholder: Would connect to {db_type} database:\n\n"
            f"Host: {host}:{port}\n"
            f"Database: {database}\n\n"
            f"To implement, see db_integration.py"
        )

    def disconnect_from_database(self):
        """Disconnect from database (placeholder)"""
        self.db_status_label.setText("Status: Not connected")
        self.db_status_label.setStyleSheet("color: #999;")
        self.connect_db_btn.setEnabled(True)
        self.disconnect_db_btn.setEnabled(False)

    def generate_report(self):
        """Generate report from database (placeholder)"""
        report_type = self.report_type_combo.currentText()

        # Clear existing data
        self.report_table.setRowCount(0)

        # Placeholder data
        sample_data = [
            ["2025-01-15", "Acme Corporation", "12345", "Widget Assembly", "Active"],
            ["2025-01-14", "Beta Industries", "54321", "Custom Bracket", "Completed"],
            ["2025-01-13", "Acme Corporation", "12346", "Housing Unit", "Active"],
            ["2025-01-12", "Gamma Systems", "99999", "Shaft Assembly", "Active"],
        ]

        # Populate table with sample data
        for row_data in sample_data:
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                self.report_table.setItem(row, col, item)

        self.report_status_label.setText(
            f"Showing {len(sample_data)} sample records for '{report_type}' (placeholder)\n"
            "To implement: Connect to database and query actual data using db_integration.py"
        )

    def export_report(self):
        """Export report to CSV (placeholder)"""
        if self.report_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Generate a report first before exporting.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)

                    # Write headers
                    headers = []
                    for col in range(self.report_table.columnCount()):
                        headers.append(self.report_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)

                    # Write data
                    for row in range(self.report_table.rowCount()):
                        row_data = []
                        for col in range(self.report_table.columnCount()):
                            item = self.report_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                QMessageBox.information(self, "Export Successful", f"Report exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export report:\n{str(e)}")

    # ==================== About/Help ====================

    def show_about(self):
        folder_term = get_os_text('folder_term')
        os_type = get_os_type()

        # OS-specific note about hard links
        if os_type == "windows":
            link_note = "<p><i>Note: Hard links work for blueprint files without admin rights. Files must be on the same volume. Use Copy mode if blueprints are on different drives.</i></p>"
        else:
            link_note = f"<p><i>Note: Hard links allow blueprint files to appear in multiple job {folder_term}s while only using disk space once.</i></p>"

        content = f"""
<h2>JobDocs</h2>
<p>A tool for managing blueprint files and customer job {folder_term}s.</p>

<h3>Features:</h3>
<ul>
<li>Single and bulk job creation</li>
<li>Add files to existing jobs</li>
<li>Blueprint file linking (hard links save disk space)</li>
<li>File system search</li>
<li>Import tools</li>
<li>ITAR {folder_term} support</li>
<li>History tracking</li>
</ul>

{link_note}

<p>Built with Python and PyQt6</p>

<p><a href="https://github.com/i-machine-things/JobDocs">github.com/i-machine-things/JobDocs</a></p>
"""
        dialog = ScrollableMessageDialog(self, "About JobDocs", content, width=500, height=400)
        dialog.exec()


def main():
    app = QApplication(sys.argv)

    # Load settings to get UI style preference
    config_dir = get_config_dir()
    settings_file = config_dir / 'settings.json'
    ui_style = 'Fusion'  # Default

    if settings_file.exists():
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                ui_style = settings.get('ui_style', 'Fusion')
        except (json.JSONDecodeError, IOError):
            pass

    # Set the style
    app.setStyle(ui_style)

    window = JobDocs()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
