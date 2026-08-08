"""
Application context for sharing resources between core app and modules

The AppContext provides modules with access to shared application state,
settings, and common operations without tight coupling to the main window.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


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
        main_window: Optional[Any] = None,
        readonly_mode: bool = False
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
            readonly_mode: True for a read-only (search-only) install — see
                main.py's _is_readonly_install(). Modules must check this
                (via the readonly_mode property or is_readonly()) before
                performing any filesystem write or persisted settings change,
                since a read-only install still loads the Search module.
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
        self._print_provider = None
        self._readonly_mode = readonly_mode
        self._search_index = None
        self._search_index_failed = False

    @property
    def readonly_mode(self) -> bool:
        """True if this is a read-only (search-only) install.

        Modules must not perform filesystem writes (e.g. creating/linking
        files into shop directories) or persist settings changes when this
        is True.
        """
        return self._readonly_mode

    def is_readonly(self) -> bool:
        """Same as the readonly_mode property; provided for call-site clarity."""
        return self._readonly_mode

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

    def register_print_provider(self, provider) -> None:
        """Register a plugin as the active print provider.

        The provider must implement add_files_to_list(paths: list).
        If a provider is registered, print_files_with_dialog() delegates to it
        instead of using the built-in QPrintDialog.
        """
        self._print_provider = provider

    def get_print_provider(self):
        """Return the registered print provider, or None."""
        return self._print_provider

    def get_search_index(self):
        """Return the shared SearchIndex instance (lazily opened), or None if it
        could not be opened. Points at the same DB file the Search tab's
        background indexer maintains, so callers should check is_populated()
        before relying on results being complete.
        """
        if self._search_index is None and not self._search_index_failed:
            try:
                from core.search_index import SearchIndex
                self._search_index = SearchIndex(self._config_dir / 'search_index.db')
            except Exception as exc:
                logger.warning(
                    "get_search_index: could not open index DB (%s): %s", type(exc).__name__, exc
                )
                self._search_index_failed = True
        return self._search_index

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

    def build_job_path(self, base_dir: str, customer: str, job_folder_name: str, po_number: str = '') -> Path:
        """
        Build job path based on the configured structure template.

        Args:
            base_dir: Base customer files directory
            customer: Customer name
            job_folder_name: Job folder name (e.g., "12345_Description_Drawing")
            po_number: Optional PO number for path template

        Returns:
            Path to the job folder
        """
        structure = self._settings.get('job_folder_structure', '{customer}/{po_number}/{job_folder}')

        # Replace placeholders
        path_str = (
            structure
            .replace('{customer}', customer)
            .replace('{job_folder}', job_folder_name)
            .replace('{po_number}', po_number)
        )

        # Clean up any double slashes from empty placeholders
        path_str = path_str.replace('//', '/')
        # Remove leading/trailing slashes
        path_str = path_str.strip('/')

        # Replace PO number placeholder if present
        if '{po_number}' in path_str:
            path_str = path_str.replace('{po_number}', po_number if po_number else '')

        return Path(base_dir) / path_str

    def find_job_folders(
        self,
        customer_path: str,
        *,
        errors: Optional[List[OSError]] = None,
        include_po_number: bool = False,
    ) -> List[Tuple[str, str]]:
        """
        Find all job folders in a customer directory.

        Args:
            customer_path: Path to customer directory
            include_po_number: If True, each returned tuple is extended with
                the job's PO number (or '' if the structure has no PO folder,
                or the job doesn't sit inside one), i.e.
                (job_name, job_docs_path, po_number).

        Returns:
            List of (job_name, job_docs_path) tuples, or (job_name,
            job_docs_path, po_number) tuples if include_po_number is True.
        """
        structure = self._settings.get('job_folder_structure', '{customer}/{job_folder}/job documents')
        logger.debug("find_job_folders: customer=%s structure=%s", customer_path, structure)

        def _job(name: str, path: str, po_number: str = '') -> Tuple:
            return (name, path, po_number) if include_po_number else (name, path)

        after_customer = structure.split('{customer}/', 1)[-1] if '{customer}/' in structure else structure
        jobs = []

        if after_customer.startswith('{job_folder}/'):
            suffix = after_customer.replace('{job_folder}/', '', 1)
            try:
                for item in os.listdir(customer_path):
                    item_path = os.path.join(customer_path, item)
                    if os.path.isdir(item_path):
                        expected_docs_path = os.path.join(item_path, suffix)
                        if os.path.exists(expected_docs_path):
                            jobs.append(_job(item, expected_docs_path))
            except OSError as e:
                logger.debug("find_job_folders: OSError %s", e)
                if errors is not None:
                    errors.append(e)
        else:
            parts = after_customer.split('{job_folder}')
            if len(parts) == 2:
                prefix = parts[0].strip('/')
                suffix = parts[1].strip('/')

                if '{po_number}' in prefix:
                    # {po_number} may share a path segment with literal text
                    # (e.g. "job documents/PO-{po_number}"), so the text before
                    # it can be part of a directory name, not a full directory
                    # of its own. Split on the last '/' before the placeholder
                    # to separate the real directory path from the per-folder
                    # name prefix/suffix that must be matched against each
                    # PO directory's name rather than joined onto base_path.
                    po_idx = prefix.index('{po_number}')
                    dir_part = prefix[:po_idx]
                    suffix_part = prefix[po_idx + len('{po_number}'):]

                    if '/' in dir_part:
                        base_dir_part, po_name_prefix = dir_part.rsplit('/', 1)
                    else:
                        base_dir_part, po_name_prefix = '', dir_part

                    if '/' in suffix_part:
                        po_name_suffix, post_po = suffix_part.split('/', 1)
                    else:
                        po_name_suffix, post_po = suffix_part, ''

                    base_path = os.path.join(customer_path, base_dir_part) if base_dir_part else customer_path
                    if os.path.exists(base_path):
                        try:
                            for po_dir in sorted(os.listdir(base_path)):
                                po_path = os.path.join(base_path, po_dir)
                                if not os.path.isdir(po_path):
                                    continue

                                matches_po_name = (
                                    (not po_name_prefix or po_dir.startswith(po_name_prefix))
                                    and (not po_name_suffix or po_dir.endswith(po_name_suffix))
                                )
                                handled_as_po_container = False
                                if matches_po_name:
                                    sub_path = os.path.join(po_path, post_po) if post_po else po_path
                                    if os.path.exists(sub_path):
                                        handled_as_po_container = True
                                        po_number_end = (
                                            len(po_dir) - len(po_name_suffix) if po_name_suffix else len(po_dir)
                                        )
                                        po_number = po_dir[len(po_name_prefix):po_number_end]
                                        for item in sorted(os.listdir(sub_path)):
                                            item_path = os.path.join(sub_path, item)
                                            if os.path.isdir(item_path):
                                                if suffix:
                                                    expected_docs_path = os.path.join(item_path, suffix)
                                                    if os.path.exists(expected_docs_path):
                                                        jobs.append(_job(item, expected_docs_path, po_number))
                                                else:
                                                    jobs.append(_job(item, item_path, po_number))

                                if not handled_as_po_container:
                                    # Doesn't match the PO folder's naming convention (or its
                                    # expected sub-path is missing) — datasets that predate PO
                                    # folders being added have job folders sitting directly here
                                    # instead of nested one level down. Treat this entry as a job
                                    # folder itself so it isn't silently skipped. Still just the
                                    # two shallow os.listdir() calls above, no recursive walk.
                                    if suffix:
                                        expected_docs_path = os.path.join(po_path, suffix)
                                        if os.path.exists(expected_docs_path):
                                            jobs.append(_job(po_dir, expected_docs_path))
                                    else:
                                        jobs.append(_job(po_dir, po_path))
                        except OSError as e:
                            logger.debug("find_job_folders: OSError enumerating PO dirs: %s", e)
                            if errors is not None:
                                errors.append(e)
                else:
                    prefix_path = os.path.join(customer_path, prefix) if prefix else customer_path
                    if os.path.exists(prefix_path):
                        try:
                            for item in os.listdir(prefix_path):
                                item_path = os.path.join(prefix_path, item)
                                if os.path.isdir(item_path):
                                    if suffix:
                                        expected_docs_path = os.path.join(item_path, suffix)
                                        if os.path.exists(expected_docs_path):
                                            jobs.append(_job(item, expected_docs_path))
                                    else:
                                        jobs.append(_job(item, item_path))
                        except OSError as e:
                            logger.debug("find_job_folders: OSError: %s", e)
                            if errors is not None:
                                errors.append(e)

        logger.debug("find_job_folders: returning %d jobs from %s", len(jobs), customer_path)
        return jobs

    def find_quote_folders(self, customer_path: str) -> List[Tuple[str, str]]:
        """
        Find all quote folders in a customer directory.
        Quotes are located in customer/{quote_folder_path}/quote_folders

        Args:
            customer_path: Path to customer directory

        Returns:
            List of (quote_name, quote_path) tuples
        """
        quote_folder_path = self._settings.get('quote_folder_path', 'Quotes')
        quotes_dir = os.path.join(customer_path, quote_folder_path)

        quotes = []

        if os.path.exists(quotes_dir):
            try:
                items = os.listdir(quotes_dir)
                for item in items:
                    item_path = os.path.join(quotes_dir, item)
                    if os.path.isdir(item_path):
                        quotes.append((item, item_path))
            except OSError:
                pass

        return quotes
