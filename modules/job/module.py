"""
Job Module - Create Job Folders and Add Files to Existing Jobs

This module handles:
- Creation of new job folders in the customer files directory
- Adding files to existing job folders
- ITAR job support, file linking, and duplicate detection
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List, Type
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QTreeWidgetItem, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6 import uic
from datetime import datetime

from core.base_module import BaseModule
from shared.widgets import DropZone, JobSearchDialog
from shared.utils import (
    is_blueprint_file, parse_job_numbers, create_file_link,
    sanitize_filename, open_folder, get_next_number
)


class JobTreeWorker(QThread):
    """Background worker for loading job tree data"""

    # Signal emitted when a customer with jobs is found
    customer_loaded = pyqtSignal(str, str, list)  # (display_name, customer_path, jobs_list)
    # Signal emitted when loading is complete
    finished = pyqtSignal()

    def __init__(self, dirs_to_search, selected_customer, show_all_customers, app_context):
        super().__init__()
        self.dirs_to_search = dirs_to_search
        self.selected_customer = selected_customer
        self.show_all_customers = show_all_customers
        self.app_context = app_context
        self._is_cancelled = False

    def cancel(self):
        """Cancel the worker"""
        self._is_cancelled = True

    def run(self):
        """Run the background job loading"""
        for prefix, cf_dir in self.dirs_to_search:
            if self._is_cancelled:
                break

            try:
                if self.show_all_customers:
                    customers = [d for d in os.listdir(cf_dir) if os.path.isdir(os.path.join(cf_dir, d))]
                else:
                    customers = [self.selected_customer] if os.path.isdir(os.path.join(cf_dir, self.selected_customer)) else []

                for customer in sorted(customers):
                    if self._is_cancelled:
                        break

                    customer_path = os.path.join(cf_dir, customer)
                    if not os.path.exists(customer_path):
                        continue

                    display_name = f"[{prefix}] {customer}" if prefix else customer
                    jobs = self.app_context.find_job_folders(customer_path)

                    # Only emit if customer has jobs
                    if jobs:
                        self.customer_loaded.emit(display_name, customer_path, jobs)

            except OSError as e:
                print(f"[JobTreeWorker] OSError: {e}", flush=True)

        self.finished.emit()


class JobModule(BaseModule):
    """Module for creating and managing job folders"""

    def __init__(self):
        super().__init__()
        # File lists
        self.job_files: List[str] = []  # For "Create New" tab
        self.add_files: List[str] = []  # For "Add to Existing" tab
        self._widget = None
        self._worker = None  # Background thread worker

        # Create New tab widget references
        self.customer_combo = None
        self.job_number_edit = None
        self.po_number_edit = None
        self.job_status_label = None
        self.description_edit = None
        self.drawings_edit = None
        self.itar_check = None
        self.job_files_list = None
        self.job_drop_zone = None

        # Add to Existing tab widget references
        self.add_customer_combo = None
        self.add_search_edit = None
        self.job_tree = None
        self.selected_job_label = None
        self.add_files_list = None
        self.add_status_label = None
        self.add_all_radio = None
        self.add_standard_radio = None
        self.add_itar_radio = None
        self.dest_both_radio = None
        self.dest_blueprints_radio = None
        self.dest_job_radio = None
        self.add_drop_zone = None
        self.add_filter_group = None
        self.dest_button_group = None

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
        """Create the job tab widget with both Create and Add tabs"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('job/ui/job_tab.ui')
        uic.loadUi(ui_file, widget)

        # ===== Setup "Create New" Tab =====
        self.customer_combo = widget.customer_combo
        self.job_number_edit = widget.job_number_edit
        self.po_number_edit = widget.po_number_edit
        self.job_status_label = widget.job_status_label
        self.description_edit = widget.description_edit
        self.drawings_edit = widget.drawings_edit
        self.itar_check = widget.itar_check
        self.job_files_list = widget.job_files_list

        # Replace DropZone placeholder for Create tab
        placeholder = widget.job_drop_zone
        parent = placeholder.parent()
        layout = parent.layout()
        index = layout.indexOf(placeholder)
        placeholder.deleteLater()
        self.job_drop_zone = DropZone("Drop files")
        self.job_drop_zone.setMinimumHeight(60)
        layout.insertWidget(index, self.job_drop_zone)

        # Connect Create New tab signals
        self.job_drop_zone.files_dropped.connect(lambda files: self.handle_job_files(files))
        widget.remove_btn.clicked.connect(self.remove_job_file)
        widget.copy_from_btn.clicked.connect(self.show_copy_from_dialog)
        widget.create_btn.clicked.connect(self.create_job)
        widget.clear_btn.clicked.connect(self.clear_job_form)
        widget.auto_gen_job_btn.clicked.connect(self.auto_generate_job_number)
        widget.open_bp_btn.clicked.connect(self.open_blueprints_folder)
        widget.open_cf_btn.clicked.connect(self.open_customer_files_folder)

        # ===== Setup "Add to Existing" Tab =====
        self.add_customer_combo = widget.add_customer_combo
        self.add_search_edit = widget.add_search_edit
        self.job_tree = widget.job_tree
        self.selected_job_label = widget.selected_job_label
        self.add_files_list = widget.add_files_list
        self.add_status_label = widget.add_status_label

        # Store radio button references
        self.add_all_radio = widget.add_all_radio
        self.add_standard_radio = widget.add_standard_radio
        self.add_itar_radio = widget.add_itar_radio
        self.dest_both_radio = widget.dest_both_radio
        self.dest_blueprints_radio = widget.dest_blueprints_radio
        self.dest_job_radio = widget.dest_job_radio

        # Create button groups
        self.add_filter_group = QButtonGroup(widget)
        self.add_filter_group.addButton(self.add_all_radio)
        self.add_filter_group.addButton(self.add_standard_radio)
        self.add_filter_group.addButton(self.add_itar_radio)

        self.dest_button_group = QButtonGroup(widget)
        self.dest_button_group.addButton(self.dest_both_radio)
        self.dest_button_group.addButton(self.dest_blueprints_radio)
        self.dest_button_group.addButton(self.dest_job_radio)

        # Replace DropZone placeholder for Add tab
        add_placeholder = widget.add_drop_zone
        add_parent = add_placeholder.parent()
        add_layout = add_parent.layout()
        add_index = add_layout.indexOf(add_placeholder)
        add_placeholder.deleteLater()
        self.add_drop_zone = DropZone("Drop files")
        self.add_drop_zone.setMinimumHeight(60)
        add_layout.insertWidget(add_index, self.add_drop_zone)

        # Set splitter sizes for Add tab
        widget.addSplitter.setSizes([450, 450])

        # Connect Add to Existing tab signals
        self.add_customer_combo.currentTextChanged.connect(self.refresh_job_tree)
        self.add_all_radio.toggled.connect(self.refresh_job_tree)
        self.add_standard_radio.toggled.connect(self.refresh_job_tree)
        self.add_itar_radio.toggled.connect(self.refresh_job_tree)
        self.add_search_edit.returnPressed.connect(self.search_jobs)
        widget.search_btn.clicked.connect(self.search_jobs)
        widget.clear_search_btn.clicked.connect(self.clear_job_search)
        self.job_tree.itemSelectionChanged.connect(self.on_job_tree_select)
        self.add_drop_zone.files_dropped.connect(lambda files: self.handle_add_files(files))
        widget.remove_add_btn.clicked.connect(self.remove_add_file)
        widget.clear_add_btn.clicked.connect(self.clear_add_files)
        widget.add_files_btn.clicked.connect(self.add_files_to_job)

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
        """Populate customer combo box for Create New tab"""
        customers = self.app_context.get_customer_list()
        self.customer_combo.clear()
        self.customer_combo.addItems(sorted(customers))

    def populate_add_customer_list(self):
        """Populate customer combo box for Add to Existing tab"""
        customers = set()
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            dir_path = self.app_context.get_setting(dir_key, '')
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

    # ==================== Create New Tab: File Management ====================

    def handle_job_files(self, files: List[str]):
        """Add files to the job files list (Create New tab)"""
        for f in files:
            if f not in self.job_files:
                self.job_files.append(f)
                self.job_files_list.addItem(os.path.basename(f))

    def remove_job_file(self):
        """Remove selected file from job files list (Create New tab)"""
        row = self.job_files_list.currentRow()
        if row >= 0:
            self.job_files_list.takeItem(row)
            del self.job_files[row]

    # ==================== Create New Tab: Job Creation ====================

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
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass

                    job_dest = job_path / file_name
                    if not job_dest.exists():
                        create_file_link(bp_dest, job_dest, link_type)
                else:
                    job_dest = job_path / file_name
                    try:
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
        """Clear all form fields (Create New tab)"""
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

    # ==================== Create New Tab: Search & Copy Functions ====================

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

    # ==================== Add to Existing Tab: Job Tree Management ====================

    def refresh_job_tree(self):
        """Refresh the job tree with current filter settings (async with background thread)"""
        # Cancel any existing worker
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self.job_tree.clear()
        self.add_status_label.setText("Loading jobs...")

        selected_customer = self.add_customer_combo.currentText()
        show_all_customers = selected_customer == "(All Customers)" or not selected_customer

        # Get directories based on filter selection
        dirs_to_search = []

        if self.add_all_radio.isChecked():
            dirs_to_search = self._get_customer_files_dirs()
        elif self.add_standard_radio.isChecked():
            cf_dir = self.app_context.get_setting('customer_files_dir', '')
            if cf_dir and os.path.exists(cf_dir):
                dirs_to_search.append(('', cf_dir))
        else:  # ITAR only
            itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
            if itar_cf_dir and os.path.exists(itar_cf_dir):
                dirs_to_search.append(('ITAR', itar_cf_dir))

        # Start background worker
        self._worker = JobTreeWorker(dirs_to_search, selected_customer, show_all_customers, self.app_context)
        self._worker.customer_loaded.connect(self._on_customer_loaded)
        self._worker.finished.connect(self._on_loading_finished)
        self._worker.start()

    def _on_customer_loaded(self, display_name: str, customer_path: str, jobs: list):
        """Slot called when a customer with jobs is loaded"""
        customer_item = QTreeWidgetItem([display_name])
        customer_item.setData(0, Qt.ItemDataRole.UserRole, customer_path)

        for job_name, job_docs_path in sorted(jobs):
            job_item = QTreeWidgetItem([job_name])
            job_item.setData(0, Qt.ItemDataRole.UserRole, job_docs_path)
            customer_item.addChild(job_item)

        self.job_tree.addTopLevelItem(customer_item)

    def _on_loading_finished(self):
        """Slot called when loading is complete"""
        total_items = self.job_tree.topLevelItemCount()
        self.add_status_label.setText(f"Loaded {total_items} customer(s) with jobs")

    def search_jobs(self):
        """Search for jobs matching the search term"""
        search_term = self.add_search_edit.text().strip().lower()

        if not search_term:
            self.refresh_job_tree()
            return

        self.job_tree.clear()
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
                    jobs = self.app_context.find_job_folders(customer_path)
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
        """Clear search and refresh tree"""
        self.add_search_edit.clear()
        self.refresh_job_tree()

    def on_job_tree_select(self):
        """Update label when job tree selection changes"""
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

    def _get_customer_files_dirs(self):
        """Get list of (prefix, path) tuples for customer file directories"""
        dirs = []
        cf_dir = self.app_context.get_setting('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs.append(('', cf_dir))
        itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            dirs.append(('ITAR', itar_cf_dir))
        return dirs

    # ==================== Add to Existing Tab: File Management ====================

    def handle_add_files(self, files: List[str]):
        """Add files to the add files list (Add to Existing tab)"""
        for f in files:
            if f not in self.add_files:
                self.add_files.append(f)
                self.add_files_list.addItem(os.path.basename(f))

    def remove_add_file(self):
        """Remove selected file from add files list"""
        row = self.add_files_list.currentRow()
        if row >= 0:
            self.add_files_list.takeItem(row)
            del self.add_files[row]

    def clear_add_files(self):
        """Clear all files from add files list"""
        self.add_files.clear()
        self.add_files_list.clear()

    # ==================== Add to Existing Tab: Add Files to Job ====================

    def add_files_to_job(self):
        """Add files to the selected job"""
        items = self.job_tree.selectedItems()
        if not items:
            self.show_error("No Selection", "Please select a job folder")
            return

        item = items[0]
        if not item.parent():
            self.show_error("Invalid Selection", "Please select a job, not a customer")
            return

        if not self.add_files:
            self.show_error("No Files", "Please add files")
            return

        job_path = item.data(0, Qt.ItemDataRole.UserRole)
        job_name = item.text(0)

        customer_text = item.parent().text(0)
        if customer_text.startswith('[ITAR] '):
            customer = customer_text[7:]
            is_itar = True
        else:
            customer = customer_text
            itar_cf = self.app_context.get_setting('itar_customer_files_dir', '')
            is_itar = itar_cf and job_path.startswith(itar_cf)

        bp_dir, _ = self.app_context.get_directories(is_itar)
        if not bp_dir:
            self.show_error("Error", "Blueprints directory not configured")
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

        link_type = self.app_context.get_setting('link_type', 'hard')

        for file_path in self.add_files:
            file_name = os.path.basename(file_path)

            try:
                if dest == 'blueprints':
                    bp_dest = customer_bp / file_name
                    try:
                        shutil.copy2(file_path, bp_dest)
                        added += 1
                    except FileExistsError:
                        skipped += 1

                elif dest == 'job':
                    job_dest = Path(job_path) / file_name
                    try:
                        shutil.copy2(file_path, job_dest)
                        added += 1
                    except FileExistsError:
                        skipped += 1

                else:  # both
                    bp_dest = customer_bp / file_name
                    try:
                        shutil.copy2(file_path, bp_dest)
                    except FileExistsError:
                        pass

                    job_dest = Path(job_path) / file_name
                    if not job_dest.exists():
                        create_file_link(bp_dest, job_dest, link_type)
                        added += 1
                    else:
                        skipped += 1

            except Exception as e:
                self.log_message(f"Error adding {file_name}: {e}")
                skipped += 1

        self.add_status_label.setText(f"Added: {added}, Skipped: {skipped}")

        if added > 0:
            self.show_info("Files Added", f"Added {added} file(s) to {job_name}")
            self.clear_add_files()

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
        # Stop any running worker thread
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self.job_files.clear()
        self.add_files.clear()
