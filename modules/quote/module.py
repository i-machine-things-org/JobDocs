"""
Quote Module - Create Quote Folders

This module handles creation of quote folders in the customer files directory.
Supports ITAR quotes, file linking, and conversion to jobs.
"""

import os
import sys
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QWidget, QMessageBox, QFileDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6 import uic

from core.base_module import BaseModule
from shared.widgets import DropZone, JobSearchDialog
from shared.utils import (
    is_blueprint_file, parse_job_numbers, create_file_link, sanitize_filename,
    open_folder
)


class QuoteModule(BaseModule):
    """Module for creating quote folders"""

    def __init__(self):
        super().__init__()
        # Instance variables
        self.quote_files: List[str] = []
        # Widget references (set in _create_widget)
        self._widget = None
        self.quote_customer_combo = None
        self.quote_number_edit = None
        self.quote_description_edit = None
        self.quote_drawings_edit = None
        self.quote_itar_check = None
        self.quote_files_list = None
        self.quote_search_input = None
        self.quote_search_results = None
        self.quote_drop_zone = None

    def get_name(self) -> str:
        return "Create Quote"

    def get_order(self) -> int:
        return 10  # First tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the quote tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('quote/ui/quote_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.quote_customer_combo = widget.quote_customer_combo
        self.quote_number_edit = widget.quote_number_edit
        self.quote_description_edit = widget.quote_description_edit
        self.quote_drawings_edit = widget.quote_drawings_edit
        self.quote_itar_check = widget.quote_itar_check
        self.quote_files_list = widget.quote_files_list

        # Replace QFrame placeholder with actual DropZone widget
        placeholder = widget.quote_drop_zone
        parent = placeholder.parent()
        layout = parent.layout()
        index = layout.indexOf(placeholder)
        placeholder.deleteLater()
        self.quote_drop_zone = DropZone("Drop files")
        self.quote_drop_zone.setMinimumHeight(60)
        layout.insertWidget(index, self.quote_drop_zone)

        # Connect signals - use lambda to ensure proper connection
        self.quote_drop_zone.files_dropped.connect(lambda files: self.add_quote_files(files))
        widget.remove_btn.clicked.connect(self.remove_quote_file)
        widget.copy_from_btn.clicked.connect(self.show_copy_from_dialog)
        widget.create_btn.clicked.connect(self.create_quote)
        widget.clear_btn.clicked.connect(self.clear_quote_form)
        widget.open_bp_btn.clicked.connect(self.open_blueprints_folder)
        widget.open_cf_btn.clicked.connect(self.open_customer_files_folder)

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

    def populate_quote_customer_list(self):
        """Populate customer combo box"""
        if self.app_context is None:
            return

        if self.quote_customer_combo is None:
            return

        try:
            customers = self.app_context.get_customer_list()

            self.quote_customer_combo.clear()
            self.quote_customer_combo.addItems(sorted(customers))
            self.app_context.log_message(f"Quote module: Populated {len(customers)} customers")
        except Exception as e:
            self.app_context.log_message(f"Quote module error populating customers: {e}")

    # ==================== File Management ====================

    def add_quote_files(self, files: List[str]):
        """Add files to the quote files list"""
        if self.quote_files_list is None:
            return

        for file in files:
            if file not in self.quote_files:
                self.quote_files.append(file)
                self.quote_files_list.addItem(os.path.basename(file))

    def remove_quote_file(self):
        """Remove selected file from quote files list"""
        row = self.quote_files_list.currentRow()
        if row >= 0:
            self.quote_files_list.takeItem(row)
            del self.quote_files[row]

    def clear_quote_files(self):
        """Clear all files from quote files list"""
        self.quote_files.clear()
        self.quote_files_list.clear()

    # ==================== Quote Creation ====================

    def create_quote(self):
        """Create quote folder(s) from form data"""
        customer = self.quote_customer_combo.currentText().strip()
        quote_numbers_text = self.quote_number_edit.text().strip()
        description = self.quote_description_edit.text().strip()
        drawings_text = self.quote_drawings_edit.text().strip()

        if not customer or not quote_numbers_text or not description:
            self.show_error("Error", "Customer, Quote #, and Description are required")
            return

        is_itar = self.quote_itar_check.isChecked()
        bp_dir, cf_dir = self.app_context.get_directories(is_itar)

        if not bp_dir or not cf_dir:
            self.show_error("Error", "Directories not configured")
            return

        # Parse quote numbers
        quote_numbers = parse_job_numbers(quote_numbers_text)
        if not quote_numbers:
            self.show_error("Error", "Invalid quote number format")
            return

        # Parse drawings
        drawings = [d.strip() for d in drawings_text.split(',') if d.strip()]

        created = 0
        for quote_num in quote_numbers:
            if self.create_single_quote(customer, quote_num, description, drawings, is_itar, self.quote_files):
                created += 1

        if created > 0:
            self.show_info("Success", f"Created {created}/{len(quote_numbers)} quote(s)")
            self.clear_quote_form()
            # Refresh history via main window
            if self.app_context.main_window:
                self.app_context.main_window.refresh_history()
                self.app_context.main_window.populate_customer_lists()
        else:
            self.show_error("Error", "Failed to create quotes")

    def create_single_quote(self, customer: str, quote_number: str, description: str,
                           drawings: List[str], is_itar: bool, files: List[str]) -> bool:
        """Create a single quote folder"""
        try:
            bp_dir, cf_dir = self.app_context.get_directories(is_itar)

            # Build quote folder name
            if drawings:
                quote_dir_name = f"{quote_number}_{description}_{'-'.join(drawings)}"
            else:
                quote_dir_name = f"{quote_number}_{description}"

            quote_dir_name = sanitize_filename(quote_dir_name)

            # Build quote path
            quote_folder_path = self.app_context.get_setting('quote_folder_path', 'Quotes')
            quote_path = Path(cf_dir) / customer / quote_folder_path / quote_dir_name
            quote_path.mkdir(parents=True, exist_ok=True)

            customer_bp = Path(bp_dir) / customer
            customer_bp.mkdir(parents=True, exist_ok=True)

            # Get blueprint extensions
            blueprint_extensions = self.app_context.get_setting('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
            link_type = self.app_context.get_setting('link_type', 'hard')

            # Process files
            for file_path in files:
                file_name = os.path.basename(file_path)

                if is_blueprint_file(file_name, blueprint_extensions):
                    # Copy to blueprints folder
                    bp_dest = customer_bp / file_name
                    try:
                        import shutil
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass

                    # Link to quote folder
                    quote_dest = quote_path / file_name
                    if not quote_dest.exists():
                        create_file_link(bp_dest, quote_dest, link_type)
                else:
                    # Other files go directly to quote folder
                    quote_dest = quote_path / file_name
                    try:
                        import shutil
                        shutil.copy2(file_path, quote_dest)
                    except FileExistsError:
                        pass

            # Link existing drawings from blueprints
            if drawings:
                exts = blueprint_extensions
                available_bps = {}
                try:
                    for bp_file in customer_bp.iterdir():
                        if bp_file.is_file() and bp_file.suffix.lower() in [e.lower() for e in exts]:
                            available_bps[bp_file.name.lower()] = bp_file
                except OSError:
                    pass

                for drawing in drawings:
                    drawing_lower = drawing.lower()
                    for ext in exts:
                        for bp_name, bp_file in available_bps.items():
                            if drawing_lower in bp_name and bp_name.endswith(ext.lower()):
                                dest = quote_path / bp_file.name
                                if not dest.exists():
                                    create_file_link(bp_file, dest, link_type)

            # Add to history
            self.app_context.add_to_history('quote', {
                'customer': customer,
                'quote_number': quote_number,
                'description': description,
                'drawings': drawings,
                'is_itar': is_itar,
                'path': str(quote_path)
            })
            self.app_context.save_history()

            return True

        except Exception as e:
            self.show_error("Error", f"Error creating quote {quote_number}: {e}")
            return False

    def clear_quote_form(self):
        """Clear all form fields"""
        self.quote_customer_combo.setCurrentText("")
        self.quote_number_edit.clear()
        self.quote_description_edit.clear()
        self.quote_drawings_edit.clear()
        self.clear_quote_files()

    # ==================== Quote to Job Conversion ====================

    def convert_current_quote_to_job(self):
        """Convert current quote form data to Create Job tab"""
        customer = self.quote_customer_combo.currentText().strip()
        quote_number = self.quote_number_edit.text().strip()
        description = self.quote_description_edit.text().strip()
        drawings = self.quote_drawings_edit.text().strip()

        if not customer or not quote_number or not description:
            self.show_error("Error", "Please fill in Customer, Quote #, and Description before converting")
            return

        # Get main window reference
        main_window = self.app_context.main_window
        if not main_window:
            self.show_error("Error", "Cannot access main window")
            return

        # Switch to Create Job tab (tab index 1)
        main_window.tabs.setCurrentIndex(1)

        # Populate job fields with quote data
        main_window.customer_combo.setCurrentText(customer)
        main_window.job_number_edit.setText(quote_number)
        main_window.description_edit.setText(description)
        main_window.drawings_edit.setText(drawings)

        # Copy ITAR setting
        main_window.itar_check.setChecked(self.quote_itar_check.isChecked())

        # Copy files
        main_window.job_files = self.quote_files.copy()
        main_window.job_files_list.clear()
        for file in main_window.job_files:
            main_window.job_files_list.addItem(os.path.basename(file))

        self.show_info("Quote Converted", f"Quote {quote_number} data copied to Create Job tab.\n\nYou can now create the job from this quote.")

    # ==================== Search & Copy Functions ====================

    def show_copy_from_dialog(self):
        """Show popup dialog to search and copy from existing job/quote"""
        dialog = JobSearchDialog(self.get_widget(), self.app_context, "jobs/quotes")

        if dialog.exec():
            folder_path = dialog.get_selected_folder()
            if folder_path and os.path.exists(folder_path):
                self._copy_info_from_folder(folder_path)

    def _copy_info_from_folder(self, folder_path: str):
        """Copy job/quote info from folder to form"""
        # Parse folder name (format: quote#_description_drawings or quote#_description)
        folder_name = os.path.basename(folder_path)
        parts = folder_name.split('_', 2)

        if len(parts) >= 2:
            quote_number = parts[0]
            description = parts[1]
            drawings = parts[2] if len(parts) > 2 else ""

            # Get customer name (parent folder or grandparent if in Quotes subfolder)
            parent = os.path.dirname(folder_path)
            customer = os.path.basename(parent)
            quote_folder_path = self.app_context.get_setting('quote_folder_path', 'Quotes')
            if customer.lower() == 'quotes' or customer.lower() == quote_folder_path.lower():
                customer = os.path.basename(os.path.dirname(parent))

            # Populate form
            self.quote_customer_combo.setCurrentText(customer)
            self.quote_number_edit.setText(quote_number)
            self.quote_description_edit.setText(description)
            self.quote_drawings_edit.setText(drawings)

    # ==================== Folder Operations ====================

    def open_blueprints_folder(self):
        """Open blueprints directory"""
        bp_dir = self.app_context.get_setting('blueprints_dir', '')
        if bp_dir and os.path.exists(bp_dir):
            success, error = open_folder(bp_dir)
            if not success:
                self.show_error("Error", error)
        else:
            self.show_error("Warning", "Blueprints directory not configured")

    def open_customer_files_folder(self):
        """Open customer files directory"""
        cf_dir = self.app_context.get_setting('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            success, error = open_folder(cf_dir)
            if not success:
                self.show_error("Error", error)
        else:
            self.show_error("Warning", "Customer files directory not configured")

    def cleanup(self):
        """Cleanup resources"""
        self.quote_files.clear()
