"""
Settings Dialog for JobDocs

Provides a UI for configuring application settings including:
- Directory paths
- Link types
- File extensions
- Advanced options
- Experimental features
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup, QComboBox, QScrollArea,
    QWidget, QFrame, QDialogButtonBox, QFileDialog,
    QStyleFactory
)

from shared.utils import get_os_type, get_os_text


class SettingsDialog(QDialog):
    """Settings dialog"""

    def __init__(self, settings: Dict[str, Any], parent=None,
                 available_modules: Optional[List[tuple]] = None,
                 save_callback: Optional[Callable[..., Any]] = None,
                 active_keys: Optional[set] = None):
        super().__init__(parent)
        self.settings = settings.copy()
        self._active_keys = active_keys  # keys present in DEFAULT_SETTINGS; None means show all
        self.available_modules = available_modules or []  # List of (module_name, display_name) tuples
        self.module_checkboxes = {}  # Store module checkboxes
        self._save_callback = save_callback  # Called to persist settings to disk mid-dialog
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setup_ui()

    # ------------------------------------------------------------------
    def _active(self, key: str) -> bool:
        """Return True if this setting key is present in DEFAULT_SETTINGS."""
        return self._active_keys is None or key in self._active_keys

    def _dir_row(self, parent_layout, label_text: str, attr_name: str, setting_key: str):
        """Add a label + line-edit + Browse row to parent_layout; hide if inactive."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.addWidget(QLabel(label_text))
        edit = QLineEdit(self.settings.get(setting_key, ''))
        setattr(self, attr_name, edit)
        h.addWidget(edit, 1)
        btn = QPushButton("Browse...")
        btn.clicked.connect(lambda checked=False, e=edit: self.browse_dir(e))
        h.addWidget(btn)
        row.setVisible(self._active(setting_key))
        parent_layout.addWidget(row)
        return row

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # --- Directories ---
        dir_group = QGroupBox("Directories")
        dir_vbox = QVBoxLayout(dir_group)
        self._dir_row(dir_vbox, "Blueprints Directory:", 'blueprints_edit', 'blueprints_dir')
        self._dir_row(dir_vbox, "Customer Files Directory:", 'customer_files_edit', 'customer_files_dir')
        dir_group.setVisible(
            self._active('blueprints_dir') or self._active('customer_files_dir')
        )
        scroll_layout.addWidget(dir_group)

        # --- ITAR Directories ---
        itar_group = QGroupBox("ITAR Directories (optional)")
        itar_vbox = QVBoxLayout(itar_group)
        self._dir_row(itar_vbox, "ITAR Blueprints:", 'itar_blueprints_edit', 'itar_blueprints_dir')
        self._dir_row(itar_vbox, "ITAR Customer Files:", 'itar_customer_files_edit', 'itar_customer_files_dir')
        itar_group.setVisible(
            self._active('itar_blueprints_dir') or self._active('itar_customer_files_dir')
        )
        scroll_layout.addWidget(itar_group)

        # --- Link Type ---
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
        if get_os_type() == "windows":
            self.hard_radio.setToolTip("Creates a hard link. Saves disk space. Files must be on same volume.")
            self.symbolic_radio.setToolTip("Creates a symbolic link. Requires admin or Developer Mode.")
            self.copy_radio.setToolTip("Creates independent copy. Use if on different drives.")
        else:
            self.hard_radio.setToolTip("Creates a hard link. Recommended - saves disk space.")
            self.symbolic_radio.setToolTip("Creates a symbolic link.")
            self.copy_radio.setToolTip("Creates an independent copy.")
        link_group.setVisible(self._active('link_type'))
        scroll_layout.addWidget(link_group)

        # --- Blueprint File Types ---
        ext_group = QGroupBox("Blueprint File Types")
        ext_layout = QVBoxLayout(ext_group)
        ext_layout.addWidget(QLabel("Files with these extensions go to blueprints folder:"))
        self.extensions_edit = QLineEdit(
            ', '.join(self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf']))
        )
        ext_layout.addWidget(self.extensions_edit)
        ext_layout.addWidget(QLabel("(comma-separated, e.g., .pdf, .dwg, .dxf)"))
        ext_group.setVisible(self._active('blueprint_extensions'))
        scroll_layout.addWidget(ext_group)

        # --- Options ---
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.allow_duplicates_check = QCheckBox("Allow duplicate job numbers (not recommended)")
        self.allow_duplicates_check.setChecked(self.settings.get('allow_duplicate_jobs', False))
        self.allow_duplicates_check.setVisible(self._active('allow_duplicate_jobs'))
        options_layout.addWidget(self.allow_duplicates_check)

        self.skip_images_check = QCheckBox("Skip image attachments (.jpg, .png, etc.) when extracting emails")
        self.skip_images_check.setChecked(self.settings.get('skip_image_attachments', True))
        self.skip_images_check.setToolTip("Skips inline signature images when extracting email attachments.")
        self.skip_images_check.setVisible(self._active('skip_image_attachments'))
        options_layout.addWidget(self.skip_images_check)

        default_tab_row = QWidget()
        default_tab_h = QHBoxLayout(default_tab_row)
        default_tab_h.setContentsMargins(0, 0, 0, 0)
        default_tab_h.addWidget(QLabel("Default opening tab:"))
        self.default_tab_combo = QComboBox()
        disabled = self.settings.get('disabled_modules', [])
        self._tab_display_names = []
        for module_name, display_name in self.available_modules:
            if module_name not in disabled:
                self.default_tab_combo.addItem(display_name)
                self._tab_display_names.append(display_name)
        if self.default_tab_combo.count() == 0:
            self.default_tab_combo.addItem("(no modules enabled)")
            self.default_tab_combo.setEnabled(False)
        else:
            current_default = self.settings.get('default_tab', '')
            if isinstance(current_default, str) and current_default in self._tab_display_names:
                self.default_tab_combo.setCurrentIndex(self._tab_display_names.index(current_default))
        default_tab_h.addWidget(self.default_tab_combo)
        default_tab_h.addStretch()
        default_tab_row.setVisible(self._active('default_tab'))
        options_layout.addWidget(default_tab_row)

        options_group.setVisible(
            self._active('allow_duplicate_jobs') or
            self._active('skip_image_attachments') or
            self._active('default_tab')
        )
        scroll_layout.addWidget(options_group)

        # --- Modules ---
        if self.available_modules and self._active('disabled_modules'):
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

        # --- Appearance ---
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
        appearance_group.setVisible(self._active('ui_style'))
        scroll_layout.addWidget(appearance_group)

        # --- Remote Sync ---
        remote_group = QGroupBox("Remote Sync")
        remote_layout = QGridLayout(remote_group)
        remote_layout.addWidget(QLabel("Remote Server Path:"), 0, 0)
        self.remote_server_edit = QLineEdit(self.settings.get('remote_server_path', ''))
        self.remote_server_edit.setPlaceholderText(r"\\server\share\jobdocs or /mnt/share/jobdocs")
        remote_layout.addWidget(self.remote_server_edit, 0, 1)
        remote_browse_btn = QPushButton("Browse...")
        remote_browse_btn.clicked.connect(lambda: self.browse_dir(self.remote_server_edit))
        remote_layout.addWidget(remote_browse_btn, 0, 2)
        remote_info = QLabel("Settings and history will sync to/from remote server on startup/shutdown")
        remote_info.setWordWrap(True)
        remote_info.setStyleSheet("color: gray; font-size: 9pt;")
        remote_layout.addWidget(remote_info, 1, 0, 1, 3)
        remote_group.setVisible(self._active('remote_server_path'))
        scroll_layout.addWidget(remote_group)

        # --- Advanced Settings (collapsible) ---
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

        _job_struct_block = QWidget()
        _js_vbox = QVBoxLayout(_job_struct_block)
        _js_vbox.setContentsMargins(0, 0, 0, 0)
        _js_vbox.addWidget(QLabel("Job Folder Structure:"))
        _js_vbox.addWidget(QLabel("Available placeholders: {customer}, {job_folder}, {po_number}"))
        _js_vbox.addWidget(QLabel(f"Default: {path_example}"))
        _js_vbox.addWidget(QLabel(f"Legacy: {legacy_example}"))
        self.job_structure_edit = QLineEdit(
            self.settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')
        )
        _js_vbox.addWidget(self.job_structure_edit)
        _job_struct_block.setVisible(self._active('job_folder_structure'))
        advanced_content_layout.addWidget(_job_struct_block)

        _quote_block = QWidget()
        _q_vbox = QVBoxLayout(_quote_block)
        _q_vbox.setContentsMargins(0, 0, 0, 0)
        _q_vbox.addWidget(QLabel("Quote Folder Path:"))
        self.quote_folder_edit = QLineEdit(self.settings.get('quote_folder_path', 'Quotes'))
        _q_vbox.addWidget(self.quote_folder_edit)
        _quote_block.setVisible(self._active('quote_folder_path'))
        advanced_content_layout.addWidget(_quote_block)

        self.legacy_mode_check = QCheckBox("Enable legacy mode (shows 'Search All Folders' option)")
        self.legacy_mode_check.setChecked(self.settings.get('legacy_mode', True))
        self.legacy_mode_check.setVisible(self._active('legacy_mode'))
        advanced_content_layout.addWidget(self.legacy_mode_check)

        self.experimental_check = QCheckBox("Enable experimental features (Reporting)")
        self.experimental_check.setChecked(self.settings.get('experimental_features', False))
        self.experimental_check.setToolTip("Enables experimental features. Requires restart.")
        self.experimental_check.setVisible(self._active('experimental_features'))
        advanced_content_layout.addWidget(self.experimental_check)

        advanced_layout.addWidget(self.advanced_content)
        self.advanced_content.setVisible(False)
        self.advanced_group.toggled.connect(self.advanced_content.setVisible)

        _any_advanced = any(self._active(k) for k in (
            'job_folder_structure', 'quote_folder_path', 'legacy_mode', 'experimental_features'
        ))
        self.advanced_group.setVisible(_any_advanced)
        scroll_layout.addWidget(self.advanced_group)

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

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
        if self._active('blueprints_dir'):
            self.settings['blueprints_dir'] = self.blueprints_edit.text()
        if self._active('customer_files_dir'):
            self.settings['customer_files_dir'] = self.customer_files_edit.text()
        if self._active('itar_blueprints_dir'):
            self.settings['itar_blueprints_dir'] = self.itar_blueprints_edit.text()
        if self._active('itar_customer_files_dir'):
            self.settings['itar_customer_files_dir'] = self.itar_customer_files_edit.text()

        if self._active('link_type'):
            if self.hard_radio.isChecked():
                self.settings['link_type'] = 'hard'
            elif self.symbolic_radio.isChecked():
                self.settings['link_type'] = 'symbolic'
            else:
                self.settings['link_type'] = 'copy'

        if self._active('blueprint_extensions'):
            extensions = [ext.strip().lower() for ext in self.extensions_edit.text().split(',') if ext.strip()]
            extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
            self.settings['blueprint_extensions'] = extensions

        if self._active('job_folder_structure'):
            self.settings['job_folder_structure'] = self.job_structure_edit.text().strip()
        if self._active('quote_folder_path'):
            self.settings['quote_folder_path'] = self.quote_folder_edit.text().strip()
        if self._active('legacy_mode'):
            self.settings['legacy_mode'] = self.legacy_mode_check.isChecked()
        if self._active('allow_duplicate_jobs'):
            self.settings['allow_duplicate_jobs'] = self.allow_duplicates_check.isChecked()
        if self._active('skip_image_attachments'):
            self.settings['skip_image_attachments'] = self.skip_images_check.isChecked()
        if self._active('ui_style'):
            self.settings['ui_style'] = self.style_combo.currentText()
        if self._active('default_tab'):
            idx = self.default_tab_combo.currentIndex()
            if 0 <= idx < len(self._tab_display_names):
                self.settings['default_tab'] = self._tab_display_names[idx]
        if self._active('experimental_features'):
            self.settings['experimental_features'] = self.experimental_check.isChecked()
        if self._active('disabled_modules'):
            disabled_modules = []
            for module_name, checkbox in self.module_checkboxes.items():
                if not checkbox.isChecked():
                    disabled_modules.append(module_name)
            self.settings['disabled_modules'] = disabled_modules
        if self._active('remote_server_path'):
            self.settings['remote_server_path'] = self.remote_server_edit.text().strip()

        self.accept()
