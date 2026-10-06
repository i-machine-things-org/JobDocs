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
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QEvent, Qt
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QFileDialog, QHeaderView, QAbstractItemView,
    QDateEdit, QCalendarWidget
)
from PyQt6 import uic

from core.base_module import BaseModule
from experimental.db_integration import is_configured, test_connection, fetch_report, fetch_customers

_REPORT_COLUMNS = ('date', 'customer', 'job', 'description', 'status')


class _DateCalendarPopupFilter(QObject):
    """Double-click a QDateEdit to drop down a small calendar for picking a
    date, in addition to Qt's built-in dropdown-arrow click (calendarPopup).
    Built on public QCalendarWidget/QWidget APIs rather than QDateEdit's
    private popup internals, which aren't safe to trigger programmatically.

    QAbstractSpinBox (QDateEdit's base) routes mouse events for the visible
    text to its internal child QLineEdit, not to the QDateEdit itself -- so
    this must be installed on date_edit.lineEdit(), not date_edit directly,
    or a real double-click never reaches eventFilter() at all.
    """

    def __init__(self, date_edit: QDateEdit, parent=None):
        super().__init__(parent)
        self._date_edit = date_edit

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self._show_popup()
            return True
        return False

    def _show_popup(self):
        date_edit = self._date_edit
        calendar = QCalendarWidget()
        calendar.setWindowFlags(Qt.WindowType.Popup)
        calendar.setSelectedDate(date_edit.date())

        def pick(qdate):
            date_edit.setDate(qdate)
            calendar.close()

        calendar.clicked.connect(pick)
        calendar.activated.connect(pick)
        calendar.move(date_edit.mapToGlobal(date_edit.rect().bottomLeft()))
        calendar.show()
        self._popup = calendar  # keep alive while shown; see CODING_NOTES.md on non-modal dialogs


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
        self._default_table_headers = []

        self._db_ready = False
        self._connect_worker = None
        self._report_worker = None
        self._customer_worker = None

        # Metadata for whatever report is currently in report_table, captured
        # at generate time so Export reflects what was actually run even if
        # the combo/filters have changed since (not whatever they show now).
        self._last_report_type = None
        self._last_filters = {}
        self._last_generated_at = None

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

        self._start_date_popup_filter = _DateCalendarPopupFilter(self.report_start_date, widget)
        self.report_start_date.lineEdit().installEventFilter(self._start_date_popup_filter)
        self._end_date_popup_filter = _DateCalendarPopupFilter(self.report_end_date, widget)
        self.report_end_date.lineEdit().installEventFilter(self._end_date_popup_filter)

        # Setup table properties
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Connect signals
        self.connect_db_btn.clicked.connect(self.connect_to_db)
        self.disconnect_db_btn.clicked.connect(self.disconnect_from_db)
        self.generate_report_btn.clicked.connect(self.generate_report)
        widget.export_report_btn.clicked.connect(self.export_report)
        self._default_table_headers = [
            self.report_table.horizontalHeaderItem(col).text()
            for col in range(self.report_table.columnCount())
        ]
        self.report_type_combo.currentTextChanged.connect(self._on_report_type_changed)
        self._on_report_type_changed(self.report_type_combo.currentText())

        return widget

    def _on_report_type_changed(self, report_type: str):
        self._update_filter_enabled_state(report_type)
        self._update_table_headers(report_type)

    def _update_filter_enabled_state(self, report_type: str):
        """Grey out the Customer/Date filters when the selected report type
        doesn't use them, instead of silently ignoring whatever's typed in.
        """
        self.report_customer_combo.setEnabled(report_type == "Jobs by Customer")
        uses_dates = report_type in ("Jobs by Date Range", "Top Customers")
        self.report_start_date.setEnabled(uses_dates)
        self.report_end_date.setEnabled(uses_dates)

    def _update_table_headers(self, report_type: str):
        """Relabel the fixed Date/Customer/Job #/Description/Status columns
        for aggregate reports that repurpose them for different data, instead
        of showing misleading headers for what's actually in each cell.
        """
        if report_type == "Top Customers":
            headers = ['', 'Customer', 'Job Count', '', 'Gross Revenue']
        elif report_type == "Job Statistics":
            headers = ['', '', '', 'Metric', 'Value']
        else:
            headers = self._default_table_headers
        for col, label in enumerate(headers):
            self.report_table.setHorizontalHeaderItem(col, QTableWidgetItem(label))

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

    @staticmethod
    def _picked_date(date_edit: QDateEdit):
        """The QDate as a Python date, or None if still at the "(No Filter)"
        sentinel (date_edit's minimumDate, set in reporting_tab.ui).
        """
        if date_edit.date() == date_edit.minimumDate():
            return None
        return date_edit.date().toPyDate()

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
            start = self._picked_date(self.report_start_date)
            end = self._picked_date(self.report_end_date)
            if start is None or end is None:
                self.show_error(
                    "Invalid Date",
                    "Pick both a Start Date and End Date (double-click a field, or use its "
                    "dropdown arrow, to open the calendar)."
                )
                return
            filters['start_date'] = start
            filters['end_date'] = end
        elif report_type == "Top Customers":
            start = self._picked_date(self.report_start_date)
            end = self._picked_date(self.report_end_date)
            if (start is None) != (end is None):
                self.show_error(
                    "Invalid Date",
                    "Pick both Start Date and End Date, or leave both as \"(No Filter)\" for all time."
                )
                return
            if start is not None and end is not None:
                filters['start_date'] = start
                filters['end_date'] = end

        self.generate_report_btn.setEnabled(False)
        self.report_status_label.setText(f"Running '{report_type}'...")

        self._last_report_type = report_type
        self._last_filters = filters

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

        self._last_generated_at = datetime.now()
        report_type = self.report_type_combo.currentText()
        self.report_status_label.setText(f"Showing {len(rows)} record(s) for '{report_type}'")
        self.log_message(f"Generated report: {report_type} ({len(rows)} rows)")

    def _on_report_error(self, message: str):
        self.generate_report_btn.setEnabled(True)
        self.report_status_label.setText("Report failed.")
        self.show_error("Report Failed", message)

    def _date_range_label(self) -> str:
        start = self._last_filters.get('start_date')
        end = self._last_filters.get('end_date')
        if start and end:
            return f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        if self._last_report_type == "Top Customers":
            return "All Time"
        return "N/A"

    def _export_title_block(self) -> list:
        generated = self._last_generated_at
        return [
            ["JobDocs - JobBOSS Reporting"],
            ["Report:", self._last_report_type or ""],
            ["Date Range:", self._date_range_label()],
            ["Generated:", generated.strftime('%Y-%m-%d %H:%M:%S') if generated else ""],
            [],
        ]

    def _export_table_rows(self) -> tuple:
        """(headers, data_rows) from report_table, as plain strings."""
        headers = [
            self.report_table.horizontalHeaderItem(col).text()
            for col in range(self.report_table.columnCount())
        ]
        data_rows = []
        for row in range(self.report_table.rowCount()):
            data_rows.append([
                self.report_table.item(row, col).text() if self.report_table.item(row, col) else ""
                for col in range(self.report_table.columnCount())
            ])
        return headers, data_rows

    def export_report(self):
        """Export report to CSV or Excel (.xlsx)"""
        if self.report_table.rowCount() == 0:
            self.show_error("No Data", "Generate a report first before exporting")
            return

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self._widget,
            "Export Report",
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        is_excel = 'xlsx' in selected_filter.lower() or file_path.lower().endswith('.xlsx')
        if is_excel and not file_path.lower().endswith('.xlsx'):
            file_path += '.xlsx'
        elif not is_excel and not file_path.lower().endswith('.csv'):
            file_path += '.csv'

        try:
            if is_excel:
                self._export_xlsx(file_path)
            else:
                self._export_csv(file_path)
            self.show_info("Export Successful", f"Report exported to:\n{file_path}")
            self.log_message(f"Exported report to: {file_path}")
        except Exception as e:
            self.show_error("Export Failed", f"Failed to export report:\n{str(e)}")

    def _export_csv(self, file_path: str):
        headers, data_rows = self._export_table_rows()
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(self._export_title_block())
            writer.writerow(headers)
            writer.writerows(data_rows)

    def _export_xlsx(self, file_path: str):
        from openpyxl import Workbook
        from openpyxl.styles import Font

        title_block = self._export_title_block()
        headers, data_rows = self._export_table_rows()

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        for row in title_block:
            ws.append(row)
        header_row_idx = len(title_block) + 1
        ws.append(headers)
        for row in data_rows:
            ws.append(row)

        ws['A1'].font = Font(bold=True, size=12)
        for cell in ws[header_row_idx]:
            cell.font = Font(bold=True)
        for col_cells in ws.columns:
            width = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
            ws.column_dimensions[col_cells[0].column_letter].width = max(10, min(40, width + 2))

        wb.save(file_path)

    def cleanup(self):
        """Cleanup resources"""
        for worker in (self._connect_worker, self._report_worker, self._customer_worker):
            if worker is not None and worker.isRunning():
                worker.wait(2000)
