"""
Job Module - Create Job Folders

This module handles creation of job folders in the customer files directory.
Supports ITAR jobs, file linking, and duplicate detection.
"""

import os
import sys
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6 import uic
from datetime import datetime

from core.base_module import BaseModule
from shared.widgets import DropZone, JobSearchDialog
from shared.utils import (
    is_blueprint_file, parse_job_numbers, create_file_link,
    sanitize_filename, open_folder, get_next_number
)


class JobModule(BaseModule):
    """Module for creating job folders"""

    def __init__(self):
        super().__init__()
        self.job_files: List[str] = []
        self._widget = None
        # Widget references
        self.customer_combo = None
        self.job_number_edit = None
        self.po_number_edit = None
        self.job_status_label = None
        self.description_edit = None
        self.drawings_edit = None
        self.itar_check = None
        self.job_files_list = None
        self.job_search_input = None
        self.job_search_results = None
        self.job_drop_zone = None

    def get_name(self) -> str:
        return "Create Job Folder"

    def get_order(self) -> int:
        return 20  # Second tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the job tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('job/ui/job_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.customer_combo = widget.customer_combo
        self.job_number_edit = widget.job_number_edit
        self.po_number_edit = widget.po_number_edit
        self.job_status_label = widget.job_status_label
        self.description_edit = widget.description_edit
        self.drawings_edit = widget.drawings_edit
        self.itar_check = widget.itar_check
        self.job_files_list = widget.job_files_list

        # Replace DropZone placeholder
        placeholder = widget.job_drop_zone
        parent = placeholder.parent()
        layout = parent.layout()
        index = layout.indexOf(placeholder)
        placeholder.deleteLater()
        self.job_drop_zone = DropZone("Drop files")
        self.job_drop_zone.setMinimumHeight(60)
        layout.insertWidget(index, self.job_drop_zone)

        # Customer list will be populated by main window after all modules load

        # Connect signals - use lambda to ensure proper connection
        self.job_drop_zone.files_dropped.connect(lambda files: self.handle_job_files(files))
        widget.remove_btn.clicked.connect(self.remove_job_file)
        widget.copy_from_btn.clicked.connect(self.show_copy_from_dialog)
        widget.create_btn.clicked.connect(self.create_job)
        widget.clear_btn.clicked.connect(self.clear_job_form)
        widget.auto_gen_job_btn.clicked.connect(self.auto_generate_job_number)
        widget.open_bp_btn.clicked.connect(self.open_blueprints_folder)
        widget.open_cf_btn.clicked.connect(self.open_customer_files_folder)

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

    def populate_job_customer_list(self):
        """Populate customer combo box"""
        customers = self.app_context.get_customer_list()
        self.customer_combo.clear()
        self.customer_combo.addItems(sorted(customers))

    # ==================== File Management ====================

    def handle_job_files(self, files: List[str]):
        """Add files to the job files list"""
        for f in files:
            if f not in self.job_files:
                self.job_files.append(f)
                self.job_files_list.addItem(os.path.basename(f))

    def remove_job_file(self):
        """Remove selected file from job files list"""
        row = self.job_files_list.currentRow()
        if row >= 0:
            self.job_files_list.takeItem(row)
            del self.job_files[row]

    # ==================== Job Creation ====================

    def create_job(self):
        """Create job folder(s) from form data"""
        customer = self.customer_combo.currentText().strip()
        job_input = self.job_number_edit.text().strip()
        po_number = self.po_number_edit.text().strip()
        description = self.description_edit.text().strip()
        drawings_str = self.drawings_edit.text().strip()
        is_itar = self.itar_check.isChecked()

        if not all([customer, job_input, description]):
            self.show_error("Error", "Please fill in customer, job number, and description")
            return

        bp_dir, cf_dir = self.app_context.get_directories(is_itar)

        if is_itar and (not bp_dir or not cf_dir):
            self.show_error("Error", "ITAR directories not configured in Settings")
            return

        if not bp_dir or not cf_dir:
            self.show_error("Error", "Please configure directories in Settings")
            return

        drawings = [d.strip() for d in drawings_str.split(',') if d.strip()] if drawings_str else []
        job_numbers = parse_job_numbers(job_input)

        if not job_numbers:
            self.show_error("Error", "Invalid job number format")
            return

        # Check for duplicate job numbers
        duplicates = []
        for job_num in job_numbers:
            is_dup, dup_path = self._check_duplicate_job(customer, job_num)
            if is_dup:
                duplicates.append(f"Job #{job_num} already exists at: {dup_path}")

        if duplicates:
            dup_msg = "\n".join(duplicates)
            self.show_error("Duplicate Job Numbers", f"The following job numbers already exist:\n\n{dup_msg}")
            return

        self.log_message(f"Creating job(s): {', '.join(job_numbers)}")

        # Track if this is a new customer
        existing_customers = self.app_context.get_customer_list()
        is_new_customer = customer not in existing_customers

        created = 0
        for job_num in job_numbers:
            if self.create_single_job(customer, job_num, po_number, description, drawings, is_itar, self.job_files):
                created += 1

        if created > 0:
            self.show_info("Success", f"Created {created}/{len(job_numbers)} job(s)")
            self.job_files.clear()
            self.job_files_list.clear()

            # Refresh history via main window
            if self.app_context.main_window:
                self.app_context.main_window.refresh_history()
                if is_new_customer:
                    self.app_context.main_window.populate_customer_lists()
        else:
            self.show_error("Error", "Failed to create jobs")

    def create_single_job(self, customer: str, job_number: str, po_number: str, description: str,
                         drawings: List[str], is_itar: bool, files: List[str]) -> bool:
        """Create a single job folder"""
        try:
            bp_dir, cf_dir = self.app_context.get_directories(is_itar)

            # Build job folder name with description and drawings
            if drawings:
                job_dir_name = f"{job_number}_{description}_{'-'.join(drawings)}"
            else:
                job_dir_name = f"{job_number}_{description}"

            job_dir_name = sanitize_filename(job_dir_name)

            # Build job path using configured structure
            job_path = self.app_context.build_job_path(cf_dir, customer, job_dir_name, po_number)
            job_path.mkdir(parents=True, exist_ok=True)

            customer_bp = Path(bp_dir) / customer
            customer_bp.mkdir(parents=True, exist_ok=True)

            # Get settings
            blueprint_extensions = self.app_context.get_setting('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
            link_type = self.app_context.get_setting('link_type', 'hard')

            # Process files
            for file_path in files:
                file_name = os.path.basename(file_path)

                if is_blueprint_file(file_name, blueprint_extensions):
                    bp_dest = customer_bp / file_name
                    try:
                        import shutil
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass

                    job_dest = job_path / file_name
                    if not job_dest.exists():
                        create_file_link(bp_dest, job_dest, link_type)
                else:
                    job_dest = job_path / file_name
                    try:
                        import shutil
                        shutil.copy2(file_path, job_dest)
                    except FileExistsError:
                        pass

            # Link existing drawings
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
                                dest = job_path / bp_file.name
                                if not dest.exists():
                                    create_file_link(bp_file, dest, link_type)

            # Add to history
            self.app_context.add_to_history('job', {
                'date': datetime.now().isoformat(),
                'customer': customer,
                'job_number': job_number,
                'po_number': po_number,
                'description': description,
                'drawings': drawings,
                'path': str(job_path)
            })
            self.app_context.save_history()

            self.log_message(f"Created: {job_path}")
            return True

        except Exception as e:
            self.log_message(f"Error: {e}")
            self.show_error("Error", f"Error creating job {job_number}: {e}")
            return False

    def _check_duplicate_job(self, customer: str, job_number: str):
        """Check if a job number already exists"""
        job_number_lower = job_number.lower()

        # Check history first
        recent_jobs = self.app_context.history.get('recent_jobs', [])
        for job in recent_jobs:
            if job.get('job_number', '').lower() == job_number_lower:
                existing_customer = job.get('customer', 'Unknown')
                return True, f"{existing_customer}: {job.get('path', 'Unknown')}"

        # Check file system
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            cf_dir = self.app_context.get_setting(dir_key, '')
            if not cf_dir or not os.path.exists(cf_dir):
                continue

            try:
                for customer_dir in os.listdir(cf_dir):
                    customer_path = os.path.join(cf_dir, customer_dir)
                    if not os.path.isdir(customer_path):
                        continue

                    jobs = self.app_context.find_job_folders(customer_path)
                    for job_name, job_docs_path in jobs:
                        parts = job_name.split('_', 1)
                        if parts and parts[0].lower() == job_number_lower:
                            return True, f"{customer_dir}: {job_name}"
            except OSError:
                pass

        return False, None

    def clear_job_form(self):
        """Clear all form fields"""
        self.customer_combo.setCurrentText("")
        self.job_number_edit.clear()
        self.po_number_edit.clear()
        self.description_edit.clear()
        self.drawings_edit.clear()
        self.itar_check.setChecked(False)
        self.job_files.clear()
        self.job_files_list.clear()

    def auto_generate_job_number(self):
        """Auto-generate the next job number"""
        next_number = get_next_number(self.app_context.history, 'job', start_number=10000)
        self.job_number_edit.setText(next_number)
        self.log_message(f"Auto-generated job number: {next_number}")

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
        folder_name = os.path.basename(folder_path)
        parts = folder_name.split('_', 2)

        if len(parts) >= 2:
            job_number = parts[0]
            description = parts[1]
            drawings = parts[2] if len(parts) > 2 else ""

            # Get customer name from parent directory
            parent = os.path.dirname(folder_path)
            customer = os.path.basename(parent)

            # Check if parent is "Quotes" or similar subfolder
            quote_folder_path = self.app_context.get_setting('quote_folder_path', 'Quotes')
            if customer.lower() == 'quotes' or customer.lower() == quote_folder_path.lower():
                customer = os.path.basename(os.path.dirname(parent))

            self.customer_combo.setCurrentText(customer)
            self.job_number_edit.setText(job_number)
            self.description_edit.setText(description)
            self.drawings_edit.setText(drawings)

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
        self.job_files.clear()
