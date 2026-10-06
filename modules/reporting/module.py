"""
Reporting Module - JobBOSS DB reporting (experimental)

Pulls job data straight out of a JobBOSS SQL Server (see
experimental/db_integration.py) instead of showing placeholder sample data.
Connection details are configured in Settings > Advanced Settings.
"""

import sys
import csv
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QFileDialog, QHeaderView, QAbstractItemView
)
from PyQt6 import uic

from core.base_module import BaseModule
from experimental.db_integration import is_configured, test_connection, fetch_report, fetch_customers

_REPORT_COLUMNS = ('date', 'customer', 'job', 'description', 'status')


class _ConnectWorker(QThread):
    """One-shot connection test, off the GUI thread (mirrors main.py's _PluginInstallWorker)."""

    finished_ok = pyqtSignal(bool, str)

    def __init__(self, settings: dict):
        super().__init__()
        self._settings = settings

    def run(self):
        ok, message = test_connection(self._settings)
        self.finished_ok.emit(ok, message)


class _CustomerListWorker(QThread):
    """Fetches the distinct customer list to populate the Customer filter combo."""

    success = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self._settings = settings

    def run(self):
        try:
            customers = fetch_customers(self._settings)
        except Exception as exc:
            self.error.emit(f"Customer list query failed ({type(exc).__name__})")
        else:
            self.success.emit(customers)


class _ReportWorker(QThread):
    """Runs one report query off the GUI thread."""

    success = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, settings: dict, report_type: str, filters: dict):
        super().__init__()
        self._settings = settings
        self._report_type = report_type
        self._filters = filters

    def run(self):
        try:
            rows = fetch_report(self._settings, self._report_type, self._filters)
        except Exception as exc:
            # Only the exception type, not str(exc) -- same rule as
            # experimental/db_integration.py's test_connection().
            self.error.emit(f"Report query failed ({type(exc).__name__})")
        else:
            self.success.emit(rows)


class ReportingModule(BaseModule):
    """Module for generating and exporting JobBOSS reports"""

    def __init__(self):
        super().__init__()
        self._widget = None
        # Widget references
        self.report_type_combo = None
        self.report_table = None
        self.report_status_label = None
        self.generate_report_btn = None
        self.connect_db_btn = None
        self.disconnect_db_btn = None
        self.db_status_label = None
        self.report_customer_combo = None
        self.report_start_date = None
        self.report_end_date = None

        self._db_ready = False
        self._connect_worker = None
        self._report_worker = None
        self._customer_worker = None

    def get_name(self) -> str:
        return "Reports (Beta)"

    def get_order(self) -> int:
        return 80  # Eighth tab

    def is_experimental(self) -> bool:
        return True  # This module is experimental

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the reporting tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('reporting/ui/reporting_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.report_type_combo = widget.report_type_combo
        self.report_table = widget.report_table
        self.report_status_label = widget.report_status_label
        self.generate_report_btn = widget.generate_report_btn
        self.connect_db_btn = widget.connect_db_btn
        self.disconnect_db_btn = widget.disconnect_db_btn
        self.db_status_label = widget.db_status_label
        self.report_customer_combo = widget.report_customer_combo
        self.report_start_date = widget.report_start_date
        self.report_end_date = widget.report_end_date

        # Setup table properties
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Connect signals
        self.connect_db_btn.clicked.connect(self.connect_to_db)
        self.disconnect_db_btn.clicked.connect(self.disconnect_from_db)
        self.generate_report_btn.clicked.connect(self.generate_report)
        widget.export_report_btn.clicked.connect(self.export_report)
        self.report_type_combo.currentTextChanged.connect(self._update_filter_enabled_state)
        self._update_filter_enabled_state(self.report_type_combo.currentText())

        return widget

    def _update_filter_enabled_state(self, report_type: str):
        """Grey out the Customer/Date filters when the selected report type
        doesn't use them, instead of silently ignoring whatever's typed in.
        """
        self.report_customer_combo.setEnabled(report_type == "Jobs by Customer")
        is_date_range = report_type == "Jobs by Date Range"
        self.report_start_date.setEnabled(is_date_range)
        self.report_end_date.setEnabled(is_date_range)

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

    def _jobboss_settings(self) -> dict:
        """Collect the non-secret JobBOSS DB connection settings; the password
        itself is looked up from the OS credential store by db_integration.
        """
        return {
            'jobboss_db_host': self.app_context.get_setting('jobboss_db_host', ''),
            'jobboss_db_port': self.app_context.get_setting('jobboss_db_port', ''),
            'jobboss_db_name': self.app_context.get_setting('jobboss_db_name', ''),
            'jobboss_db_user': self.app_context.get_setting('jobboss_db_user', ''),
        }

    # ==================== Database Connection ====================

    def connect_to_db(self):
        settings = self._jobboss_settings()
        if not is_configured(settings):
            self.show_error(
                "Not Configured",
                "Set the JobBOSS DB connection (Host, Database, Username, Password) "
                "in Settings > Advanced Settings first."
            )
            return

        self.connect_db_btn.setEnabled(False)
        self.db_status_label.setText("Status: Connecting...")
        self.db_status_label.setStyleSheet("color: #999;")

        self._connect_worker = _ConnectWorker(settings)
        self._connect_worker.finished_ok.connect(self._on_connect_result)
        self._connect_worker.start()

    def _on_connect_result(self, ok: bool, message: str):
        self._db_ready = ok
        self.connect_db_btn.setEnabled(not ok)
        self.disconnect_db_btn.setEnabled(ok)
        if ok:
            self.db_status_label.setText("Status: Connected")
            self.db_status_label.setStyleSheet("color: green;")
            self.log_message("Connected to JobBOSS DB")
            self._load_customer_list()
        else:
            self.db_status_label.setText(f"Status: {message}")
            self.db_status_label.setStyleSheet("color: #999;")

    def disconnect_from_db(self):
        self._db_ready = False
        self.connect_db_btn.setEnabled(True)
        self.disconnect_db_btn.setEnabled(False)
        self.db_status_label.setText("Status: Not connected")
        self.db_status_label.setStyleSheet("color: #999;")

    def _load_customer_list(self):
        """Populate the Customer filter combo from JobBOSS after a successful connect."""
        self._customer_worker = _CustomerListWorker(self._jobboss_settings())
        self._customer_worker.success.connect(self._on_customers_loaded)
        self._customer_worker.error.connect(
            lambda msg: self.log_message(f"Reporting: {msg}")
        )
        self._customer_worker.start()

    def _on_customers_loaded(self, customers: list):
        current = self.report_customer_combo.currentText()
        self.report_customer_combo.clear()
        self.report_customer_combo.addItem("All Customers")
        self.report_customer_combo.addItems(customers)
        idx = self.report_customer_combo.findText(current)
        if idx >= 0:
            self.report_customer_combo.setCurrentIndex(idx)
        else:
            self.report_customer_combo.setCurrentText(current)

    # ==================== Report Generation ====================

    def generate_report(self):
        """Generate a report by querying the JobBOSS DB on a background thread."""
        if not self._db_ready:
            self.show_error("Not Connected", "Click \"Connect to Database\" first.")
            return

        report_type = self.report_type_combo.currentText()
        filters = {}

        if report_type == "Jobs by Customer":
            customer = self.report_customer_combo.currentText().strip()
            if customer and customer != "All Customers":
                filters['customer'] = customer
        elif report_type == "Jobs by Date Range":
            try:
                filters['start_date'] = datetime.strptime(
                    self.report_start_date.text().strip(), '%Y-%m-%d').date()
                filters['end_date'] = datetime.strptime(
                    self.report_end_date.text().strip(), '%Y-%m-%d').date()
            except ValueError:
                self.show_error("Invalid Date", "Enter Start Date and End Date as YYYY-MM-DD.")
                return

        self.generate_report_btn.setEnabled(False)
        self.report_status_label.setText(f"Running '{report_type}'...")

        self._report_worker = _ReportWorker(self._jobboss_settings(), report_type, filters)
        self._report_worker.success.connect(self._on_report_rows)
        self._report_worker.error.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_rows(self, rows: list):
        self.generate_report_btn.setEnabled(True)

        self.report_table.setRowCount(0)
        for row in rows:
            r = self.report_table.rowCount()
            self.report_table.insertRow(r)
            for col, key in enumerate(_REPORT_COLUMNS):
                self.report_table.setItem(r, col, QTableWidgetItem(row.get(key, '')))

        report_type = self.report_type_combo.currentText()
        self.report_status_label.setText(f"Showing {len(rows)} record(s) for '{report_type}'")
        self.log_message(f"Generated report: {report_type} ({len(rows)} rows)")

    def _on_report_error(self, message: str):
        self.generate_report_btn.setEnabled(True)
        self.report_status_label.setText("Report failed.")
        self.show_error("Report Failed", message)

    def export_report(self):
        """Export report to CSV"""
        if self.report_table.rowCount() == 0:
            self.show_error("No Data", "Generate a report first before exporting")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self._widget,
            "Export Report",
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)

                    # Write headers
                    headers = []
                    for col in range(self.report_table.columnCount()):
                        headers.append(self.report_table.horizontalHeaderItem(col).text())
                    writer.writerow(headers)

                    # Write data
                    for row in range(self.report_table.rowCount()):
                        row_data = []
                        for col in range(self.report_table.columnCount()):
                            item = self.report_table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                self.show_info("Export Successful", f"Report exported to:\n{file_path}")
                self.log_message(f"Exported report to: {file_path}")
            except Exception as e:
                self.show_error("Export Failed", f"Failed to export report:\n{str(e)}")

    def cleanup(self):
        """Cleanup resources"""
        for worker in (self._connect_worker, self._report_worker, self._customer_worker):
            if worker is not None and worker.isRunning():
                worker.wait(2000)
