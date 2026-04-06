"""
Reporting Module - Experimental Reporting Features

This module provides experimental reporting functionality with sample data.
Future implementation will connect to database for actual reporting.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QTableWidgetItem, QFileDialog, QHeaderView, QAbstractItemView
)
from PyQt6 import uic

from core.base_module import BaseModule


class ReportingModule(BaseModule):
    """Module for generating and exporting reports"""

    def __init__(self):
        super().__init__()
        self._widget = None
        # Widget references
        self.report_type_combo = None
        self.report_table = None
        self.report_status_label = None

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

        # Setup table properties
        self.report_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.report_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Connect signals
        widget.generate_report_btn.clicked.connect(self.generate_report)
        widget.export_report_btn.clicked.connect(self.export_report)

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

    # ==================== Report Generation ====================

    def generate_report(self):
        """Generate report from database (placeholder with sample data)"""
        report_type = self.report_type_combo.currentText()

        # Clear existing data
        self.report_table.setRowCount(0)

        # Placeholder data
        sample_data = [
            ["2025-01-15", "Acme Corporation", "12345", "Widget Assembly", "Active"],
            ["2025-01-14", "Beta Industries", "54321", "Custom Bracket", "Completed"],
            ["2025-01-13", "Acme Corporation", "12346", "Housing Unit", "Active"],
            ["2025-01-12", "Gamma Systems", "99999", "Shaft Assembly", "Active"],
        ]

        # Populate table with sample data
        for row_data in sample_data:
            row = self.report_table.rowCount()
            self.report_table.insertRow(row)
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                self.report_table.setItem(row, col, item)

        self.report_status_label.setText(
            f"Showing {len(sample_data)} sample records for '{report_type}' (placeholder)\n"
            "To implement: Connect to database and query actual data using db_integration.py"
        )
        self.log_message(f"Generated report: {report_type}")

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
        pass
