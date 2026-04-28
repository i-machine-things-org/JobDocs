"""
Base module interface for JobDocs modular architecture

All tab modules must inherit from BaseModule and implement required methods.
This enables dynamic loading and ensures consistent behavior across modules.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from PyQt6.QtWidgets import QMessageBox, QWidget


class BaseModule(ABC):
    """
    Abstract base class for all JobDocs modules.

    Each module represents a tab in the application and provides
    its own UI and functionality while accessing shared application
    context for settings, history, and common operations.
    """

    def __init__(self):
        """Initialize the module"""
        self._app_context = None
        self._widget = None

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the display name for this module's tab.

        Returns:
            str: The tab name to display in the UI
        """
        pass

    @abstractmethod
    def get_widget(self) -> QWidget:
        """
        Return the widget to display in the tab.

        This method should create and return the main widget for this module.
        The widget will be added to the tab widget in the main window.

        Returns:
            QWidget: The widget to display in this module's tab
        """
        pass

    @abstractmethod
    def initialize(self, app_context):
        """
        Initialize the module with application context.

        This method is called once when the module is loaded, before the
        widget is created. Use this to set up any connections, load data,
        or perform other initialization tasks.

        Args:
            app_context: AppContext object providing access to shared
                        application resources and callbacks
        """
        self._app_context = app_context

    def is_tab_module(self) -> bool:
        """
        Indicate whether this module should appear as a top-level tab.

        Modules that return False are still loaded (accessible via
        app_context.main_window.modules) but are not added to the tab bar.

        Returns:
            bool: True to show as a tab (default), False to load silently
        """
        return True

    def is_experimental(self) -> bool:
        """
        Indicate if this is an experimental module.

        Experimental modules are only loaded when experimental features
        are enabled in settings.

        Returns:
            bool: True if experimental, False otherwise (default)
        """
        return False

    def get_order(self) -> int:
        """
        Return the display order for this module.

        Lower numbers appear first (leftmost tabs).
        Default is 100. Use multiples of 10 to allow easy insertion.

        Suggested order:
            10: Quote
            20: Job
            30: Add to Job
            40: Bulk
            50: Search
            60: Import
            70: History
            80: Reporting

        Returns:
            int: The display order (default 100)
        """
        return 100

    def cleanup(self):
        """
        Cleanup resources when the module is unloaded or app closes.

        Override this method to release resources, close connections,
        save state, etc. This is called when the application is closing
        or when a module is being hot-reloaded.
        """
        pass

    @property
    def app_context(self):
        """
        Get the application context.

        Returns:
            AppContext: The application context object
        """
        return self._app_context

    def log_message(self, message: str):
        """
        Log a message to the application log.

        Args:
            message: The message to log
        """
        if self._app_context:
            self._app_context.log_message(message)

    def show_error(self, title: str, message: str):
        """
        Show an error dialog.

        Args:
            title: The dialog title
            message: The error message
        """
        if self._app_context:
            self._app_context.show_error(title, message)

    def show_info(self, title: str, message: str):
        """
        Show an information dialog.

        Args:
            title: The dialog title
            message: The information message
        """
        if self._app_context:
            self._app_context.show_info(title, message)

    def _check_po_rfq_files(self, newly_added: List[str], files_store: List[str], list_widget) -> None:
        """Scan newly-added files for PO/RFQ signals and prompt the user for each flagged file.

        Only files whose extension matches the configured blueprint extensions are checked —
        non-drawing files (.msg, .docx, etc.) are always documents and need no prompt.
        """
        from shared.utils import classify_document
        bp_exts = [e.lower() for e in self.app_context.get_setting('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])]
        for path in list(newly_added):
            if Path(path).suffix.lower() not in bp_exts:
                continue
            is_flagged, reason = classify_document(path)
            if not is_flagged:
                continue
            filename = Path(path).name
            msg = QMessageBox(self._widget)
            msg.setWindowTitle("PO / RFQ Detected")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(f"'{filename}' appears to be a Purchase Order or RFQ.")
            msg.setInformativeText(
                f"Detected: {reason}\n\n"
                "Save it as a document in the job folder, or remove it from the list?"
            )
            save_btn = msg.addButton("Save as Document", QMessageBox.ButtonRole.AcceptRole)
            remove_btn = msg.addButton("Remove", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(save_btn)
            msg.exec()
            if msg.clickedButton() is remove_btn and path in files_store:
                idx = files_store.index(path)
                files_store.pop(idx)
                list_widget.takeItem(idx)
