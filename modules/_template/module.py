"""
Template Module - Example/Starting Point for New Modules

This is a template for creating new JobDocs modules.
Copy this entire directory and modify to create your own module.

INSTRUCTIONS:
1. Copy modules/_template/ to modules/your_module_name/
2. Rename this file and class appropriately
3. Implement the required methods
4. Create your UI file (or build UI programmatically)
5. That's it! The module loader will automatically discover it
"""

import os
import sys
from pathlib import Path
from typing import List, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PyQt6 import uic

from core.base_module import BaseModule
from shared.widgets import DropZone  # Optional: if you need file drops
from shared.utils import get_os_text  # Optional: if you need OS-specific text


class TemplateModule(BaseModule):
    """
    Template module demonstrating the basic structure.

    Replace this with your module's description.
    """

    def __init__(self):
        """Initialize your module's instance variables"""
        super().__init__()

        # Module-specific data
        self.my_data: List[Any] = []

        # Widget reference (created in get_widget)
        self._widget = None

        # Widget control references (set in _create_widget)
        self.my_label = None
        self.my_button = None

    # ==================== REQUIRED METHODS ====================

    def get_name(self) -> str:
        """
        Return the display name for this module's tab.

        This is what appears in the tab label.
        """
        return "Template"

    def get_order(self) -> int:
        """
        Return the display order for this module.

        Lower numbers appear first (leftmost tabs).

        Suggested order:
            10: Quote
            20: Job
            30: Add to Job
            40: Bulk
            50: Search
            60: Import
            70: History
            80: Reporting
            100+: Custom modules
        """
        return 100  # Adjust this to control tab position

    def initialize(self, app_context):
        """
        Initialize the module with application context.

        Called once when the module is first loaded.
        Use this to set up any connections or load data.

        Args:
            app_context: The application context providing access to:
                - settings (dict)
                - history (dict)
                - save_settings(), save_history()
                - log_message(), show_error(), show_info()
                - get_customer_list()
                - and more...
        """
        super().initialize(app_context)

        # Example: Log that module was initialized
        self.log_message(f"{self.get_name()} module initialized")

        # Example: Access settings
        # my_setting = self.app_context.get_setting('my_key', 'default_value')

    def get_widget(self) -> QWidget:
        """
        Return the widget to display in the tab.

        This is called when the tab is first accessed.
        The widget is cached, so this only runs once.
        """
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    # ==================== OPTIONAL METHODS ====================

    def is_experimental(self) -> bool:
        """
        Indicate if this is an experimental module.

        Experimental modules are only loaded when experimental features
        are enabled in settings.

        Returns:
            False by default. Return True if experimental.
        """
        return False  # Change to True if this is experimental

    def cleanup(self):
        """
        Cleanup resources when module is unloaded or app closes.

        Override this to release resources, close connections, save state, etc.
        """
        # Example cleanup
        self.my_data.clear()

    # ==================== WIDGET CREATION ====================

    def _create_widget(self) -> QWidget:
        """
        Create the tab widget.

        You have two options:
        1. Load from a .ui file (recommended for complex UIs)
        2. Build programmatically (good for simple UIs)

        This template shows both approaches.
        """

        # OPTION 1: Load from .ui file (created with Qt Designer)
        # Uncomment this section if you have a .ui file
        """
        widget = QWidget()
        ui_file = self._get_ui_path('your_module_name/ui/your_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store references to controls
        self.my_label = widget.my_label
        self.my_button = widget.my_button

        # Connect signals
        self.my_button.clicked.connect(self.on_button_click)

        return widget
        """

        # OPTION 2: Build UI programmatically (shown below)
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create controls
        self.my_label = QLabel("Template Module")
        self.my_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        info_label = QLabel(
            "This is a template module.\n\n"
            "To create your own module:\n"
            "1. Copy modules/_template/ to modules/your_name/\n"
            "2. Edit module.py\n"
            "3. Create your UI\n"
            "4. The module will be auto-discovered!"
        )

        self.my_button = QPushButton("Click Me!")
        self.my_button.clicked.connect(self.on_button_click)

        demo_access_button = QPushButton("Demo: Access Settings")
        demo_access_button.clicked.connect(self.demo_access_settings)

        # Add to layout
        layout.addWidget(self.my_label)
        layout.addWidget(info_label)
        layout.addWidget(self.my_button)
        layout.addWidget(demo_access_button)
        layout.addStretch()  # Push everything to the top

        return widget

    def _get_ui_path(self, relative_path: str) -> Path:
        """
        Get the absolute path to a UI file.

        Args:
            relative_path: Path relative to modules/ directory
                          e.g., "my_module/ui/my_tab.ui"

        Returns:
            Absolute Path to the UI file
        """
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            application_path = Path(sys._MEIPASS)
        else:
            # Running as script
            application_path = Path(__file__).parent.parent.parent

        ui_file = application_path / 'modules' / relative_path
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")
        return ui_file

    # ==================== YOUR MODULE'S METHODS ====================

    def on_button_click(self):
        """Example button click handler"""
        self.show_info(
            "Button Clicked",
            "You clicked the button in the template module!"
        )
        self.log_message("Template button was clicked")

    def demo_access_settings(self):
        """Demonstrate accessing application settings"""
        # Access settings
        bp_dir = self.app_context.get_setting('blueprints_dir', 'Not configured')
        cf_dir = self.app_context.get_setting('customer_files_dir', 'Not configured')

        # Get customer list
        customers = self.app_context.get_customer_list()
        customer_count = len(customers)

        # Show info
        message = (
            f"<b>Application Settings:</b><br/>"
            f"Blueprints Dir: {bp_dir}<br/>"
            f"Customer Files Dir: {cf_dir}<br/>"
            f"<br/>"
            f"<b>Customers:</b> {customer_count} total<br/>"
        )

        self.show_info("Settings Demo", message)

    # Add your own methods here for your module's functionality
    # Examples:
    # - def load_data(self): ...
    # - def save_data(self): ...
    # - def process_files(self, files): ...
    # - def search_something(self): ...


# ==================== USAGE EXAMPLES ====================

"""
EXAMPLE 1: Access Settings
---------------------------
def my_method(self):
    # Get a setting with default
    link_type = self.app_context.get_setting('link_type', 'hard')

    # Get directories
    bp_dir, cf_dir = self.app_context.get_directories(is_itar=False)

    # Modify and save settings
    self.app_context.set_setting('my_custom_setting', 'value')
    self.app_context.save_settings()


EXAMPLE 2: Show Dialogs
-----------------------
def my_method(self):
    # Show error
    self.show_error("Error Title", "Error message")

    # Show info
    self.show_info("Success", "Operation completed")

    # Log message (appears in main window's log)
    self.log_message("Processing started...")


EXAMPLE 3: Access History
--------------------------
def my_method(self):
    # Get recent jobs
    recent = self.app_context.history.get('recent_jobs', [])

    # Add to history
    self.app_context.add_to_history('my_entry_type', {
        'key': 'value',
        'timestamp': datetime.now().isoformat()
    })
    self.app_context.save_history()


EXAMPLE 4: Use Shared Utilities
--------------------------------
from shared.utils import (
    parse_job_numbers,
    is_blueprint_file,
    create_file_link,
    sanitize_filename
)

def my_method(self):
    # Parse job numbers (handles ranges like "1-5")
    jobs = parse_job_numbers("1,3,5-7")  # Returns ['1', '3', '5', '6', '7']

    # Check if file is blueprint
    exts = ['.pdf', '.dwg', '.dxf']
    if is_blueprint_file('drawing.pdf', exts):
        # Create file link
        create_file_link(source_path, dest_path, 'hard')


EXAMPLE 5: Access Main Window (use sparingly)
----------------------------------------------
def my_method(self):
    # Get main window reference
    main_window = self.app_context.main_window

    if main_window:
        # Switch to another tab
        main_window.tabs.setCurrentIndex(1)

        # Access another module's controls
        # (Only do this if absolutely necessary)
        main_window.customer_combo.setCurrentText("ACME Corp")
"""
