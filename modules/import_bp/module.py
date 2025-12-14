"""
Import Module - Import Blueprint Files to Customer Folders

This module handles importing blueprint files into customer blueprint directories.
Supports both regular and ITAR blueprint directories.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6 import uic

from core.base_module import BaseModule
from shared.widgets import DropZone


class ImportModule(BaseModule):
    """Module for importing blueprints to customer folders"""

    def __init__(self):
        super().__init__()
        self._widget = None
        self.import_files: List[str] = []
        # Widget references
        self.import_customer_combo = None
        self.import_itar_check = None
        self.import_files_list = None
        self.import_log = None
        self.import_drop_zone = None

    def get_name(self) -> str:
        return "Import Blueprints"

    def get_order(self) -> int:
        return 60  # Sixth tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the import tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('import_bp/ui/import_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.import_customer_combo = widget.import_customer_combo
        self.import_itar_check = widget.import_itar_check
        self.import_files_list = widget.import_files_list
        self.import_log = widget.import_log

        # Replace DropZone placeholder
        placeholder = widget.import_drop_zone
        parent = placeholder.parent()
        layout = parent.layout()
        index = layout.indexOf(placeholder)
        placeholder.deleteLater()
        self.import_drop_zone = DropZone("Drop blueprint files here")
        self.import_drop_zone.setMinimumHeight(100)
        layout.insertWidget(index, self.import_drop_zone)

        # Connect signals
        self.import_drop_zone.files_dropped.connect(self.handle_import_files)
        widget.clear_btn.clicked.connect(self.clear_import_list)
        widget.import_btn.clicked.connect(self.check_and_import)

        # Customer list will be populated by main window after all modules load

        return widget

    def _get_ui_path(self, relative_path: str) -> Path:
        """Get path to UI file"""
        if getattr(sys, 'frozen', False):
            application_path = Path(sys._MEIPASS)
        else:
            application_path = Path(__file__).parent.parent.parent

        ui_file = application_path / 'modules' / relative_path
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")
        return ui_file

    # ==================== File Management ====================

    def handle_import_files(self, files: List[str]):
        """Add files to import list"""
        for f in files:
            if f not in self.import_files:
                self.import_files.append(f)
                self.import_files_list.addItem(os.path.basename(f))

    def clear_import_list(self):
        """Clear import file list"""
        self.import_files.clear()
        self.import_files_list.clear()

    # ==================== Customer List ====================

    def populate_import_customer_list(self):
        """Populate customer combo box"""
        customers = self.app_context.get_customer_list()
        self.import_customer_combo.clear()
        self.import_customer_combo.addItems(sorted(customers))
        self.import_customer_combo.setEditable(True)

    # ==================== Import Functionality ====================

    def check_and_import(self):
        """Import files to customer blueprint folder"""
        customer = self.import_customer_combo.currentText().strip()
        if not customer:
            self.show_error("Error", "Please enter a customer name")
            return

        if not self.import_files:
            self.show_error("Error", "Please add files to import")
            return

        # Check if ITAR is selected
        is_itar = self.import_itar_check.isChecked()
        bp_dir = self.app_context.get_setting(
            'itar_blueprints_dir' if is_itar else 'blueprints_dir', ''
        )

        if not bp_dir:
            dir_type = "ITAR blueprints" if is_itar else "Blueprints"
            self.show_error("Error", f"{dir_type} directory not configured")
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
        self.show_info("Complete", f"Imported: {imported}, Skipped: {skipped}")

        # Refresh customer lists if new customer was added
        if self.app_context.main_window:
            self.app_context.main_window.populate_customer_lists()

    def cleanup(self):
        """Cleanup resources"""
        self.import_files.clear()
