#!/usr/bin/env python3
"""
JobDocs - Modular Blueprint and Job Management System

Main application entry point using the modular plugin architecture.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt

from core.module_loader import ModuleLoader
from core.app_context import AppContext
from shared.utils import get_config_dir, get_os_text


class JobDocsMainWindow(QMainWindow):
    """Main application window with modular plugin system"""

    DEFAULT_SETTINGS = {
        'blueprints_dir': '',
        'customer_files_dir': '',
        'itar_blueprints_dir': '',
        'itar_customer_files_dir': '',
        'link_type': 'hard',
        'blueprint_extensions': ['.pdf', '.dwg', '.dxf'],
        'allow_duplicate_jobs': False,
        'ui_style': 'Fusion',
        'job_folder_structure': '{customer}/{job_folder}/job documents',
        'quote_folder_path': 'Quotes',
        'legacy_mode': True,
        'default_tab': 0,
        'experimental_features': False,
        'db_type': 'mssql',
        'db_host': 'localhost',
        'db_port': 1433,
        'db_name': '',
        'db_username': '',
        'db_password': ''
    }

    def __init__(self):
        super().__init__()

        # Configuration
        self.config_dir = get_config_dir()
        self.settings_file = self.config_dir / 'settings.json'
        self.history_file = self.config_dir / 'history.json'

        self.settings = self.load_settings()
        self.history = self.load_history()
        self.modules = []  # Store loaded modules

        # Setup UI
        self.setWindowTitle("JobDocs")
        self.resize(1200, 800)

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create app context for modules
        self.app_context = AppContext(
            settings=self.settings,
            history=self.history,
            config_dir=self.config_dir,
            save_settings_callback=self.save_settings,
            save_history_callback=self.save_history,
            log_message_callback=self.log_message,
            show_error_callback=self.show_error_dialog,
            show_info_callback=self.show_info_dialog,
            get_customer_list_callback=self.get_customer_list,
            add_to_history_callback=self.add_to_history,
            main_window=self
        )

        # Load modules
        self.load_modules()

        # Setup menu
        self.setup_menu()

        # Apply UI style
        self.apply_ui_style()

        # Set default tab
        default_tab = self.settings.get('default_tab', 0)
        if 0 <= default_tab < self.tabs.count():
            self.tabs.setCurrentIndex(default_tab)

        self.statusBar().showMessage("Ready")

    # ==================== Settings & History ====================

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    merged = self.DEFAULT_SETTINGS.copy()
                    merged.update(settings)
                    return merged
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load settings: {e}")
        return self.DEFAULT_SETTINGS.copy()

    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError as e:
            self.show_error_dialog("Error", f"Failed to save settings: {e}")

    def load_history(self) -> Dict[str, Any]:
        """Load history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load history: {e}")
        return {'customers': {}, 'recent_jobs': []}

    def save_history(self):
        """Save history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except IOError as e:
            self.show_error_dialog("Error", f"Failed to save history: {e}")

    # ==================== Module Loading ====================

    def load_modules(self):
        """Load all modules using the module loader"""
        modules_dir = Path(__file__).parent / 'modules'
        loader = ModuleLoader(modules_dir)

        try:
            # Load modules with experimental flag
            experimental_enabled = self.settings.get('experimental_features', False)
            self.modules = loader.load_all_modules(self.app_context, experimental_enabled)

            if not self.modules:
                QMessageBox.warning(
                    self,
                    "No Modules",
                    "No modules were loaded. Check the modules/ directory."
                )
                return

            # Add each module as a tab
            for module in self.modules:
                try:
                    widget = module.get_widget()
                    name = module.get_name()
                    self.tabs.addTab(widget, name)
                    self.log_message(f"Loaded module: {name}")
                except Exception as e:
                    self.log_message(f"ERROR: Failed to load module {module.__class__.__name__}: {e}")
                    import traceback
                    traceback.print_exc()

            self.statusBar().showMessage(f"Loaded {len(self.modules)} module(s)")

            # Populate customer lists in all modules
            self.populate_customer_lists()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Module Load Error",
                f"Failed to load modules:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    # ==================== Menu ====================

    def setup_menu(self):
        """Setup application menu"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        settings_action = file_menu.addAction("&Settings")
        settings_action.triggered.connect(self.open_settings)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        getting_started_action = help_menu.addAction("&Getting Started")
        getting_started_action.triggered.connect(self.show_getting_started)

        help_menu.addSeparator()

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self.show_about)

    def open_settings(self):
        """Open settings dialog"""
        # Import here to avoid circular dependency
        from settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings
            self.save_settings()
            self.populate_customer_lists()
            QMessageBox.information(self, "Settings", "Settings saved. Please restart for all changes to take effect.")

    def show_getting_started(self):
        """Show getting started guide"""
        folder_term = get_os_text('folder_term')
        path_example = get_os_text('path_example')

        content = f"""
<h2>GETTING STARTED</h2>

<p><b>1. Go to File → Settings</b><br>
<b>2. Configure directories:</b><br>
&nbsp;&nbsp;- Blueprints Directory: Central drawing storage<br>
&nbsp;&nbsp;- Customer Files Directory: Where job {folder_term}s are created<br>
<b>3. Choose link type (Hard Link recommended)</b><br>
<b>4. Set blueprint file extensions</b></p>

<p><b>CREATE JOB TAB</b><br>
Enter job information and drop files to create job {folder_term}s.</p>

<p><b>BULK CREATE TAB</b><br>
Create multiple jobs at once using CSV format.</p>

<p><b>SEARCH TAB</b><br>
Search across all customers and jobs.</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("Getting Started")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(content)
        msg.exec()

    def show_about(self):
        """Show about dialog"""
        folder_term = get_os_text('folder_term')

        content = f"""
<h2>JobDocs</h2>
<p>A modular tool for managing blueprint files and customer job {folder_term}s.</p>

<p><b>Features:</b></p>
<ul>
<li>Plugin-based modular architecture</li>
<li>Quote and job management</li>
<li>Blueprint file organization</li>
<li>ITAR support for controlled documents</li>
<li>Bulk job creation</li>
<li>Advanced search capabilities</li>
</ul>

<p>Built with PyQt6 and the JobDocs Plugin System</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("About JobDocs")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(content)
        msg.exec()

    # ==================== UI Helpers ====================

    def apply_ui_style(self):
        """Apply UI style from settings"""
        style = self.settings.get('ui_style', 'Fusion')
        QApplication.setStyle(style)

    def log_message(self, message: str):
        """Log a message to console and status bar"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.statusBar().showMessage(message, 3000)

    def show_error_dialog(self, title: str, message: str):
        """Show error dialog"""
        QMessageBox.critical(self, title, message)

    def show_info_dialog(self, title: str, message: str):
        """Show information dialog"""
        QMessageBox.information(self, title, message)

    # ==================== Data Helpers ====================

    def get_customer_list(self) -> List[str]:
        """Get list of customers from customer files directory"""
        customers = set()
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            dir_path = self.settings.get(dir_key, '')
            if dir_path and Path(dir_path).exists():
                try:
                    for d in Path(dir_path).iterdir():
                        if d.is_dir():
                            customers.add(d.name)
                except OSError:
                    pass
        return sorted(customers)

    def add_to_history(self, entry_type: str, data: Dict[str, Any]):
        """Add an entry to history"""
        if entry_type == 'job':
            recent_jobs = self.history.get('recent_jobs', [])

            # Add timestamp
            data['date'] = datetime.now().isoformat()

            # Add to front of list
            recent_jobs.insert(0, data)

            # Keep only last 100 entries
            self.history['recent_jobs'] = recent_jobs[:100]

            # Update customer history
            customer = data.get('customer', '')
            if customer:
                if 'customers' not in self.history:
                    self.history['customers'] = {}
                self.history['customers'][customer] = datetime.now().isoformat()

            self.save_history()

    def populate_customer_lists(self):
        """Refresh customer lists in all modules (called after settings change)"""
        # Call populate methods on all loaded modules that have them
        for module in self.modules:
            # Check for populate_*_customer_list methods
            for method_name in dir(module):
                if method_name.startswith('populate_') and method_name.endswith('_customer_list'):
                    method = getattr(module, method_name, None)
                    if callable(method):
                        try:
                            method()
                        except Exception as e:
                            self.log_message(f"Error refreshing {module.get_name()} customer list: {e}")

        self.log_message("Customer lists refreshed")

    def refresh_history(self):
        """Refresh history displays in all modules"""
        # Hook for modules to refresh history displays
        self.log_message("History refreshed")

    # ==================== Job Creation (for Bulk module) ====================

    def create_single_job(self, customer: str, job_number: str, description: str,
                         drawings: List[str], is_itar: bool, quote_files: List[str]) -> bool:
        """
        Create a single job (called by Bulk module).
        This is a simplified version - full implementation would be in Job module.
        """
        try:
            # This is a stub - in reality, the Job module handles job creation
            # The Bulk module calls this to create jobs
            self.add_to_history('job', {
                'customer': customer,
                'job_number': job_number,
                'description': description,
                'drawings': drawings,
                'is_itar': is_itar
            })
            return True
        except Exception as e:
            self.log_message(f"Error creating job {job_number}: {e}")
            return False


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("JobDocs")
    app.setOrganizationName("JobDocs")

    print("=" * 60)
    print("JobDocs - Modular Plugin System")
    print("=" * 60)
    print()

    window = JobDocsMainWindow()
    window.show()

    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
