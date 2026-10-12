"""
Reporting Module - JobBOSS DB reporting (experimental)

Pulls job data straight out of a JobBOSS SQL Server instead of showing
placeholder sample data. Connection details are configured in Settings >
Advanced Settings. Generic UI glue only -- every report type's query, row
shape, and filter requirements live in modules/reporting/reports/ (one file
per report type, see that package's __init__.py for the registry); this
file has no per-report-type branches, so adding a report type never
requires editing it.
"""

import sys
import csv
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QDate, QThread, pyqtSignal, QObject, QEvent, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QFileDialog, QHeaderView, QAbstractItemView,
    QDateEdit, QCalendarWidget, QDialog, QDialogButtonBox, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QHBoxLayout
)
from PyQt6 import uic

from core.base_module import BaseModule
from experimental.db_integration import is_configured, test_connection, fetch_customers, fetch_employees
from modules.reporting.reports import REPORTS, REPORT_TYPES

# Exported cells (Description/Notes/Customer/PO etc.) are free text sourced
# from JobBOSS -- neutralize values Excel/CSV readers treat as formula
# triggers (a note starting with "=" becomes a live formula on open; "+"/"-"/
# "@"/tab/CR are also sniffed by Excel's CSV importer). Prefixing with "'"
# is the standard mitigation (matches how Excel itself stores a manually
# typed "'=foo" as literal text).
_FORMULA_TRIGGER_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _neutralize_formula_cell(value: str) -> str:
    return f"'{value}" if value and value.startswith(_FORMULA_TRIGGER_CHARS) else value


# Fill color for whatever cell a report's row_highlight() flags (see
# modules/reporting/reports/base.py) -- currently only Job Report's
# Scheduled-End-past-Promise-Date flag, mirroring Report Fixer's Fix &
# Export red-highlight rule for the same comparison.
_LATE_FILL_COLOR = QColor(255, 204, 204)

# Cap on auto-fit column width (px) -- without it, one row with an unusually
# long Description/Notes value would stretch that single column wide enough
# to push every other column off-screen. The horizontal scrollbar (Interactive
# resize mode already enables it) covers genuinely-wide content beyond this;
# the user can still drag a capped column wider by hand if they want to see
# the full value without scrolling.
_MAX_AUTO_COLUMN_WIDTH = 300


class _CustomerPickerDialog(QDialog):
    """Pick zero, one, or several items for a report filter.

    Generic (value, label) checklist -- reused for both the Customer picker
    (value == label, a plain customer name straight off fetch_customers())
    and the Employee picker (value = the 6-char Employee code the SQL filter
    actually matches on, label = a human-readable "Name (Code)" display
    string off fetch_employees()); `title`/`noun` just relabel the dialog
    for whichever filter opened it.

    Zero checked means "All", not "none" -- Clear really clears back to All,
    it doesn't produce an empty/no-match report.
    """

    def __init__(self, items: list, selected: list, parent=None,
                 title: str = "Select Customers", noun: str = "Customers"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(320, 420)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        selected_set = set(selected)
        for value, label in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if value in selected_set else Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Checked))
        clear_btn = QPushButton(f"Clear (All {noun})")
        clear_btn.clicked.connect(lambda: self._set_all(Qt.CheckState.Unchecked))
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, state: Qt.CheckState):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def selected_values(self) -> list:
        return [
            self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]


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


class _EmployeeListWorker(QThread):
    """Fetches the active employee list to populate the Employee filter picker."""

    success = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, settings: dict):
        super().__init__()
        self._settings = settings

    def run(self):
        try:
            employees = fetch_employees(self._settings)
        except Exception as exc:
            self.error.emit(f"Employee list query failed ({type(exc).__name__})")
        else:
            self.success.emit(employees)


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
            if not is_configured(self._settings):
                raise RuntimeError("JobBOSS DB is not configured")
            rows = REPORTS[self._report_type].fetch(self._settings, self._filters)
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
        self.customer_filter_btn = None
        self.employee_filter_btn = None
        self.exclude_assemblies_check = None
        self.report_start_date = None
        self.report_end_date = None
        self._available_customers = []
        self._selected_customers = []
        self._available_employees = []
        self._selected_employees = []

        self._db_ready = False
        self._connect_worker = None
        self._report_worker = None
        self._customer_worker = None
        self._employee_worker = None

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
        self.customer_filter_btn = widget.customer_filter_btn
        self.employee_filter_btn = widget.employee_filter_btn
        self.exclude_assemblies_check = widget.exclude_assemblies_check
        self.report_start_date = widget.report_start_date
        self.report_end_date = widget.report_end_date
        # End defaults to today, not "(No Filter)" -- "through today" is the
        # overwhelmingly common upper bound, so this saves a click on every
        # date-filtered report. Start has no equally obvious default, so it
        # stays at reporting_tab.ui's "(No Filter)" sentinel (minimumDate)
        # until the user actually picks one.
        self.report_end_date.setDate(QDate.currentDate())

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
        self.customer_filter_btn.clicked.connect(self._open_customer_picker)
        self.employee_filter_btn.clicked.connect(self._open_employee_picker)
        widget.export_report_btn.clicked.connect(self.export_report)

        # Populated from the reports registry, not reporting_tab.ui's XML --
        # adding a report type means adding a file to modules/reporting/reports/,
        # never touching this .ui file.
        self.report_type_combo.clear()
        self.report_type_combo.addItems(REPORT_TYPES)

        self.report_type_combo.currentTextChanged.connect(self._on_report_type_changed)
        self._on_report_type_changed(self.report_type_combo.currentText())

        return widget

    def _on_report_type_changed(self, report_type: str):
        self._update_filter_enabled_state(report_type)
        # Only reset rows/headers immediately if nothing's in flight -- if a
        # report is still running, leave the old (still internally consistent)
        # headers/rows in place rather than resetting to the new type's empty
        # layout; _on_report_rows() applies the correct headers for whichever
        # report actually completes, using the type that was really queried.
        if self._report_worker is None or not self._report_worker.isRunning():
            self.report_table.setRowCount(0)
            self._update_table_headers(report_type)

    def _update_filter_enabled_state(self, report_type: str):
        """Grey out the Customer/Employee/Date filters when the selected
        report type doesn't use them, instead of silently ignoring whatever's
        set.
        """
        report_def = REPORTS[report_type]
        self.customer_filter_btn.setEnabled(report_def.uses_customer_filter)
        self.employee_filter_btn.setEnabled(report_def.uses_employee_filter)
        self.exclude_assemblies_check.setEnabled(report_def.uses_exclude_assemblies)
        self.report_start_date.setEnabled(report_def.uses_dates)
        self.report_end_date.setEnabled(report_def.uses_dates)

    def _report_columns(self, report_type: str) -> tuple:
        """The row-dict keys to pull into report_table, in column order, for report_type."""
        return REPORTS[report_type].columns

    def _update_table_headers(self, report_type: str):
        """Apply the headers/column count/resize mode the registered report
        declares for itself -- every report type owns its own headers now, no
        shared fallback.
        """
        report_def = REPORTS[report_type]
        headers = report_def.headers

        self.report_table.setColumnCount(len(headers))
        for col, label in enumerate(headers):
            self.report_table.setHorizontalHeaderItem(col, QTableWidgetItem(label))

        # Stretch-to-fit reads fine for 5 columns but crams Job Report's 16
        # into illegibly narrow slivers -- Interactive lets the user resize
        # and scroll instead.
        resize_mode = (QHeaderView.ResizeMode.Interactive if report_def.resize_mode == "interactive"
                       else QHeaderView.ResizeMode.Stretch)
        self.report_table.horizontalHeader().setSectionResizeMode(resize_mode)

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
            self._load_employee_list()
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
        # Guard against Connect -> Disconnect -> Connect faster than the
        # distinct-customer query finishes: replacing self._customer_worker
        # while the old one is still running drops its only reference (it has
        # no Qt parent), and Qt aborts the process on "destroyed while thread
        # is still running" once that worker's run() eventually finishes.
        if self._customer_worker is not None and self._customer_worker.isRunning():
            return
        self._customer_worker = _CustomerListWorker(self._jobboss_settings())
        self._customer_worker.success.connect(self._on_customers_loaded)
        self._customer_worker.error.connect(
            lambda msg: self.log_message(f"Reporting: {msg}")
        )
        self._customer_worker.start()

    def _on_customers_loaded(self, customers: list):
        self._available_customers = customers
        # Drop any previously-selected customer that's no longer in the list
        # (e.g. reconnected to a different JobBOSS DB) rather than silently
        # filtering on a name that can never match again.
        customer_set = set(customers)
        self._selected_customers = [c for c in self._selected_customers if c in customer_set]
        self._update_customer_filter_button_text()

    def _open_customer_picker(self):
        items = [(name, name) for name in self._available_customers]
        dialog = _CustomerPickerDialog(
            items, self._selected_customers, self._widget,
            title="Select Customers", noun="Customers")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_customers = dialog.selected_values()
            self._update_customer_filter_button_text()

    def _update_customer_filter_button_text(self):
        n = len(self._selected_customers)
        if n == 0:
            text = "Customers: All"
        elif n == 1:
            text = f"Customer: {self._selected_customers[0]}"
        else:
            text = f"Customers: {n} selected"
        self.customer_filter_btn.setText(text)

    def _load_employee_list(self):
        """Populate the Employee filter picker from JobBOSS after a successful connect."""
        if self._employee_worker is not None and self._employee_worker.isRunning():
            return
        self._employee_worker = _EmployeeListWorker(self._jobboss_settings())
        self._employee_worker.success.connect(self._on_employees_loaded)
        self._employee_worker.error.connect(
            lambda msg: self.log_message(f"Reporting: {msg}")
        )
        self._employee_worker.start()

    def _on_employees_loaded(self, employees: list):
        self._available_employees = employees
        codes = {e['code'] for e in employees}
        self._selected_employees = [c for c in self._selected_employees if c in codes]
        self._update_employee_filter_button_text()

    def _open_employee_picker(self):
        items = [(e['code'], f"{e['name']} ({e['code']})") for e in self._available_employees]
        dialog = _CustomerPickerDialog(
            items, self._selected_employees, self._widget,
            title="Select Employees", noun="Employees")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_employees = dialog.selected_values()
            self._update_employee_filter_button_text()

    def _employee_name_by_code(self) -> dict:
        return {e['code']: e['name'] for e in self._available_employees}

    def _update_employee_filter_button_text(self):
        n = len(self._selected_employees)
        if n == 0:
            text = "Employees: All"
        elif n == 1:
            name = self._employee_name_by_code().get(self._selected_employees[0], self._selected_employees[0])
            text = f"Employee: {name}"
        else:
            text = f"Employees: {n} selected"
        self.employee_filter_btn.setText(text)

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
        """Generate a report by querying the JobBOSS DB on a background thread.

        One generic filter-building block driven by the report's declared
        flags (base.ReportDefinition) -- a new report type with any
        combination of these flags needs no new code here.
        """
        if not self._db_ready:
            self.show_error("Not Connected", "Click \"Connect to Database\" first.")
            return

        report_type = self.report_type_combo.currentText()
        report_def = REPORTS[report_type]
        filters = {}

        if report_def.uses_customer_filter and self._selected_customers:
            filters['customers'] = list(self._selected_customers)
        if report_def.uses_employee_filter and self._selected_employees:
            filters['employees'] = list(self._selected_employees)
        if report_def.uses_exclude_assemblies and self.exclude_assemblies_check.isChecked():
            filters['exclude_assemblies'] = True

        if report_def.uses_dates:
            start = self._picked_date(self.report_start_date)
            end = self._picked_date(self.report_end_date)
            if report_def.dates_required:
                if start is None or end is None:
                    self.show_error(
                        "Invalid Date",
                        "Pick both a Start Date and End Date (double-click a field, or use its "
                        "dropdown arrow, to open the calendar)."
                    )
                    return
                filters['start_date'] = start
                filters['end_date'] = end
            else:
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

        # _last_report_type/_last_filters, not the live combo/field selection
        # -- both can change while this report is still running in the
        # background, and these rows were produced from whatever was actually
        # sent to the worker at generate_report() time.
        report_type = self._last_report_type
        report_def = REPORTS[report_type]
        columns = report_def.columns
        # Apply headers for the report type that was actually queried, not
        # whatever the combo currently shows -- otherwise a combo switch
        # while this query was running leaves stale, mismatched headers/
        # column-count in place and setItem()/the highlight lookup below can
        # silently truncate or index into a None cell.
        self._update_table_headers(report_type)

        self.report_table.setRowCount(0)
        for row in rows:
            r = self.report_table.rowCount()
            self.report_table.insertRow(r)
            for col, key in enumerate(columns):
                self.report_table.setItem(r, col, QTableWidgetItem(row.get(key, '')))
            highlight_key = report_def.row_highlight(row) if report_def.row_highlight else None
            if highlight_key:
                self.report_table.item(r, columns.index(highlight_key)).setBackground(_LATE_FILL_COLOR)

        # Auto-fit columns to their actual content (header + widest cell) now
        # that the table is populated -- Interactive resize mode's default
        # column widths don't reflect content at all, which is what made Job
        # Report's 16 columns read as compacted/truncated. No-op in Stretch
        # mode (the 5-column reports): Stretch always re-fills the viewport
        # width regardless, so this has no lasting visible effect there.
        self.report_table.resizeColumnsToContents()
        for col in range(self.report_table.columnCount()):
            if self.report_table.columnWidth(col) > _MAX_AUTO_COLUMN_WIDTH:
                self.report_table.setColumnWidth(col, _MAX_AUTO_COLUMN_WIDTH)

        self._last_generated_at = datetime.now()
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
        report_def = REPORTS.get(self._last_report_type)
        if report_def and report_def.date_label_when_unset:
            return report_def.date_label_when_unset
        return "N/A"

    def _export_title_block(self) -> list:
        generated = self._last_generated_at
        report_def = REPORTS.get(self._last_report_type)
        rows = [
            ["JobDocs - JobBOSS Reporting"],
            ["Report:", self._last_report_type or ""],
            ["Date Range:", self._date_range_label()],
        ]
        if report_def and report_def.uses_customer_filter:
            customers = self._last_filters.get('customers')
            rows.append(["Customers:", ", ".join(customers) if customers else "All"])
        if report_def and report_def.uses_employee_filter:
            codes = self._last_filters.get('employees')
            name_by_code = self._employee_name_by_code()
            labels = [name_by_code.get(c, c) for c in codes] if codes else []
            rows.append(["Employees:", ", ".join(labels) if labels else "All"])
        rows.append(["Generated:", generated.strftime('%Y-%m-%d %H:%M:%S') if generated else ""])
        rows.append([])
        return rows

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
            f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
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
        safe_rows = [[_neutralize_formula_cell(v) for v in row] for row in data_rows]
        # utf-8-sig, not the platform-default encoding (cp1252 on Windows) --
        # a customer name or note containing a character outside cp1252 would
        # otherwise raise UnicodeEncodeError and fail the export; the BOM also
        # makes Excel itself open the file as UTF-8 instead of guessing wrong.
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerows(self._export_title_block())
            writer.writerow(headers)
            writer.writerows(safe_rows)

    def _export_xlsx(self, file_path: str):
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.table import Table, TableStyleInfo

        title_block = self._export_title_block()
        headers, data_rows = self._export_table_rows()
        # Neutralizing here (not just in _export_csv) matters for xlsx too --
        # openpyxl auto-detects data_type='f' (formula) for any plain string
        # cell value starting with "=", so an unprefixed JobBOSS note would
        # become a *real* live formula, not just something Excel's CSV import
        # heuristically treats as one. Safe to do once, upfront: date/numeric
        # columns never start with a trigger char, so the highlight lookup
        # below (which reads these same data_rows by index) is unaffected.
        data_rows = [[_neutralize_formula_cell(v) for v in row] for row in data_rows]

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        for row in title_block:
            ws.append(row)
        header_row_idx = len(title_block) + 1

        # openpyxl's Table requires non-empty, unique headers -- some report
        # types repurpose blank columns for aggregate data (e.g. Top
        # Customers), so blanks get a placeholder name here; the on-screen
        # report_table is unaffected, this only changes what lands in the file.
        safe_headers = []
        seen = set()
        for i, h in enumerate(headers, start=1):
            name = h.strip() if h and h.strip() else f"Column{i}"
            if name in seen:
                name = f"{name}_{i}"
            seen.add(name)
            safe_headers.append(name)

        ws.append(safe_headers)
        for row in data_rows:
            ws.append(row)

        # Same row_highlight() flag as the on-screen report_table
        # (_on_report_rows) -- reapplied here from the exported string values
        # rather than read back off the QTableWidgetItem brushes, so this
        # stays correct even if someone exports without ever having the tab
        # open. Matched by column KEY (zip report_def.columns with the
        # exported row, same as _on_report_rows), not by header label -- one
        # shared way to find "which column" instead of two.
        report_def = REPORTS.get(self._last_report_type)
        if report_def and report_def.row_highlight and data_rows:
            red_fill = PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid')
            for i, row in enumerate(data_rows):
                row_dict = dict(zip(report_def.columns, row))
                highlight_key = report_def.row_highlight(row_dict)
                if highlight_key and highlight_key in report_def.columns:
                    col_idx = report_def.columns.index(highlight_key)
                    ws.cell(row=header_row_idx + 1 + i, column=col_idx + 1).fill = red_fill

        ws['A1'].font = Font(bold=True, size=12)
        for cell in ws[header_row_idx]:
            cell.font = Font(bold=True)
        for col_cells in ws.columns:
            width = max((len(str(c.value)) for c in col_cells if c.value is not None), default=0)
            ws.column_dimensions[col_cells[0].column_letter].width = max(10, min(40, width + 2))

        # Wrap header + data in a real Excel Table with its AutoFilter, so the
        # exported file opens already sortable/filterable per column in Excel
        # -- not just a plain value dump. Skipped for a header-only (no data
        # rows) export: nothing to sort/filter, and Excel's Table requires at
        # least one row below the header.
        if len(data_rows) > 0:
            last_col_letter = get_column_letter(len(safe_headers))
            table_ref = f"A{header_row_idx}:{last_col_letter}{ws.max_row}"
            table = Table(displayName="ReportTable", ref=table_ref)
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
                showRowStripes=True, showColumnStripes=False,
            )
            ws.add_table(table)

        wb.save(file_path)

    def cleanup(self):
        """Cleanup resources"""
        workers = (self._connect_worker, self._report_worker, self._customer_worker, self._employee_worker)
        for worker in workers:
            if worker is not None and worker.isRunning():
                worker.wait(2000)
