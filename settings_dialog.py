"""
Settings Dialog for JobDocs

Provides a UI for configuring application settings including:
- Directory paths
- Link types
- File extensions
- Advanced options
- Experimental features
"""

from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QComboBox, QScrollArea,
    QWidget, QFrame, QDialogButtonBox, QFileDialog, QMessageBox,
    QStyleFactory
)

from shared.utils import get_os_type, get_os_text


class SettingsDialog(QDialog):
    """Settings dialog"""

    def __init__(self, settings: Dict[str, Any], parent=None, available_modules: List[tuple] = None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.available_modules = available_modules or []  # List of (module_name, display_name) tuples
        self.module_checkboxes = {}  # Store module checkboxes
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setup_ui()

    def setup_ui(self):
        # Main dialog layout
        main_layout = QVBoxLayout(self)

        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

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
            self.hard_radio.setToolTip("Creates a hard link. Saves disk space. Files must be on same volume.")
            self.symbolic_radio.setToolTip("Creates a symbolic link. Requires admin or Developer Mode.")
            self.copy_radio.setToolTip("Creates independent copy. Use if on different drives.")
        else:
            self.hard_radio.setToolTip("Creates a hard link. Recommended - saves disk space.")
            self.symbolic_radio.setToolTip("Creates a symbolic link.")
            self.copy_radio.setToolTip("Creates an independent copy.")

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
            "Quote",
            "Job",
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

        # Modules section
        if self.available_modules:
            modules_group = QGroupBox("Modules")
            modules_layout = QVBoxLayout(modules_group)

            modules_layout.addWidget(QLabel("Enable or disable modules (requires restart):"))

            disabled_modules = self.settings.get('disabled_modules', [])

            for module_name, display_name in sorted(self.available_modules, key=lambda x: x[1]):
                checkbox = QCheckBox(display_name)
                checkbox.setChecked(module_name not in disabled_modules)
                self.module_checkboxes[module_name] = checkbox
                modules_layout.addWidget(checkbox)

            scroll_layout.addWidget(modules_group)

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

        self.advanced_content = QWidget()
        advanced_content_layout = QVBoxLayout(self.advanced_content)
        advanced_content_layout.setContentsMargins(0, 0, 0, 0)

        path_example = get_os_text('path_example')
        path_sep = get_os_text('path_sep')
        legacy_example = f"{{customer}}{path_sep}job documents{path_sep}{{job_folder}}"

        advanced_content_layout.addWidget(QLabel("Job Folder Structure:"))
        advanced_content_layout.addWidget(QLabel("Available placeholders: {customer}, {job_folder}"))
        advanced_content_layout.addWidget(QLabel(f"Default: {path_example}"))
        advanced_content_layout.addWidget(QLabel(f"Legacy: {legacy_example}"))

        self.job_structure_edit = QLineEdit(
            self.settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')
        )
        advanced_content_layout.addWidget(self.job_structure_edit)

        advanced_content_layout.addWidget(QLabel(""))

        advanced_content_layout.addWidget(QLabel("Quote Folder Path:"))
        self.quote_folder_edit = QLineEdit(self.settings.get('quote_folder_path', 'Quotes'))
        advanced_content_layout.addWidget(self.quote_folder_edit)

        advanced_content_layout.addWidget(QLabel(""))

        self.legacy_mode_check = QCheckBox("Enable legacy mode (shows 'Search All Folders' option)")
        self.legacy_mode_check.setChecked(self.settings.get('legacy_mode', True))
        advanced_content_layout.addWidget(self.legacy_mode_check)

        advanced_content_layout.addWidget(QLabel(""))

        self.experimental_check = QCheckBox("Enable experimental features (Reporting)")
        self.experimental_check.setChecked(self.settings.get('experimental_features', False))
        self.experimental_check.setToolTip("Enables experimental features. Requires restart.")
        advanced_content_layout.addWidget(self.experimental_check)

        advanced_layout.addWidget(self.advanced_content)

        self.advanced_content.setVisible(False)
        self.advanced_group.toggled.connect(self.advanced_content.setVisible)

        scroll_layout.addWidget(self.advanced_group)

        # Set scroll widget and add to main layout
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Buttons
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
        self.settings['quote_folder_path'] = self.quote_folder_edit.text().strip()
        self.settings['legacy_mode'] = self.legacy_mode_check.isChecked()
        self.settings['allow_duplicate_jobs'] = self.allow_duplicates_check.isChecked()
        self.settings['ui_style'] = self.style_combo.currentText()
        self.settings['default_tab'] = self.default_tab_combo.currentIndex()
        self.settings['experimental_features'] = self.experimental_check.isChecked()

        # Save disabled modules
        disabled_modules = []
        for module_name, checkbox in self.module_checkboxes.items():
            if not checkbox.isChecked():
                disabled_modules.append(module_name)
        self.settings['disabled_modules'] = disabled_modules

        self.accept()
