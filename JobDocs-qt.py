"""
JobDocs - A tool for managing blueprint links and customer files
Qt version for modern UI
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
    QHeaderView, QAbstractItemView, QSizePolicy
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


class DropZone(QFrame):
    """A widget that accepts file drops"""
    files_dropped = pyqtSignal(list)
    
    def __init__(self, label: str = "Drop files here", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(80)
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 8px;
            }
            DropZone:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.label = QLabel(f"{label}\nor click Browse")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.label)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_files)
        self.browse_btn.setMaximumWidth(100)
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
        layout = QVBoxLayout(self)
        
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
        
        layout.addWidget(dir_group)
        
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
        
        layout.addWidget(itar_group)
        
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
        
        layout.addWidget(link_group)
        
        # Blueprint extensions
        ext_group = QGroupBox("Blueprint File Types")
        ext_layout = QVBoxLayout(ext_group)
        
        ext_layout.addWidget(QLabel("Files with these extensions go to blueprints folder:"))
        self.extensions_edit = QLineEdit(
            ', '.join(self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf']))
        )
        ext_layout.addWidget(self.extensions_edit)
        ext_layout.addWidget(QLabel("(comma-separated, e.g., .pdf, .dwg, .dxf)"))
        
        layout.addWidget(ext_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.allow_duplicates_check = QCheckBox("Allow duplicate job numbers (not recommended)")
        self.allow_duplicates_check.setChecked(self.settings.get('allow_duplicate_jobs', False))
        options_layout.addWidget(self.allow_duplicates_check)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def browse_dir(self, line_edit: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            line_edit.setText(dir_path)
    
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
        
        self.settings['allow_duplicate_jobs'] = self.allow_duplicates_check.isChecked()
        
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
        'allow_duplicate_jobs': False
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JobDocs")
        self.setMinimumSize(1000, 750)
        
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
        
        self.setup_ui()
        self.setup_menu()
        self.populate_customer_lists()
    
    def load_settings(self) -> Dict[str, Any]:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    merged = self.DEFAULT_SETTINGS.copy()
                    merged.update(settings)
                    return merged
            except:
                pass
        return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def load_history(self) -> Dict[str, Any]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'customers': {}, 'recent_jobs': []}
    
    def save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Create tabs
        self.tabs.addTab(self.create_job_tab(), "Create Job")
        self.tabs.addTab(self.create_add_to_job_tab(), "Add to Job")
        self.tabs.addTab(self.create_bulk_tab(), "Bulk Create")
        self.tabs.addTab(self.create_search_tab(), "Search")
        self.tabs.addTab(self.create_import_tab(), "Import Blueprints")
        self.tabs.addTab(self.create_history_tab(), "History")
    
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
    
    def create_job_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Job info group
        info_group = QGroupBox("Job Information")
        info_layout = QGridLayout(info_group)
        
        # Customer
        info_layout.addWidget(QLabel("Customer Name:"), 0, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setEditable(True)
        self.customer_combo.setMinimumWidth(300)
        info_layout.addWidget(self.customer_combo, 0, 1)
        
        # Job number
        info_layout.addWidget(QLabel("Job Number(s):"), 1, 0)
        self.job_number_edit = QLineEdit()
        self.job_number_edit.setPlaceholderText("e.g., 12345 or 12345, 12346 or 12345-12350")
        info_layout.addWidget(self.job_number_edit, 1, 1)
        self.job_status_label = QLabel("")
        info_layout.addWidget(self.job_status_label, 1, 2)
        
        # Description
        info_layout.addWidget(QLabel("Description:"), 2, 0)
        self.description_edit = QLineEdit()
        info_layout.addWidget(self.description_edit, 2, 1)
        
        # Drawings
        info_layout.addWidget(QLabel("Drawing Numbers:"), 3, 0)
        self.drawings_edit = QLineEdit()
        self.drawings_edit.setPlaceholderText("comma-separated, optional")
        info_layout.addWidget(self.drawings_edit, 3, 1)
        
        # ITAR
        self.itar_check = QCheckBox("ITAR Job (uses separate directories)")
        info_layout.addWidget(self.itar_check, 4, 1)
        
        layout.addWidget(info_group)
        
        # Files group
        files_group = QGroupBox("Job Files (Optional)")
        files_layout = QVBoxLayout(files_group)
        
        files_layout.addWidget(QLabel("Blueprint files → blueprints folder, others → job folder"))
        
        self.job_drop_zone = DropZone("Drop job files here")
        self.job_drop_zone.files_dropped.connect(self.handle_job_files)
        files_layout.addWidget(self.job_drop_zone)
        
        self.job_files_list = QListWidget()
        self.job_files_list.setMaximumHeight(100)
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
        create_btn.setStyleSheet("font-weight: bold; padding: 8px 16px;")
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
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)
        
        return widget
    
    def create_add_to_job_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Add documents to an existing job folder and/or blueprints"))
        
        # Splitter for left/right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left - Job browser
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        browser_group = QGroupBox("Select Existing Job")
        browser_layout = QVBoxLayout(browser_group)
        
        # Filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Customer:"))
        self.add_customer_combo = QComboBox()
        self.add_customer_combo.setMinimumWidth(150)
        self.add_customer_combo.currentTextChanged.connect(self.refresh_job_tree)
        filter_layout.addWidget(self.add_customer_combo)
        
        self.add_itar_check = QCheckBox("ITAR only")
        self.add_itar_check.stateChanged.connect(self.refresh_job_tree)
        filter_layout.addWidget(self.add_itar_check)
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
        
        left_layout.addWidget(browser_group)
        splitter.addWidget(left_widget)
        
        # Right - Add files
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        add_group = QGroupBox("Add Files")
        add_layout = QVBoxLayout(add_group)
        
        # Destination options
        dest_group = QGroupBox("Destination")
        dest_layout = QVBoxLayout(dest_group)
        
        self.dest_both_radio = QRadioButton("Blueprints + Job (linked)")
        self.dest_both_radio.setChecked(True)
        self.dest_blueprints_radio = QRadioButton("Blueprints only")
        self.dest_job_radio = QRadioButton("Job folder only (copy)")
        
        dest_layout.addWidget(self.dest_both_radio)
        dest_layout.addWidget(self.dest_blueprints_radio)
        dest_layout.addWidget(self.dest_job_radio)
        add_layout.addWidget(dest_group)
        
        # Drop zone
        self.add_drop_zone = DropZone("Drop files to add")
        self.add_drop_zone.files_dropped.connect(self.handle_add_files)
        add_layout.addWidget(self.add_drop_zone)
        
        # File list
        self.add_files_list = QListWidget()
        self.add_files_list.setMaximumHeight(120)
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
        add_files_btn = QPushButton("Add Files to Selected Job")
        add_files_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        add_files_btn.clicked.connect(self.add_files_to_job)
        add_layout.addWidget(add_files_btn)
        
        self.add_status_label = QLabel("")
        add_layout.addWidget(self.add_status_label)
        
        right_layout.addWidget(add_group)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([450, 450])
        layout.addWidget(splitter)
        
        # Initialize
        QTimer.singleShot(100, self.populate_add_customer_list)
        
        return widget
    
    def create_bulk_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Instructions
        inst_group = QGroupBox("Bulk Job Creation")
        inst_layout = QVBoxLayout(inst_group)
        inst_layout.addWidget(QLabel("Create multiple jobs at once. Format: customer, job_number, description, drawing1, drawing2, ..."))
        inst_layout.addWidget(QLabel("Example: Acme Corp, 12345, Widget Assembly, DWG-001"))
        
        self.bulk_itar_check = QCheckBox("All jobs are ITAR")
        inst_layout.addWidget(self.bulk_itar_check)
        layout.addWidget(inst_group)
        
        # Text input
        text_group = QGroupBox("Job Data (CSV Format)")
        text_layout = QVBoxLayout(text_group)
        
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
            "# Enter jobs in CSV format (lines starting with # are ignored)\n"
            "Acme Corp, 12345, Widget Assembly, DWG-001\n"
            "Beta Inc, 54321, Custom Part"
        )
        text_layout.addWidget(self.bulk_text)
        layout.addWidget(text_group)
        
        # Preview table
        preview_group = QGroupBox("Preview / Validation")
        preview_layout = QVBoxLayout(preview_group)
        
        self.bulk_table = QTableWidget()
        self.bulk_table.setColumnCount(5)
        self.bulk_table.setHorizontalHeaderLabels(["Status", "Customer", "Job Number", "Description", "Drawings"])
        self.bulk_table.horizontalHeader().setStretchLastSection(True)
        self.bulk_table.setMaximumHeight(200)
        preview_layout.addWidget(self.bulk_table)
        layout.addWidget(preview_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        create_bulk_btn = QPushButton("Create All Jobs")
        create_bulk_btn.setStyleSheet("font-weight: bold; padding: 8px 16px;")
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
        
        # Search controls
        search_group = QGroupBox("Search Criteria")
        search_layout = QVBoxLayout(search_group)
        
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
        
        # Mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.search_all_radio = QRadioButton("Search All Folders")
        self.search_all_radio.setChecked(True)
        mode_row.addWidget(self.search_all_radio)
        
        self.search_strict_radio = QRadioButton("Strict Format (faster)")
        mode_row.addWidget(self.search_strict_radio)
        mode_row.addStretch()
        search_layout.addLayout(mode_row)
        
        layout.addWidget(search_group)
        
        # Results
        results_group = QGroupBox("Search Results")
        results_layout = QVBoxLayout(results_group)
        
        self.search_table = QTableWidget()
        self.search_table.setColumnCount(5)
        self.search_table.setHorizontalHeaderLabels(["Date", "Customer", "Job Number", "Description", "Drawings"])
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
        
        layout.addWidget(QLabel("Import files to blueprints folder"))
        
        # Customer selection
        select_group = QGroupBox("Customer Selection")
        select_layout = QHBoxLayout(select_group)
        select_layout.addWidget(QLabel("Customer:"))
        self.import_customer_combo = QComboBox()
        self.import_customer_combo.setEditable(True)
        self.import_customer_combo.setMinimumWidth(250)
        select_layout.addWidget(self.import_customer_combo)
        select_layout.addStretch()
        layout.addWidget(select_group)
        
        # Drop zone
        files_group = QGroupBox("Files to Import")
        files_layout = QVBoxLayout(files_group)
        
        self.import_drop_zone = DropZone("Drop files to import")
        self.import_drop_zone.files_dropped.connect(self.handle_import_files)
        files_layout.addWidget(self.import_drop_zone)
        
        self.import_files_list = QListWidget()
        self.import_files_list.setMaximumHeight(150)
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
        self.import_log = QPlainTextEdit()
        self.import_log.setReadOnly(True)
        results_layout.addWidget(self.import_log)
        layout.addWidget(results_group)
        
        return widget
    
    def create_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # History table
        history_group = QGroupBox("Recent Jobs")
        history_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Date", "Customer", "Job Number", "Description", "Drawings"])
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
    
    # ==================== Helper Methods ====================
    
    def populate_customer_lists(self):
        customers = set()
        
        for dir_key in ['blueprints_dir', 'customer_files_dir', 'itar_blueprints_dir', 'itar_customer_files_dir']:
            dir_path = self.settings.get(dir_key, '')
            if dir_path and os.path.exists(dir_path):
                try:
                    for d in os.listdir(dir_path):
                        if os.path.isdir(os.path.join(dir_path, d)):
                            customers.add(d)
                except OSError:
                    pass
        
        for customer in self.history.get('customers', {}).keys():
            customers.add(customer)
        
        sorted_customers = sorted(customers)
        
        self.customer_combo.clear()
        self.customer_combo.addItems(sorted_customers)
        
        self.import_customer_combo.clear()
        self.import_customer_combo.addItems(sorted_customers)
    
    def populate_add_customer_list(self):
        customers = set()
        
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            dir_path = self.settings.get(dir_key, '')
            if dir_path and os.path.exists(dir_path):
                try:
                    for d in os.listdir(dir_path):
                        if os.path.isdir(os.path.join(dir_path, d)):
                            customers.add(d)
                except OSError:
                    pass
        
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
        import platform
        import subprocess
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
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
        for job in self.history.get('recent_jobs', []):
            if (job.get('customer', '').lower() == customer.lower() and
                job.get('job_number', '').lower() == job_number.lower()):
                return True, job.get('path', 'Unknown')
        
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir:
            job_docs = Path(cf_dir) / customer / 'job documents'
            if job_docs.exists():
                for item in job_docs.iterdir():
                    if item.is_dir():
                        parts = item.name.split('_', 1)
                        if parts and parts[0].lower() == job_number.lower():
                            return True, str(item)
        
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
        
        self.log_message(f"Creating job(s): {', '.join(job_numbers)}")
        
        created = 0
        for job_num in job_numbers:
            if self.create_single_job(customer, job_num, description, drawings, is_itar, self.job_files):
                created += 1
        
        QMessageBox.information(self, "Success", f"Created {created}/{len(job_numbers)} job(s)")
        
        self.job_files.clear()
        self.job_files_list.clear()
        self.refresh_history()
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
            
            job_path = Path(cf_dir) / customer / 'job documents' / job_dir_name
            job_path.mkdir(parents=True, exist_ok=True)
            
            customer_bp = Path(bp_dir) / customer
            customer_bp.mkdir(parents=True, exist_ok=True)
            
            for file_path in files:
                file_name = os.path.basename(file_path)
                
                if self.is_blueprint_file(file_name):
                    bp_dest = customer_bp / file_name
                    if not bp_dest.exists():
                        shutil.copy2(file_path, bp_dest)
                    
                    job_dest = job_path / file_name
                    if not job_dest.exists():
                        self.create_link(bp_dest, job_dest)
                else:
                    job_dest = job_path / file_name
                    if not job_dest.exists():
                        shutil.copy2(file_path, job_dest)
            
            # Link existing drawings
            if drawings:
                exts = self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
                for drawing in drawings:
                    for ext in exts:
                        for bp_file in customer_bp.glob(f"*{drawing}*{ext}"):
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
        
        show_itar_only = self.add_itar_check.isChecked()
        selected_customer = self.add_customer_combo.currentText()
        show_all_customers = selected_customer == "(All Customers)" or not selected_customer
        
        dirs_to_search = []
        
        if not show_itar_only:
            cf_dir = self.settings.get('customer_files_dir', '')
            if cf_dir and os.path.exists(cf_dir):
                dirs_to_search.append(('', cf_dir))
        
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
                    job_docs = os.path.join(cf_dir, customer, 'job documents')
                    if not os.path.exists(job_docs):
                        continue
                    
                    display_name = f"[{prefix}] {customer}" if prefix else customer
                    customer_item = QTreeWidgetItem([display_name])
                    customer_item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(cf_dir, customer))
                    
                    jobs = sorted([d for d in os.listdir(job_docs) if os.path.isdir(os.path.join(job_docs, d))])
                    for job in jobs:
                        job_item = QTreeWidgetItem([job])
                        job_item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(job_docs, job))
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
        
        dirs_to_search = []
        
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs_to_search.append(('', cf_dir))
        
        itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            dirs_to_search.append(('ITAR', itar_cf_dir))
        
        results = 0
        
        for prefix, cf_dir in dirs_to_search:
            try:
                customers = [d for d in os.listdir(cf_dir) if os.path.isdir(os.path.join(cf_dir, d))]
                
                for customer in sorted(customers):
                    job_docs = os.path.join(cf_dir, customer, 'job documents')
                    if not os.path.exists(job_docs):
                        continue
                    
                    matching_jobs = []
                    jobs = [d for d in os.listdir(job_docs) if os.path.isdir(os.path.join(job_docs, d))]
                    
                    for job in jobs:
                        if search_term in job.lower() or search_term in customer.lower():
                            matching_jobs.append((job, os.path.join(job_docs, job)))
                    
                    if matching_jobs:
                        display_name = f"[{prefix}] {customer}" if prefix else customer
                        customer_item = QTreeWidgetItem([display_name])
                        customer_item.setData(0, Qt.ItemDataRole.UserRole, os.path.join(cf_dir, customer))
                        
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
        
        for file_path in self.add_files:
            file_name = os.path.basename(file_path)
            
            try:
                if dest == 'blueprints':
                    customer_bp.mkdir(parents=True, exist_ok=True)
                    bp_dest = customer_bp / file_name
                    if not bp_dest.exists():
                        shutil.copy2(file_path, bp_dest)
                        added += 1
                    else:
                        skipped += 1
                        
                elif dest == 'job':
                    job_dest = Path(job_path) / file_name
                    if not job_dest.exists():
                        shutil.copy2(file_path, job_dest)
                        added += 1
                    else:
                        skipped += 1
                        
                else:  # both
                    customer_bp.mkdir(parents=True, exist_ok=True)
                    bp_dest = customer_bp / file_name
                    if not bp_dest.exists():
                        shutil.copy2(file_path, bp_dest)
                    
                    job_dest = Path(job_path) / file_name
                    if not job_dest.exists():
                        self.create_link(bp_dest, job_dest)
                        added += 1
                    else:
                        skipped += 1
                        
            except Exception as e:
                self.log_message(f"Error adding {file_name}: {e}")
        
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
            except:
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
                dup, _ = self.check_duplicate_job(job['customer'], job['job_number'])
                if dup:
                    status = "⚠ Duplicate"
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
        
        self.bulk_progress.setMaximum(len(jobs))
        self.bulk_progress.setValue(0)
        self.bulk_progress.show()
        
        created = 0
        for i, job in enumerate(jobs):
            if self.create_single_job(job['customer'], job['job_number'], job['description'], job['drawings'], is_itar, []):
                created += 1
            self.bulk_progress.setValue(i + 1)
            QApplication.processEvents()
        
        self.bulk_progress.hide()
        QMessageBox.information(self, "Complete", f"Created {created}/{len(jobs)} jobs")
        self.refresh_history()
        self.populate_customer_lists()
    
    # ==================== Search Tab ====================
    
    def perform_search(self):
        search_term = self.search_edit.text().strip().lower()
        if not search_term:
            QMessageBox.warning(self, "Search", "Enter a search term")
            return
        
        self.search_table.setRowCount(0)
        self.search_results.clear()
        
        dirs_to_search = []
        
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs_to_search.append(('', cf_dir))
        
        itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            dirs_to_search.append(('ITAR', itar_cf_dir))
        
        if not dirs_to_search:
            QMessageBox.warning(self, "Error", "No directories configured")
            return
        
        self.search_progress.setMaximum(0)
        self.search_progress.show()
        self.search_status_label.setText("Searching...")
        QApplication.processEvents()
        
        strict_mode = self.search_strict_radio.isChecked()
        
        try:
            for prefix, base_dir in dirs_to_search:
                for root, dirs, _ in os.walk(base_dir):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        rel_path = os.path.relpath(dir_path, base_dir)
                        parts = rel_path.split(os.sep)
                        customer = parts[0] if parts else "Unknown"
                        
                        display_customer = f"[ITAR] {customer}" if prefix else customer
                        
                        if strict_mode and not dir_name[0].isdigit():
                            continue
                        
                        match = False
                        folder_lower = dir_name.lower()
                        
                        if self.search_customer_check.isChecked() and search_term in customer.lower():
                            match = True
                        if self.search_job_check.isChecked() and search_term in folder_lower:
                            match = True
                        if self.search_desc_check.isChecked() and search_term in folder_lower:
                            match = True
                        if self.search_drawing_check.isChecked() and search_term in folder_lower:
                            match = True
                        
                        if match:
                            name_parts = dir_name.replace('_', ' ').split()
                            job_num = name_parts[0] if name_parts else ""
                            desc = ' '.join(name_parts[1:]) if len(name_parts) > 1 else dir_name
                            
                            drawings = []
                            for p in name_parts:
                                if '-' in p:
                                    drawings.extend([d.strip() for d in p.split('-') if d.strip()])
                            
                            try:
                                mod_time = datetime.fromtimestamp(os.path.getmtime(dir_path))
                            except:
                                mod_time = datetime.now()
                            
                            self.search_results.append({
                                'date': mod_time,
                                'customer': display_customer,
                                'job_number': job_num,
                                'description': desc,
                                'drawings': drawings,
                                'path': dir_path
                            })
            
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
        
        bp_dir = self.settings.get('blueprints_dir', '')
        if not bp_dir:
            QMessageBox.warning(self, "Error", "Blueprints directory not configured")
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
            self.save_settings():
            self.populate_customer_lists()
            self.populate_add_customer_list()
            QMessageBox.information(self, "Settings", "Settings saved")
    
    def show_about(self):
        QMessageBox.about(self, "About JobDocs", """
<h2>JobDocs</h2>
<p>A tool for managing blueprint files and customer job directories.</p>

<b>Features:</b>
<ul>
<li>Single and bulk job creation</li>
<li>Add files to existing jobs</li>
<li>Blueprint file linking (hard links save disk space)</li>
<li>File system search</li>
<li>Import tools</li>
<li>ITAR directory support</li>
<li>History tracking</li>
</ul>

<p>github.com/i-machine-things/JobDocs</p>
""")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = JobDocs()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
