"""
Application context for sharing resources between core app and modules

The AppContext provides modules with access to shared application state,
settings, and common operations without tight coupling to the main window.
"""

import os
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional, Tuple


class AppContext:
    """
    Context object passed to all modules providing access to shared resources.

    This enables modules to:
    - Access application settings and history
    - Save settings and history
    - Log messages and show dialogs
    - Access shared data like customer lists
    """

    def __init__(
        self,
        settings: Dict[str, Any],
        history: Dict[str, Any],
        config_dir: Path,
        save_settings_callback: Callable[[], None],
        save_history_callback: Callable[[], None],
        log_message_callback: Callable[[str], None],
        show_error_callback: Callable[[str, str], None],
        show_info_callback: Callable[[str, str], None],
        get_customer_list_callback: Callable[[], List[str]],
        add_to_history_callback: Callable[[str, Dict[str, Any]], None],
        main_window: Optional[Any] = None
    ):
        """
        Initialize the application context.

        Args:
            settings: Application settings dictionary
            history: Application history dictionary
            config_dir: Path to configuration directory
            save_settings_callback: Function to save settings
            save_history_callback: Function to save history
            log_message_callback: Function to log messages
            show_error_callback: Function to show error dialogs
            show_info_callback: Function to show info dialogs
            get_customer_list_callback: Function to get customer list
            add_to_history_callback: Function to add to history
            main_window: Optional reference to main window for advanced use
        """
        self._settings = settings
        self._history = history
        self._config_dir = config_dir
        self._save_settings = save_settings_callback
        self._save_history = save_history_callback
        self._log_message = log_message_callback
        self._show_error = show_error_callback
        self._show_info = show_info_callback
        self._get_customer_list = get_customer_list_callback
        self._add_to_history = add_to_history_callback
        self._main_window = main_window

    @property
    def settings(self) -> Dict[str, Any]:
        """Get application settings dictionary"""
        return self._settings

    @property
    def history(self) -> Dict[str, Any]:
        """Get application history dictionary"""
        return self._history

    @property
    def config_dir(self) -> Path:
        """Get configuration directory path"""
        return self._config_dir

    @property
    def main_window(self) -> Optional[Any]:
        """Get reference to main window (use sparingly)"""
        return self._main_window

    def save_settings(self):
        """Save application settings to disk"""
        self._save_settings()

    def save_history(self):
        """Save application history to disk"""
        self._save_history()

    def log_message(self, message: str):
        """
        Log a message to the application log.

        Args:
            message: The message to log
        """
        self._log_message(message)

    def show_error(self, title: str, message: str):
        """
        Show an error dialog to the user.

        Args:
            title: Dialog title
            message: Error message
        """
        self._show_error(title, message)

    def show_info(self, title: str, message: str):
        """
        Show an information dialog to the user.

        Args:
            title: Dialog title
            message: Information message
        """
        self._show_info(title, message)

    def get_customer_list(self) -> List[str]:
        """
        Get list of customers from customer files directory.

        Returns:
            List of customer names
        """
        return self._get_customer_list()

    def add_to_history(self, entry_type: str, data: Dict[str, Any]):
        """
        Add an entry to the application history.

        Args:
            entry_type: Type of history entry (e.g., 'job', 'quote')
            data: Dictionary containing entry data
        """
        self._add_to_history(entry_type, data)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value with optional default.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """
        Set a setting value.

        Note: This does not automatically save settings.
        Call save_settings() to persist changes.

        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value

    def get_directories(self, is_itar: bool) -> Tuple[Optional[str], Optional[str]]:
        """
        Get blueprints and customer files directories based on ITAR flag.

        Args:
            is_itar: Whether to get ITAR directories

        Returns:
            Tuple of (blueprints_dir, customer_files_dir)
        """
        if is_itar:
            return (
                self._settings.get('itar_blueprints_dir'),
                self._settings.get('itar_customer_files_dir')
            )
        return (
            self._settings.get('blueprints_dir'),
            self._settings.get('customer_files_dir')
        )

    def build_job_path(self, base_dir: str, customer: str, job_folder_name: str) -> Path:
        """
        Build job path based on the configured structure template.

        Args:
            base_dir: Base customer files directory
            customer: Customer name
            job_folder_name: Job folder name (e.g., "12345_Description_Drawing")

        Returns:
            Path to the job folder
        """
        structure = self._settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')

        # Replace placeholders
        path_str = structure.replace('{customer}', customer).replace('{job_folder}', job_folder_name)

        return Path(base_dir) / path_str

    def find_job_folders(self, customer_path: str) -> List[Tuple[str, str]]:
        """
        Find all job folders in a customer directory.

        Args:
            customer_path: Path to customer directory

        Returns:
            List of (job_name, job_docs_path) tuples
        """
        structure = self._settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')
        print(f"[find_job_folders] Customer: {customer_path}", flush=True)
        print(f"[find_job_folders] Structure: {structure}", flush=True)

        # Determine where job_folder appears in the structure relative to customer
        after_customer = structure.split('{customer}/', 1)[-1] if '{customer}/' in structure else structure
        print(f"[find_job_folders] After customer: {after_customer}", flush=True)

        jobs = []

        # Check if job_folder is at the root level after customer
        if after_customer.startswith('{job_folder}/'):
            # New structure: customer/job_folder/...
            suffix = after_customer.replace('{job_folder}/', '', 1)
            print(f"[find_job_folders] Using new structure, suffix: {suffix}", flush=True)
            try:
                items = os.listdir(customer_path)
                print(f"[find_job_folders] Found {len(items)} items in {customer_path}", flush=True)
                for item in items:
                    item_path = os.path.join(customer_path, item)
                    if os.path.isdir(item_path):
                        expected_docs_path = os.path.join(item_path, suffix)
                        print(f"[find_job_folders]   Checking {item} -> {expected_docs_path}", flush=True)
                        if os.path.exists(expected_docs_path):
                            print(f"[find_job_folders]     ✓ Found job: {item}", flush=True)
                            jobs.append((item, expected_docs_path))
                        else:
                            print(f"[find_job_folders]     ✗ Path doesn't exist", flush=True)
            except OSError as e:
                print(f"[find_job_folders] OSError: {e}", flush=True)
        else:
            # Legacy or custom structure
            print(f"[find_job_folders] Using legacy/custom structure", flush=True)
            parts = after_customer.split('{job_folder}')
            if len(parts) == 2:
                prefix = parts[0].strip('/')
                suffix = parts[1].strip('/')
                print(f"[find_job_folders] Prefix: '{prefix}', Suffix: '{suffix}'", flush=True)

                prefix_path = os.path.join(customer_path, prefix) if prefix else customer_path
                print(f"[find_job_folders] Prefix path: {prefix_path}", flush=True)

                if os.path.exists(prefix_path):
                    try:
                        items = os.listdir(prefix_path)
                        print(f"[find_job_folders] Found {len(items)} items in prefix path", flush=True)
                        for item in items:
                            item_path = os.path.join(prefix_path, item)
                            if os.path.isdir(item_path):
                                if suffix:
                                    expected_docs_path = os.path.join(item_path, suffix)
                                    print(f"[find_job_folders]   Checking {item} -> {expected_docs_path}", flush=True)
                                    if os.path.exists(expected_docs_path):
                                        print(f"[find_job_folders]     ✓ Found job: {item}", flush=True)
                                        jobs.append((item, expected_docs_path))
                                    else:
                                        print(f"[find_job_folders]     ✗ Path doesn't exist", flush=True)
                                else:
                                    print(f"[find_job_folders]   Found job (no suffix): {item}", flush=True)
                                    jobs.append((item, item_path))
                    except OSError as e:
                        print(f"[find_job_folders] OSError: {e}", flush=True)
                else:
                    print(f"[find_job_folders] Prefix path doesn't exist!", flush=True)

        print(f"[find_job_folders] Returning {len(jobs)} jobs", flush=True)
        return jobs
