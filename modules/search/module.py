"""
Search Module - Search for Jobs Across Customer Directories

This module provides powerful search functionality across all job folders.
Supports both strict format (fast) and legacy recursive search modes.
Uses background threading to prevent UI lockup during searches.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QTableWidgetItem, QApplication, QMenu,
    QListWidgetItem, QListWidget, QSplitter, QGroupBox, QVBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6 import uic

from core.base_module import BaseModule
from shared.utils import open_folder


class SearchWorker(QThread):
    """Background worker for performing searches without blocking UI"""

    # Signals
    result_found = pyqtSignal(dict)  # Emitted for each search result
    progress_update = pyqtSignal(str)  # Emitted with status updates
    finished = pyqtSignal(int)  # Emitted when search completes with result count

    def __init__(self, dirs_to_search, search_term, strict_mode,
                 search_customer, search_job, search_desc, search_drawing, app_context):
        super().__init__()
        self.dirs_to_search = dirs_to_search
        self.search_term = search_term
        self.strict_mode = strict_mode
        self.search_customer = search_customer
        self.search_job = search_job
        self.search_desc = search_desc
        self.search_drawing = search_drawing
        self.app_context = app_context
        self._is_cancelled = False
        self.result_count = 0

    def cancel(self):
        """Cancel the search"""
        self._is_cancelled = True

    def run(self):
        """Run the search in background"""
        try:
            if self.strict_mode:
                self._strict_search()
            else:
                self._legacy_search()
        except Exception as e:
            self.progress_update.emit(f"Error: {e}")

        self.finished.emit(self.result_count)

    def _strict_search(self):
        """Structured search using parsed folder names"""
        for prefix, base_dir in self.dirs_to_search:
            if self._is_cancelled:
                break

            self.progress_update.emit(f"Searching {prefix if prefix else 'standard'} directories...")

            # BP and IR dirs use filename search, not job folder structure
            if prefix in ('BP', 'ITAR-BP', 'IR'):
                self._file_search(base_dir, prefix)
                continue

            try:
                customers = [d for d in os.listdir(base_dir)
                           if os.path.isdir(os.path.join(base_dir, d))]
            except OSError:
                continue

            for customer in customers:
                if self._is_cancelled:
                    break

                customer_path = os.path.join(base_dir, customer)
                display_customer = f"[ITAR] {customer}" if prefix == 'ITAR' else customer

                # Check if searching by customer name
                customer_match = self.search_customer and self.search_term in customer.lower()

                # Find job folders
                jobs = self.app_context.find_job_folders(customer_path)

                for dir_name, job_docs_path in jobs:
                    if self._is_cancelled:
                        break

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
                    if not match and self.search_job and self.search_term in job_num.lower():
                        match = True
                    if not match and self.search_desc and self.search_term in desc.lower():
                        match = True
                    if not match and self.search_drawing:
                        for drawing in drawings:
                            if self.search_term in drawing.lower():
                                match = True
                                break

                    if match:
                        try:
                            mod_time = datetime.fromtimestamp(Path(job_docs_path).stat().st_mtime)
                        except (OSError, FileNotFoundError):
                            mod_time = datetime.now()

                        result = {
                            'date': mod_time,
                            'customer': display_customer,
                            'job_number': job_num,
                            'description': desc,
                            'drawings': drawings,
                            'path': job_docs_path
                        }
                        self.result_found.emit(result)
                        self.result_count += 1

    def _legacy_search(self):
        """Recursive search through all directories"""
        for prefix, base_dir in self.dirs_to_search:
            if self._is_cancelled:
                break
            self.progress_update.emit(f"Searching {prefix if prefix else 'standard'} directories...")
            # BP and IR dirs use filename search, not folder name search
            if prefix in ('BP', 'ITAR-BP', 'IR'):
                self._file_search(base_dir, prefix)
            else:
                self._legacy_recursive_search(base_dir, prefix)

    def _file_search(self, base_dir: str, prefix: str):
        """Search for files by filename within a directory tree (for BP/IR dirs)"""
        try:
            for root, dirs, files in os.walk(base_dir):
                if self._is_cancelled:
                    break
                for filename in files:
                    if self._is_cancelled:
                        break
                    if self.search_term in filename.lower():
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(root, base_dir)
                        path_parts = rel_path.split(os.sep)
                        customer = path_parts[0] if path_parts and path_parts[0] != '.' else ''

                        try:
                            mod_time = datetime.fromtimestamp(Path(file_path).stat().st_mtime)
                        except (OSError, FileNotFoundError):
                            mod_time = datetime.now()

                        name_no_ext = os.path.splitext(filename)[0]
                        result = {
                            'date': mod_time,
                            'customer': f"[{prefix}] {customer}" if customer else f"[{prefix}]",
                            'job_number': name_no_ext,
                            'description': rel_path if rel_path != '.' else '',
                            'drawings': [],
                            'path': root
                        }
                        self.result_found.emit(result)
                        self.result_count += 1
        except Exception:
            pass

    def _legacy_recursive_search(self, base_dir: str, prefix: str):
        """Recursively search all folders in legacy mode"""
        try:
            for root, dirs, files in os.walk(base_dir):
                if self._is_cancelled:
                    break

                folder_name = os.path.basename(root)

                # Try to extract customer from path
                rel_path = os.path.relpath(root, base_dir)
                path_parts = rel_path.split(os.sep)
                customer = path_parts[0] if path_parts and path_parts[0] != '.' else "Unknown"

                # Check if folder name or path contains search term
                if self.search_term in folder_name.lower() or self.search_term in rel_path.lower():
                    # Try to parse folder name for job info
                    parts = folder_name.split('_')
                    job_num = ""
                    desc = ""
                    drawings = []

                    # Try to extract job number
                    for part in parts:
                        if part and part[0].isdigit():
                            job_num = part
                            break

                    # If no structured format, use folder name as description
                    if not job_num:
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

                    result = {
                        'date': mod_time,
                        'customer': display_customer,
                        'job_number': job_num if job_num else "(no job #)",
                        'description': desc,
                        'drawings': drawings,
                        'path': root
                    }
                    self.result_found.emit(result)
                    self.result_count += 1
        except Exception:
            # Skip directories that cause errors
            pass


class SearchModule(BaseModule):
    """Module for searching jobs across customer directories"""

    def __init__(self):
        super().__init__()
        self._widget = None
        self.search_results: List[Dict[str, Any]] = []
        self._worker = None  # Background search worker

        # Widget references
        self.search_edit = None
        self.search_table = None
        self.search_status_label = None
        self.search_progress = None
        self.search_customer_check = None
        self.search_job_check = None
        self.search_desc_check = None
        self.search_drawing_check = None
        self.search_all_radio = None
        self.search_strict_radio = None
        self.search_blueprints_check = None
        self.mode_row_widget = None
        self.legacy_options_widget = None
        self.search_btn = None
        self.cancel_btn = None
        self.folder_contents_list = None

    def get_name(self) -> str:
        return "Search"

    def get_order(self) -> int:
        return 50  # Fifth tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the search tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('search/ui/search_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.search_edit = widget.search_edit
        self.search_table = widget.search_table
        self.search_status_label = widget.search_status_label
        self.search_progress = widget.search_progress
        self.search_customer_check = widget.search_customer_check
        self.search_job_check = widget.search_job_check
        self.search_desc_check = widget.search_desc_check
        self.search_drawing_check = widget.search_drawing_check
        self.search_all_radio = widget.search_all_radio
        self.search_strict_radio = widget.search_strict_radio
        self.search_blueprints_check = widget.search_blueprints_check
        self.search_inspection_check = widget.search_inspection_check
        self.mode_row_widget = widget.mode_row_widget
        self.legacy_options_widget = widget.legacy_options_widget
        self.search_btn = widget.search_btn
        self.cancel_btn = widget.cancel_btn

        # Keep criteria group compact, let results group expand
        widget.layout().setStretchFactor(widget.searchCriteriaGroup, 0)
        widget.layout().setStretchFactor(widget.searchResultsGroup, 1)

        # Build folder contents panel and wrap table in a splitter programmatically
        results_layout = widget.searchResultsGroup.layout()
        results_layout.removeWidget(self.search_table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.search_table)

        folder_group = QGroupBox("Folder Contents")
        folder_layout = QVBoxLayout()
        folder_layout.setContentsMargins(5, 5, 5, 5)
        self.folder_contents_list = QListWidget()
        self.folder_contents_list.setAlternatingRowColors(True)
        folder_layout.addWidget(self.folder_contents_list)
        folder_group.setLayout(folder_layout)
        splitter.addWidget(folder_group)

        splitter.setSizes([400, 200])
        results_layout.insertWidget(0, splitter)
        results_layout.setStretchFactor(splitter, 1)

        # Setup table properties
        self.search_table.horizontalHeader().setStretchLastSection(True)
        self.search_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Setup folder contents list
        self.folder_contents_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Hide progress bar and cancel button initially
        self.search_progress.hide()
        self.cancel_btn.hide()

        # Connect signals
        self.search_btn.clicked.connect(self.perform_search)
        self.cancel_btn.clicked.connect(self.cancel_search)
        self.search_edit.returnPressed.connect(self.perform_search)
        widget.clear_btn.clicked.connect(self.clear_search)
        self.search_all_radio.toggled.connect(self.update_search_field_checkboxes)
        self.search_strict_radio.toggled.connect(self.update_search_field_checkboxes)
        self.search_table.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_table.doubleClicked.connect(self.open_selected_search_job)
        self.search_table.itemSelectionChanged.connect(
            lambda: self._on_result_selected(self.search_table.currentRow())
        )
        self.folder_contents_list.doubleClicked.connect(self._open_folder_file)
        self.folder_contents_list.customContextMenuRequested.connect(self._show_file_context_menu)

        # Initialize UI state
        self.update_legacy_mode_ui()

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

    # ==================== UI State Management ====================

    def update_search_field_checkboxes(self):
        """Enable/disable field checkboxes based on search mode"""
        is_strict_mode = self.search_strict_radio.isChecked()

        self.search_customer_check.setEnabled(is_strict_mode)
        self.search_job_check.setEnabled(is_strict_mode)
        self.search_desc_check.setEnabled(is_strict_mode)
        self.search_drawing_check.setEnabled(is_strict_mode)

        # legacy_options_widget has no content — keep hidden
        self.legacy_options_widget.hide()

    def update_legacy_mode_ui(self):
        """Show/hide UI elements based on legacy mode setting"""
        is_legacy = self.app_context.get_setting('legacy_mode', True)

        # Show/hide "Search All Folders" option
        if is_legacy:
            self.mode_row_widget.setVisible(True)
        else:
            # Hide mode selection, force Strict Format
            self.mode_row_widget.setVisible(False)
            self.search_strict_radio.setChecked(True)

        # Update checkbox states
        self.update_search_field_checkboxes()

    # ==================== Search Functionality ====================

    def perform_search(self):
        """Perform search based on search term and mode"""
        search_term = self.search_edit.text().strip().lower()
        if len(search_term) < 2:
            self.show_error("Search", "Please enter at least 2 characters")
            return

        # Cancel any existing search
        if self._worker and self._worker.isRunning():
            self.cancel_search()
            return

        self.search_table.setRowCount(0)
        self.search_results.clear()

        strict_mode = self.search_strict_radio.isChecked()

        # Build list of directories to search
        dirs_to_search = []

        # Always search customer files directories
        customer_dirs = self._get_customer_files_dirs()
        if not customer_dirs:
            cf_dir = self.app_context.get_setting('customer_files_dir', '')
            itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
            if not cf_dir and not itar_cf_dir:
                self.show_error("Error", "No customer directories configured")
            else:
                self.show_error("Error", "Configured directories do not exist")
            return

        dirs_to_search.extend(customer_dirs)

        # Optionally search blueprints directories (available in all modes)
        if self.search_blueprints_check.isChecked():
            bp_dir = self.app_context.get_setting('blueprints_dir', '')
            if bp_dir and os.path.exists(bp_dir):
                dirs_to_search.append(('BP', bp_dir))
            itar_bp_dir = self.app_context.get_setting('itar_blueprints_dir', '')
            if itar_bp_dir and os.path.exists(itar_bp_dir):
                dirs_to_search.append(('ITAR-BP', itar_bp_dir))

        # Optionally search inspection reports directory
        if self.search_inspection_check.isChecked():
            ir_dir = self.app_context.get_setting('inspection_report_dir', '')
            if ir_dir and os.path.exists(ir_dir):
                dirs_to_search.append(('IR', ir_dir))

        # Determine which fields to search
        if strict_mode:
            search_customer = self.search_customer_check.isChecked()
            search_job = self.search_job_check.isChecked()
            search_desc = self.search_desc_check.isChecked()
            search_drawing = self.search_drawing_check.isChecked()
        else:
            # Legacy mode: search all fields
            search_customer = search_job = search_desc = search_drawing = True

        # Show progress UI
        self.search_progress.setMaximum(0)  # Indeterminate progress
        self.search_progress.show()
        self.search_status_label.setText("Starting search...")
        self.search_btn.setEnabled(False)
        self.cancel_btn.show()

        # Start background search worker
        self._worker = SearchWorker(
            dirs_to_search, search_term, strict_mode,
            search_customer, search_job, search_desc, search_drawing,
            self.app_context
        )
        self._worker.result_found.connect(self._on_result_found)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.start()

    def cancel_search(self):
        """Cancel the running search"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.search_status_label.setText("Cancelling search...")

    def _on_result_found(self, result: dict):
        """Slot called when a search result is found"""
        self.search_results.append(result)

        # Add to table immediately
        row = self.search_table.rowCount()
        self.search_table.insertRow(row)
        self.search_table.setItem(row, 0, QTableWidgetItem(result['date'].strftime("%Y-%m-%d %H:%M")))
        self.search_table.setItem(row, 1, QTableWidgetItem(result['customer']))
        self.search_table.setItem(row, 2, QTableWidgetItem(result['job_number']))
        self.search_table.setItem(row, 3, QTableWidgetItem(result['description']))
        self.search_table.setItem(row, 4, QTableWidgetItem(', '.join(result['drawings'])))

    def _on_progress_update(self, status: str):
        """Slot called with progress updates"""
        self.search_status_label.setText(status)

    def _on_search_finished(self, result_count: int):
        """Slot called when search completes"""
        # Sort results by date (newest first)
        self.search_results.sort(key=lambda x: x['date'], reverse=True)

        # Rebuild table with sorted results
        self.search_table.setRowCount(0)
        for result in self.search_results:
            row = self.search_table.rowCount()
            self.search_table.insertRow(row)
            self.search_table.setItem(row, 0, QTableWidgetItem(result['date'].strftime("%Y-%m-%d %H:%M")))
            self.search_table.setItem(row, 1, QTableWidgetItem(result['customer']))
            self.search_table.setItem(row, 2, QTableWidgetItem(result['job_number']))
            self.search_table.setItem(row, 3, QTableWidgetItem(result['description']))
            self.search_table.setItem(row, 4, QTableWidgetItem(', '.join(result['drawings'])))

        self.search_status_label.setText(f"Found {result_count} result(s)")
        self.search_progress.hide()
        self.search_btn.setEnabled(True)
        self.cancel_btn.hide()

    def clear_search(self):
        """Clear search results and input"""
        # Cancel any running search
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self.search_edit.clear()
        self.search_table.setRowCount(0)
        self.search_results.clear()
        self.folder_contents_list.clear()
        self.search_status_label.setText("")
        self.search_progress.hide()
        self.search_btn.setEnabled(True)
        self.cancel_btn.hide()

    # ==================== Helper Methods ====================

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

    # ==================== Context Menu ====================

    def show_search_context_menu(self, pos):
        """Show context menu on right-click"""
        row = self.search_table.currentRow()
        if row < 0:
            return

        menu = QMenu(self._widget)

        open_action = menu.addAction("Open Job Folder")
        open_action.triggered.connect(self.open_selected_search_job)

        open_bp_action = menu.addAction("Open Blueprints Folder")
        open_bp_action.triggered.connect(self.open_selected_blueprints)

        menu.addSeparator()

        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(self.copy_search_path)

        menu.exec(self.search_table.viewport().mapToGlobal(pos))

    def open_selected_search_job(self):
        """Open the selected job folder"""
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            if os.path.exists(path):
                open_folder(path)
            else:
                self.show_error("Not Found", f"Folder not found: {path}")

    def open_selected_blueprints(self):
        """Open the blueprints folder for the selected job's customer"""
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            customer = self.search_results[row]['customer'].replace('[ITAR] ', '').replace('[ITAR-BP] ', '')
            is_itar = '[ITAR]' in self.search_results[row]['customer']

            bp_dir = self.app_context.get_setting('itar_blueprints_dir' if is_itar else 'blueprints_dir', '')
            if bp_dir:
                customer_bp = os.path.join(bp_dir, customer)
                if os.path.exists(customer_bp):
                    open_folder(customer_bp)
                else:
                    self.show_error("Not Found", f"Blueprints for {customer} not found")

    def copy_search_path(self):
        """Copy the selected result's path to clipboard"""
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            QApplication.clipboard().setText(path)
            self.search_status_label.setText("Path copied to clipboard")

    # ==================== Folder Contents Panel ====================

    def _on_result_selected(self, row: int):
        """Populate folder contents list when a search result row is selected"""
        self.folder_contents_list.clear()
        if row < 0 or row >= len(self.search_results):
            return

        path = self.search_results[row]['path']
        if not os.path.exists(path):
            item = QListWidgetItem("(folder not found)")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.folder_contents_list.addItem(item)
            return

        try:
            entries = sorted(os.listdir(path), key=lambda n: (os.path.isdir(os.path.join(path, n)), n.lower()))
        except OSError:
            return

        for name in entries:
            full_path = os.path.join(path, name)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, full_path)
            if os.path.isdir(full_path):
                item.setText(f"[{name}]")
            self.folder_contents_list.addItem(item)

    def _open_folder_file(self):
        """Open the double-clicked file or folder from the contents list"""
        item = self.folder_contents_list.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_file_context_menu(self, pos):
        """Context menu for the folder contents list"""
        item = self.folder_contents_list.itemAt(pos)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        menu = QMenu(self._widget)
        open_action = menu.addAction("Open")
        open_action.triggered.connect(self._open_folder_file)

        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(path))

        menu.exec(self.folder_contents_list.viewport().mapToGlobal(pos))

    def cleanup(self):
        """Cleanup resources"""
        # Stop any running worker thread
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self.search_results.clear()
