"""
History Module - View Recent Job History

This module displays recent job creation history with the ability to clear history.
"""

import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QMessageBox, QTableWidgetItem
from PyQt6.QtCore import QTimer
from PyQt6 import uic

from core.base_module import BaseModule


class HistoryModule(BaseModule):
    """Module for viewing job history"""

    def __init__(self):
        super().__init__()
        self._widget = None
        # Widget references
        self.history_table = None

    def get_name(self) -> str:
        return "History"

    def get_order(self) -> int:
        return 70  # Seventh tab

    def initialize(self, app_context):
        super().initialize(app_context)

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the history tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('history/ui/history_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.history_table = widget.history_table

        # Setup table properties
        self.history_table.horizontalHeader().setStretchLastSection(True)

        # Connect signals
        widget.clear_btn.clicked.connect(self.clear_history)
        widget.refresh_btn.clicked.connect(self.refresh_history)

        # Load history
        QTimer.singleShot(100, self.refresh_history)

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

    # ==================== History Management ====================

    def refresh_history(self):
        """Refresh history table from history data"""
        self.history_table.setRowCount(0)

        for job in self.app_context.history.get('recent_jobs', []):
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            try:
                date = datetime.fromisoformat(job['date']).strftime("%Y-%m-%d %H:%M")
            except Exception:
                date = "Unknown"

            self.history_table.setItem(row, 0, QTableWidgetItem(date))
            self.history_table.setItem(row, 1, QTableWidgetItem(job.get('customer', '')))
            self.history_table.setItem(row, 2, QTableWidgetItem(job.get('job_number', '')))
            self.history_table.setItem(row, 3, QTableWidgetItem(job.get('description', '')))
            self.history_table.setItem(row, 4, QTableWidgetItem(', '.join(job.get('drawings', []))))

    def clear_history(self):
        """Clear all job history after confirmation"""
        reply = QMessageBox.question(
            self._widget,
            "Confirm",
            "Clear all history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear history
            self.app_context.history['customers'] = {}
            self.app_context.history['recent_jobs'] = []
            self.app_context.save_history()
            self.refresh_history()
            self.show_info("History", "History cleared")

    def cleanup(self):
        """Cleanup resources"""
        pass
