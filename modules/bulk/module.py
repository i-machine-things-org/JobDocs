"""
Bulk Module - Bulk Job Creation from CSV

This module handles creating multiple jobs from CSV data.
Supports validation, duplicate detection, and progress tracking.
"""

import os
import sys
import csv
from io import StringIO
from pathlib import Path
from typing import List, Dict, Any
from PyQt6.QtWidgets import QWidget, QMessageBox, QTableWidgetItem, QFileDialog, QApplication
from PyQt6 import uic

from core.base_module import BaseModule
from shared.utils import parse_job_numbers


class BulkModule(BaseModule):
    """Module for bulk job creation from CSV"""

    def __init__(self):
        super().__init__()
        self._widget = None
        # Widget references
        self.bulk_itar_check = None
        self.bulk_text = None
        self.bulk_table = None
        self.bulk_status_label = None
        self.bulk_progress = None

    def get_name(self) -> str:
        return "Bulk Create"

    def get_order(self) -> int:
        return 40  # Fourth tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the bulk tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('bulk/ui/bulk_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.bulk_itar_check = widget.bulk_itar_check
        self.bulk_text = widget.bulk_text
        self.bulk_table = widget.bulk_table
        self.bulk_status_label = widget.bulk_status_label
        self.bulk_progress = widget.bulk_progress

        # Setup table properties
        self.bulk_table.horizontalHeader().setStretchLastSection(True)

        # Connect signals
        widget.import_btn.clicked.connect(self.import_bulk_csv)
        widget.clear_bulk_btn.clicked.connect(lambda: self.bulk_text.clear())
        widget.validate_btn.clicked.connect(self.validate_bulk_data)
        widget.create_bulk_btn.clicked.connect(self.create_bulk_jobs)

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

    # ==================== CSV Import ====================

    def import_bulk_csv(self):
        """Import CSV file into bulk text area"""
        file_path, _ = QFileDialog.getOpenFileNames(
            self._widget, "Select CSV File", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        if file_path:
            try:
                with open(file_path[0], 'r', encoding='utf-8') as f:
                    self.bulk_text.setPlainText(f.read())
                self.validate_bulk_data()
            except Exception as e:
                self.show_error("Error", f"Failed to read file: {e}")

    # ==================== Data Parsing ====================

    def parse_bulk_data(self) -> List[Dict[str, Any]]:
        """Parse bulk data from text area"""
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
                parts = [p.strip() for p in line.split(',')]

            if len(parts) < 3:
                jobs.append({'line': line_num, 'valid': False, 'error': 'Need customer, job#, description'})
                continue

            customer = parts[0].strip()
            job_number = parts[1].strip()
            description = parts[2].strip()
            drawings = [d.strip() for d in parts[3:] if d.strip()]

            errors = []
            if not customer:
                errors.append("Missing customer")
            if not job_number:
                errors.append("Missing job#")
            if not description:
                errors.append("Missing description")

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

    # ==================== Validation ====================

    def validate_bulk_data(self) -> bool:
        """Validate bulk data and show in table"""
        self.bulk_table.setRowCount(0)
        jobs = self.parse_bulk_data()

        valid = 0
        invalid = 0

        for job in jobs:
            row = self.bulk_table.rowCount()
            self.bulk_table.insertRow(row)

            if job['valid']:
                status = "✓ Valid"
                dup, dup_location = self._check_duplicate_job(job['customer'], job['job_number'])
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

    def _check_duplicate_job(self, customer: str, job_number: str):
        """Check if job already exists"""
        job_number_lower = job_number.lower()

        # Check history
        recent_jobs = self.app_context.history.get('recent_jobs', [])
        for job in recent_jobs:
            if job.get('job_number', '').lower() == job_number_lower:
                existing_customer = job.get('customer', 'Unknown')
                return True, f"{existing_customer}"

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
                            return True, f"{customer_dir}"
            except OSError:
                pass

        return False, None

    def job_exists(self, customer: str, job_number: str, is_itar: bool) -> bool:
        """Check if a job already exists in the system"""
        if self.app_context.get_setting('allow_duplicate_jobs', False):
            return False

        bp_dir, cf_dir = self.app_context.get_directories(is_itar)
        if not cf_dir:
            return False

        customer_path = Path(cf_dir) / customer
        if not customer_path.exists():
            return False

        jobs = self.app_context.find_job_folders(str(customer_path))
        for job_name, _ in jobs:
            if job_name.startswith(f"{job_number}_") or job_name == job_number:
                return True

        return False

    # ==================== Bulk Job Creation ====================

    def create_bulk_jobs(self):
        """Create all valid jobs from bulk data"""
        if not self.validate_bulk_data():
            reply = QMessageBox.question(
                self._widget,
                "Warning",
                "Some jobs have errors. Create only valid jobs?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        jobs = [j for j in self.parse_bulk_data() if j['valid']]
        if not jobs:
            self.show_error("No Jobs", "No valid jobs to create")
            return

        is_itar = self.bulk_itar_check.isChecked()
        bp_dir, cf_dir = self.app_context.get_directories(is_itar)

        if not bp_dir or not cf_dir:
            self.show_error("Error", "Directories not configured")
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
            reply = QMessageBox.question(
                self._widget,
                "Duplicate Jobs Found",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.bulk_progress.setMaximum(len(jobs))
        self.bulk_progress.setValue(0)
        self.bulk_progress.show()

        # Track existing customers
        existing_customers = self.app_context.get_customer_list()
        new_customers = set()

        created = 0
        skipped = 0

        # Get job module reference for creating jobs
        job_module = None
        for module in self.app_context.main_window.modules:
            if module.get_name() == "Create Job Folder":
                job_module = module
                break

        if not job_module:
            self.show_error("Error", "Job module not found")
            return

        for i, job in enumerate(jobs):
            customer = job['customer']
            if customer not in existing_customers and customer not in new_customers:
                new_customers.add(customer)

            # Skip if job already exists
            if self.job_exists(customer, job['job_number'], is_itar):
                skipped += 1
            else:
                if job_module.create_single_job(customer, job['job_number'], job['description'], job['drawings'], is_itar, []):
                    created += 1

            self.bulk_progress.setValue(i + 1)
            QApplication.processEvents()

        self.bulk_progress.hide()
        msg = f"Created {created}/{len(jobs)} jobs"
        if skipped > 0:
            msg += f" (Skipped {skipped} duplicates)"
        self.show_info("Complete", msg)

        # Refresh via main window
        main_window = self.app_context.main_window
        if main_window:
            main_window.refresh_history()
            if new_customers:
                main_window.populate_customer_lists()

    def cleanup(self):
        """Cleanup resources"""
        pass
