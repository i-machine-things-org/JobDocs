"""
Base module interface for JobDocs modular architecture

All tab modules must inherit from BaseModule and implement required methods.
This enables dynamic loading and ensures consistent behavior across modules.
"""

from abc import ABC, abstractmethod
from typing import Optional
from PyQt6.QtWidgets import QWidget


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
