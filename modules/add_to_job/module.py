"""
Add to Job Module - Add Files to Existing Jobs

This module handles adding files to existing job folders.
Supports filtering by ITAR status and flexible destination options.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QTreeWidgetItem, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6 import uic

from core.base_module import BaseModule
from shared.widgets import DropZone
from shared.utils import create_file_link


class AddToJobModule(BaseModule):
    """Module for adding files to existing jobs"""

    def __init__(self):
        super().__init__()
        self.add_files: List[str] = []
        self._widget = None
        # Widget references
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
        return "Add to Job"

    def get_order(self) -> int:
        return 30  # Third tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the add to job tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('add_to_job/ui/add_to_job_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
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

        # Replace DropZone placeholder
        placeholder = widget.add_drop_zone
        parent = placeholder.parent()
        layout = parent.layout()
        index = layout.indexOf(placeholder)
        placeholder.deleteLater()
        self.add_drop_zone = DropZone("Drop files")
        self.add_drop_zone.setMinimumHeight(60)
        layout.insertWidget(index, self.add_drop_zone)

        # Set splitter sizes
        widget.mainSplitter.setSizes([450, 450])

        # Connect signals
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

    def populate_add_customer_list(self):
        """Populate customer combo box"""
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

    # ==================== Job Tree Management ====================

    def refresh_job_tree(self):
        """Refresh the job tree with current filter settings"""
        print(f"\n[refresh_job_tree] === START ===", flush=True)
        self.job_tree.clear()

        selected_customer = self.add_customer_combo.currentText()
        show_all_customers = selected_customer == "(All Customers)" or not selected_customer
        print(f"[refresh_job_tree] Selected customer: '{selected_customer}'", flush=True)
        print(f"[refresh_job_tree] Show all customers: {show_all_customers}", flush=True)

        # Get directories based on filter selection
        dirs_to_search = []

        if self.add_all_radio.isChecked():
            print(f"[refresh_job_tree] Filter: All", flush=True)
            dirs_to_search = self._get_customer_files_dirs()
        elif self.add_standard_radio.isChecked():
            print(f"[refresh_job_tree] Filter: Standard only", flush=True)
            cf_dir = self.app_context.get_setting('customer_files_dir', '')
            if cf_dir and os.path.exists(cf_dir):
                dirs_to_search.append(('', cf_dir))
        else:  # ITAR only
            print(f"[refresh_job_tree] Filter: ITAR only", flush=True)
            itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
            if itar_cf_dir and os.path.exists(itar_cf_dir):
                dirs_to_search.append(('ITAR', itar_cf_dir))

        print(f"[refresh_job_tree] Dirs to search: {len(dirs_to_search)}", flush=True)

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

                    jobs = self.app_context.find_job_folders(customer_path)
                    print(f"[AddToJob] Customer: {customer}, Found {len(jobs)} jobs", flush=True)
                    for job_name, job_docs_path in jobs:
                        print(f"  Job: {job_name} -> {job_docs_path}", flush=True)

                    for job_name, job_docs_path in sorted(jobs):
                        job_item = QTreeWidgetItem([job_name])
                        job_item.setData(0, Qt.ItemDataRole.UserRole, job_docs_path)
                        customer_item.addChild(job_item)
                        print(f"[refresh_job_tree]     Added job to tree: {job_name}", flush=True)

                    if customer_item.childCount() > 0:
                        print(f"[refresh_job_tree]   Adding customer '{display_name}' to tree with {customer_item.childCount()} jobs", flush=True)
                        self.job_tree.addTopLevelItem(customer_item)
                    else:
                        print(f"[refresh_job_tree]   Skipping customer '{display_name}' (no jobs)", flush=True)

            except OSError as e:
                print(f"[refresh_job_tree] OSError in main loop: {e}", flush=True)

        print(f"[refresh_job_tree] === END === Total items in tree: {self.job_tree.topLevelItemCount()}\n", flush=True)

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

    # ==================== File Management ====================

    def handle_add_files(self, files: List[str]):
        """Add files to the add files list"""
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

    # ==================== Add Files to Job ====================

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

    def cleanup(self):
        """Cleanup resources"""
        self.add_files.clear()
