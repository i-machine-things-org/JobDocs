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
        """Refresh history table from history data (jobs and quotes, newest first)"""
        self.history_table.setRowCount(0)

        entries = (
            [('Job', job) for job in self.app_context.history.get('recent_jobs', [])]
            + [('Quote', quote) for quote in self.app_context.history.get('recent_quotes', [])]
        )

        def _sort_key_and_date(entry):
            # Entries can mix naive and offset-aware ISO strings (e.g. a
            # synced entry with a "+00:00" suffix next to a locally-written
            # naive one), and datetime objects with different
            # tzinfo-awareness raise TypeError when compared directly
            # during sort(). Parsed once here and reused for both the sort
            # key (a timestamp float, always comparable regardless of
            # awareness) and the display string.
            try:
                parsed = datetime.fromisoformat(entry.get('date') or '')
                return parsed.timestamp(), parsed.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError, OSError, OverflowError):
                return float('-inf'), "Unknown"

        # (timestamp_for_sort, display_date, kind, entry) -- an unparseable
        # date sorts last (-inf) and displays as "Unknown" rather than
        # raising or silently dropping the row.
        rows = []
        for kind, entry in entries:
            sort_key, date = _sort_key_and_date(entry)
            rows.append((sort_key, date, kind, entry))

        rows.sort(key=lambda r: r[0], reverse=True)

        for _sort_key, date, kind, entry in rows:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            number = entry.get('job_number', '') or entry.get('quote_number', '')

            self.history_table.setItem(row, 0, QTableWidgetItem(date))
            self.history_table.setItem(row, 1, QTableWidgetItem(kind))
            self.history_table.setItem(row, 2, QTableWidgetItem(entry.get('customer', '')))
            self.history_table.setItem(row, 3, QTableWidgetItem(number))
            self.history_table.setItem(row, 4, QTableWidgetItem(entry.get('po_number', '')))
            self.history_table.setItem(row, 5, QTableWidgetItem(entry.get('description', '')))
            self.history_table.setItem(row, 6, QTableWidgetItem(', '.join(entry.get('drawings', []))))

    def clear_history(self):
        """Clear all job and quote history after confirmation"""
        reply = QMessageBox.question(
            self._widget,
            "Confirm",
            "Clear all history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear every recent_* collection (add_to_history() stores
            # plugin entry types the same way, e.g. 'recent_my_entry_types' —
            # not just the built-in recent_jobs/recent_quotes), not just
            # the ones this module happens to know about.
            for history_key, entries in tuple(self.app_context.history.items()):
                if history_key.startswith('recent_') and isinstance(entries, list):
                    self.app_context.history[history_key] = []
            self.app_context.history['customers'] = {}
            self.app_context.save_history()
            self.refresh_history()
            self.show_info("History", "History cleared")

    def cleanup(self):
        """Cleanup resources"""
        pass
