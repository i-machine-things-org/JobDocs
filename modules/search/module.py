"""
Search Module - Search for Jobs Across Customer Directories

This module provides powerful search functionality across all job folders.
Supports both strict format (fast) and legacy recursive search modes.
Uses background threading to prevent UI lockup during searches.
"""

import atexit
import logging
import os
import shutil
import sys
import re
import ctypes
import tempfile
from pathlib import Path
from datetime import datetime
from types import MappingProxyType
from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QMessageBox, QTableWidgetItem, QApplication, QMenu,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QGroupBox, QVBoxLayout, QCheckBox,
    QDialog, QTableWidget, QDialogButtonBox, QLabel
)
from shared.widgets import FilePreviewWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6 import uic

from core.base_module import BaseModule
from core.search_index import SearchIndex, _parse_job_folder
from shared.utils import open_folder, reveal_in_file_manager, get_config_dir, is_reparse_point
from shared.widgets import print_files_with_dialog

logger = logging.getLogger(__name__)

# Customer-label prefixes that mark a result as ITAR-controlled. Kept as one
# constant so every readonly/ITAR-visibility check stays in sync (CODING_NOTES:
# ITAR / Filter Consistency).
_ITAR_LABEL_PREFIXES = ('[ITAR] ', '[ITAR-BP] ', '[ITAR Quote] ')

# Temp dirs created to view a file on a read-only (search-only) install
# without exposing its real path to the external viewer — see
# SearchModule._open_item_externally(). Cleaned up before each new temp
# copy is made (never more than the most-recently-viewed file's copy sits
# on disk at once) and again via this atexit handler as a fallback, mirroring
# shared/widgets.py's _dropzone_tmp_dirs pattern.
_kiosk_view_tmp_dirs: list = []


def _cleanup_kiosk_view_tmp_dirs() -> None:
    # Called both as the atexit fallback and before every new temp copy, so
    # a successfully-removed path must not be re-walked (and no-op
    # re-rmtree'd) by a later call. But shutil.rmtree(ignore_errors=True)
    # can silently fail to remove a dir the external viewer still has a
    # file open in (a real possibility on Windows, where an open handle
    # blocks deletion) -- popping unconditionally would then forget that
    # path forever, leaking it past both the next open's cleanup and the
    # atexit fallback. Keep only the paths that actually still exist after
    # the attempt, so a failed removal gets retried next time
    # (CodeRabbit, PR #317 promotion review).
    still_present = []
    for d in _kiosk_view_tmp_dirs:
        shutil.rmtree(d, ignore_errors=True)
        if os.path.exists(d):
            still_present.append(d)
    _kiosk_view_tmp_dirs[:] = still_present


atexit.register(_cleanup_kiosk_view_tmp_dirs)


def _is_hidden_file(full_path: str, name: str) -> bool:
    """Return True if the file/folder should be treated as hidden."""
    if name.startswith('.'):
        return True
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(full_path)
        if attrs != -1 and (attrs & 0x2):  # FILE_ATTRIBUTE_HIDDEN
            return True
    except (AttributeError, OSError):
        pass
    return False


class SearchWorker(QThread):
    """Background worker for performing searches without blocking UI"""

    # Signals
    result_found = pyqtSignal(dict)  # Emitted for each search result
    progress_update = pyqtSignal(str)  # Emitted with status updates
    finished = pyqtSignal(int)  # Emitted when search completes with result count

    def __init__(self, dirs_to_search, search_term, strict_mode,
                 search_customer, search_job, search_desc, search_drawing, app_context):
        super().__init__()
        self.dirs_to_search = dirs_to_search
        self.search_term = search_term
        self.strict_mode = strict_mode
        self.search_customer = search_customer
        self.search_job = search_job
        self.search_desc = search_desc
        self.search_drawing = search_drawing
        self.app_context = app_context
        self._is_cancelled = False
        self.result_count = 0

    def cancel(self):
        """Cancel the search"""
        self._is_cancelled = True

    def run(self):
        """Run the search in background"""
        try:
            if self.strict_mode:
                self._strict_search()
            else:
                self._legacy_search()
        except Exception as e:
            self.progress_update.emit(f"Error: {e}")

        self.finished.emit(self.result_count)

    def _strict_search(self):
        """Structured search using parsed folder names"""
        for prefix, base_dir in self.dirs_to_search:
            if self._is_cancelled:
                break

            self.progress_update.emit(f"Searching {prefix if prefix else 'standard'} directories...")

            # BP and IR dirs use filename search, not job folder structure
            if prefix in ('BP', 'ITAR-BP', 'IR'):
                self._file_search(base_dir, prefix)
                continue

            readonly = self.app_context.is_readonly()
            try:
                customers = [
                    d for d in os.listdir(base_dir)
                    if os.path.isdir(os.path.join(base_dir, d))
                    and not (readonly and is_reparse_point(os.path.join(base_dir, d)))
                ]
            except OSError:
                continue

            for customer in customers:
                if self._is_cancelled:
                    break

                customer_path = os.path.join(base_dir, customer)
                display_customer = f"[ITAR] {customer}" if prefix == 'ITAR' else customer

                # Check if searching by customer name
                customer_match = self.search_customer and self.search_term in customer.lower()

                # Find job folders
                scan_errors: List[OSError] = []
                jobs = self.app_context.find_job_folders(
                    customer_path, errors=scan_errors, include_po_number=True,
                )

                for dir_name, job_docs_path, po_number in jobs:
                    if self._is_cancelled:
                        break

                    # Apply strict mode filter
                    if not dir_name or not dir_name[0].isdigit():
                        continue

                    # Parse folder name — shared parser keeps strict-mode results
                    # consistent whether the index is ready or not.
                    job_num, desc, drawings = _parse_job_folder(dir_name)

                    # Check for matches
                    match = customer_match
                    if not match and self.search_job and self.search_term in job_num.lower():
                        match = True
                    if not match and self.search_desc and self.search_term in desc.lower():
                        match = True
                    if not match and self.search_drawing:
                        for drawing in drawings:
                            if self.search_term in drawing.lower():
                                match = True
                                break

                    if match:
                        try:
                            mod_time = datetime.fromtimestamp(Path(job_docs_path).stat().st_mtime)
                        except OSError:
                            mod_time = datetime.now()

                        result = {
                            'date': mod_time,
                            'customer': display_customer,
                            'job_number': job_num,
                            'description': desc,
                            'drawings': drawings,
                            'po_number': po_number,
                            'path': job_docs_path
                        }
                        self.result_found.emit(result)
                        self.result_count += 1

                # find_job_folders requires a specific subfolder (e.g. "job documents")
                # that may not exist.  Fall back to a plain digit-prefixed directory scan
                # whenever no structured jobs were returned, applying the same match logic
                # so searches by job number or description still work on flat layouts.
                if not jobs and not scan_errors:
                    try:
                        for item in sorted(os.listdir(customer_path)):
                            if self._is_cancelled:
                                break
                            item_path = os.path.join(customer_path, item)
                            if not os.path.isdir(item_path) or not item or not item[0].isdigit():
                                continue
                            job_num, desc, drawings = _parse_job_folder(item)
                            match = customer_match
                            if not match and self.search_job and self.search_term in job_num.lower():
                                match = True
                            if not match and self.search_desc and self.search_term in desc.lower():
                                match = True
                            if not match and self.search_drawing and any(
                                self.search_term in d.lower() for d in drawings
                            ):
                                match = True
                            if not match:
                                continue
                            try:
                                mod_time = datetime.fromtimestamp(Path(item_path).stat().st_mtime)
                            except OSError:
                                mod_time = datetime.now()
                            self.result_found.emit({
                                'date': mod_time,
                                'customer': display_customer,
                                'job_number': job_num,
                                'description': desc,
                                'drawings': drawings,
                                'po_number': '',
                                'path': item_path,
                            })
                            self.result_count += 1
                    except OSError:
                        pass

                # Search quotes for this customer.
                display_quote_customer = (
                    f"[ITAR Quote] {customer}" if prefix == 'ITAR' else f"[Quote] {customer}"
                )
                quotes = self.app_context.find_quote_folders(customer_path)
                for quote_name, quote_path in quotes:
                    if self._is_cancelled:
                        break
                    if not (customer_match or self.search_term in quote_name.lower()):
                        continue
                    try:
                        mod_time = datetime.fromtimestamp(Path(quote_path).stat().st_mtime)
                    except OSError:
                        mod_time = datetime.now()
                    self.result_found.emit({
                        'date': mod_time,
                        'customer': display_quote_customer,
                        'job_number': quote_name,
                        'description': '',
                        'drawings': [],
                        'po_number': '',
                        'path': quote_path,
                    })
                    self.result_count += 1

    def _legacy_search(self):
        """Recursive search through all directories"""
        for prefix, base_dir in self.dirs_to_search:
            if self._is_cancelled:
                break
            self.progress_update.emit(f"Searching {prefix if prefix else 'standard'} directories...")
            # BP and IR dirs use filename search, not folder name search
            if prefix in ('BP', 'ITAR-BP', 'IR'):
                self._file_search(base_dir, prefix)
            else:
                self._legacy_recursive_search(base_dir, prefix)

    def _file_search(self, base_dir: str, prefix: str):
        """Search for files by filename within a directory tree (for BP/IR dirs)"""
        try:
            for root, dirs, files in os.walk(base_dir):
                if self._is_cancelled:
                    break
                for filename in files:
                    if self._is_cancelled:
                        break
                    if self.search_term in filename.lower():
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(root, base_dir)
                        path_parts = rel_path.split(os.sep)
                        customer = path_parts[0] if path_parts and path_parts[0] != '.' else ''

                        try:
                            mod_time = datetime.fromtimestamp(Path(file_path).stat().st_mtime)
                        except OSError:
                            mod_time = datetime.now()

                        name_no_ext = os.path.splitext(filename)[0]
                        result = {
                            'date': mod_time,
                            'customer': f"[{prefix}] {customer}" if customer else f"[{prefix}]",
                            'job_number': name_no_ext,
                            'description': rel_path if rel_path != '.' else '',
                            'drawings': [],
                            'po_number': '',
                            'path': root
                        }
                        self.result_found.emit(result)
                        self.result_count += 1
        except Exception:
            pass

    def _legacy_recursive_search(self, base_dir: str, prefix: str):
        """Recursively search all folders in legacy mode"""
        try:
            for root, dirs, files in os.walk(base_dir):
                if self._is_cancelled:
                    break

                folder_name = os.path.basename(root)

                # Try to extract customer from path
                rel_path = os.path.relpath(root, base_dir)
                path_parts = rel_path.split(os.sep)
                customer = path_parts[0] if path_parts and path_parts[0] != '.' else "Unknown"

                # Check if folder name or path contains search term
                if self.search_term in folder_name.lower() or self.search_term in rel_path.lower():
                    # Try to parse folder name for job info
                    parts = folder_name.split('_')
                    job_num = ""
                    desc = ""
                    drawings = []

                    # Try to extract job number
                    for part in parts:
                        if part and part[0].isdigit():
                            job_num = part
                            break

                    # If no structured format, use folder name as description
                    if not job_num:
                        match = re.match(r'^(\d+)', folder_name)
                        if match:
                            job_num = match.group(1)
                            desc = folder_name[len(job_num):].strip(' -_')
                        else:
                            desc = folder_name
                    else:
                        # Parse remaining parts
                        remaining_parts = [p for p in parts if p != job_num]
                        if remaining_parts:
                            if '-' in remaining_parts[-1]:
                                drawings = [d.strip() for d in remaining_parts[-1].split('-') if d.strip()]
                                desc = ' '.join(remaining_parts[:-1])
                            else:
                                desc = ' '.join(remaining_parts)

                    display_customer = f"[{prefix}] {customer}" if prefix else customer

                    try:
                        mod_time = datetime.fromtimestamp(Path(root).stat().st_mtime)
                    except OSError:
                        mod_time = datetime.now()

                    result = {
                        'date': mod_time,
                        'customer': display_customer,
                        'job_number': job_num if job_num else "(no job #)",
                        'description': desc,
                        'drawings': drawings,
                        'po_number': '',
                        'path': root
                    }
                    self.result_found.emit(result)
                    self.result_count += 1
        except Exception:
            # Skip directories that cause errors
            pass


class IndexWorker(QThread):
    """Background thread that builds/updates the search index at startup."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(int)   # emits job count when done

    def __init__(self, index: SearchIndex, cf_dirs, bp_dirs, app_context):
        super().__init__()
        self._index = index
        self._cf_dirs = cf_dirs
        self._bp_dirs = bp_dirs
        self._app_context = app_context
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        self._index.update(
            self._cf_dirs,
            self._bp_dirs,
            self._app_context,
            progress=self.progress.emit,
            cancelled=lambda: self._cancelled,
        )
        self.finished.emit(self._index.job_count())


class FolderNamingCheckWorker(QThread):
    """Background scan for folders that don't match the configured job/PO
    naming convention.

    find_job_folders() already discovers these entries (e.g. a mistyped
    "PO 1001" missing the dash, or unrelated clutter like "New folder"), but
    every consumer of its `jobs` list drops them via a digit-first-char
    filter before they're ever shown anywhere -- found, then silently
    thrown away, with no trace. This surfaces them as an on-demand report
    instead.
    """

    progress_update = pyqtSignal(str)
    finished = pyqtSignal(list, bool)  # (customer_display, path, reason) list, was_cancelled

    def __init__(self, dirs_to_check, app_context):
        super().__init__()
        self.dirs_to_check = dirs_to_check
        self.app_context = app_context
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        results = []
        readonly = self.app_context.is_readonly()
        for prefix, base_dir in self.dirs_to_check:
            if self._is_cancelled:
                break
            self.progress_update.emit(f"Checking {prefix if prefix else 'standard'} directories...")
            try:
                customers = [
                    d for d in os.listdir(base_dir)
                    if os.path.isdir(os.path.join(base_dir, d))
                    and not (readonly and is_reparse_point(os.path.join(base_dir, d)))
                ]
            except OSError:
                continue

            for customer in customers:
                if self._is_cancelled:
                    break
                customer_path = os.path.join(base_dir, customer)
                display_customer = f"[ITAR] {customer}" if prefix == 'ITAR' else customer
                unrecognized: List = []
                try:
                    self.app_context.find_job_folders(
                        customer_path,
                        unrecognized=unrecognized,
                        is_cancelled=lambda: self._is_cancelled,
                    )
                except OSError:
                    continue
                for path, reason in unrecognized:
                    results.append((display_customer, path, reason))

        self.finished.emit(results, self._is_cancelled)


class FolderNamingReportDialog(QDialog):
    """Lists folders flagged by a FolderNamingCheckWorker scan, grouping the
    genuinely unrecognized ones ahead of near-miss PO-naming typos so the
    "wildly wrong" entries are easy to spot rather than buried in the list.
    """

    _REASON_LABELS = {
        'unrecognized folder': 'Unrecognized',
        'near-miss PO folder': 'Near-miss PO folder',
    }
    _SEVERITY_ORDER = {'unrecognized folder': 0, 'near-miss PO folder': 1}

    def __init__(self, parent, results, app_context):
        super().__init__(parent)
        self.app_context = app_context
        self.setWindowTitle("Folder Naming Check")
        self.resize(750, 400)

        layout = QVBoxLayout(self)
        description = QLabel(
            f"Found {len(results)} folder(s) that don't match the configured job/PO "
            "naming convention. \"Unrecognized\" folders are the most likely to need "
            "fixing; \"Near-miss PO folder\" entries look like a typo of the PO "
            "naming convention."
        )
        # Without word wrap, an unwrapped QLabel's minimumSizeHint equals its
        # full single-line text width, silently forcing this whole dialog
        # wider than the resize() call above to fit it on one line -- would
        # get much worse paired with resizeColumnsToContents() below, which
        # sizes the Folder column to the single longest path across every
        # row (a real network path can be huge), ballooning the dialog to
        # match instead of letting the table scroll internally.
        description.setWordWrap(True)
        layout.addWidget(description)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Customer", "Folder", "Issue"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        ordered = sorted(
            results, key=lambda r: (self._SEVERITY_ORDER.get(r[2], 2), r[0], r[1])
        )
        for customer, path, reason in ordered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(customer))
            self.table.setItem(row, 1, QTableWidgetItem(path))
            issue_item = QTableWidgetItem(self._REASON_LABELS.get(reason, reason))
            if reason == 'unrecognized folder':
                issue_item.setForeground(QColor('#c0392b'))
                font = issue_item.font()
                font.setBold(True)
                issue_item.setFont(font)
            self.table.setItem(row, 2, issue_item)

        self.table.resizeColumnsToContents()

        if not self.app_context.is_readonly():
            self.table.doubleClicked.connect(self._on_row_double_clicked)
            self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.accept)
        layout.addWidget(button_box)

    def _row_path(self, row: int) -> Optional[str]:
        path_item = self.table.item(row, 1)
        return path_item.text() if path_item is not None else None

    def _reveal_row(self, row: int):
        path = self._row_path(row)
        if path is None:
            return
        success, error = reveal_in_file_manager(path)
        if not success:
            QMessageBox.warning(self, "Not Found", error)

    def _on_row_double_clicked(self, index):
        """Reveal the double-clicked row's folder in the OS file browser,
        highlighted in its containing directory.

        Not connected at all on a read-only (search-only) install -- see
        _open_item_externally()'s own docstring for why a kiosk build must
        never launch Explorer on a directory.
        """
        self._reveal_row(index.row())

    def _show_context_menu(self, pos):
        """Right-click menu mirroring the double-click reveal action, plus
        Copy Path -- same two actions and same readonly gate (never
        connected at all on a read-only install) as show_search_context_menu().
        """
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        path = self._row_path(row)
        if path is None:
            return

        menu = QMenu(self)
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._reveal_row(row))
        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(path))
        menu.exec(self.table.viewport().mapToGlobal(pos))


class SearchModule(BaseModule):
    """Module for searching jobs across customer directories"""

    _PLACEHOLDER_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self):
        super().__init__()
        self._widget = None
        self.search_results: List[Dict[str, Any]] = []
        self._worker = None       # Background search worker
        self._index_worker = None  # Background index builder
        self._naming_worker: Optional[FolderNamingCheckWorker] = None
        # Bumped whenever a naming scan is cancelled/torn down, so queued
        # progress_update/finished deliveries already posted to the event
        # loop before that point (disconnect() does not un-queue them -- Qt
        # only guarantees it stops *future* emissions from being queued) get
        # ignored by the slots below instead of overwriting freshly-reset UI
        # state with stale text.
        self._naming_scan_id = 0
        self._index: Optional[SearchIndex] = None
        self._index_failures = 0  # consecutive query errors
        self._index_query_failed = False  # True if the most recent query raised
        self._sort_column: int = 0   # 0 = Date
        self._sort_ascending: bool = False  # newest first

        # Widget references
        self.search_edit = None
        self.search_table = None
        self.search_status_label = None
        self.search_progress = None
        self.search_customer_check = None
        self.search_job_check = None
        self.search_desc_check = None
        self.search_drawing_check = None
        self.search_all_radio = None
        self.search_strict_radio = None
        self.search_blueprints_check = None
        self.mode_row_widget = None
        self.legacy_options_widget = None
        self.search_btn = None
        self.cancel_btn = None
        self.folder_tree = None
        self.file_preview: FilePreviewWidget | None = None

    def get_name(self) -> str:
        return "Search"

    def get_order(self) -> int:
        return 50  # Fifth tab

    def initialize(self, app_context):
        super().initialize(app_context)
        # The search index is a local performance cache under config_dir,
        # not a write into shop job/blueprint directories, so read-only
        # installs still build and use it — see
        # core/app_context.py's get_search_index() for the same reasoning.
        try:
            db_path = get_config_dir() / 'search_index.db'
            self._index = SearchIndex(db_path)
        except Exception as exc:
            logger.warning("search: could not open index DB (%s): %s", type(exc).__name__, exc)
            self._index = None

    def start_indexer(self):
        """Start the background index update. Called after the UI is shown."""
        if self._index is None:
            return
        if self._index_worker and self._index_worker.isRunning():
            return

        cf_dirs = self._get_customer_files_dirs()
        bp_dirs = self._get_blueprint_dirs()

        if not cf_dirs and not bp_dirs:
            return

        self._index_worker = IndexWorker(self._index, cf_dirs, bp_dirs, self.app_context)
        self._index_worker.progress.connect(self._on_index_progress)
        self._index_worker.finished.connect(self._on_index_finished)
        self._index_worker.start()

    def rebuild_search_index(self):
        """Force a full re-scan instead of update()'s normal incremental
        skip-if-unchanged behavior -- for when the index is suspected stale
        or wrong. Cancels an indexer already in flight first (same
        cancel()+wait() pattern as cleanup()) since clearing the tables
        while it's mid-write would race its own transaction.

        Must not call start_indexer() if clear_all() couldn't actually
        clear the tables (e.g. lock contention) -- update() would then just
        run its normal incremental scan, silently downgrading a requested
        full rebuild with no visible sign to the user that it didn't
        happen."""
        if self._index is None:
            return
        if self._index_worker and self._index_worker.isRunning():
            self._index_worker.cancel()
            self._index_worker.wait()
        if not self._index.clear_all():
            self.show_error(
                "Rebuild Search Index",
                "Could not rebuild the index right now — the database is busy. Try again shortly."
            )
            return
        self.start_indexer()

    def _on_index_progress(self, msg: str):
        if self.search_status_label and not (self._worker and self._worker.isRunning()):
            self.search_status_label.setText(f"Index: {msg}")

    def _on_index_finished(self, job_count: int):
        if self.search_status_label and not (self._worker and self._worker.isRunning()):
            self.search_status_label.setText(f"Index ready — {job_count} jobs")

    def get_widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._create_widget()
        return self._widget

    def _create_widget(self) -> QWidget:
        """Create the search tab widget"""
        widget = QWidget()

        # Load UI file
        ui_file = self._get_ui_path('search/ui/search_tab.ui')
        uic.loadUi(ui_file, widget)

        # Store widget references
        self.search_edit = widget.search_edit
        self.search_table = widget.search_table
        self.search_status_label = widget.search_status_label
        self.search_progress = widget.search_progress
        self.search_customer_check = widget.search_customer_check
        self.search_job_check = widget.search_job_check
        self.search_desc_check = widget.search_desc_check
        self.search_drawing_check = widget.search_drawing_check
        self.search_all_radio = widget.search_all_radio
        self.search_strict_radio = widget.search_strict_radio
        self.search_blueprints_check = widget.search_blueprints_check
        self.mode_row_widget = widget.mode_row_widget
        self.legacy_options_widget = widget.legacy_options_widget
        self.search_btn = widget.search_btn
        self.cancel_btn = widget.cancel_btn

        # Keep criteria group compact, let results group expand
        widget.layout().setStretchFactor(widget.searchCriteriaGroup, 0)
        widget.layout().setStretchFactor(widget.searchResultsGroup, 1)

        # Build folder contents panel and wrap table in a splitter programmatically
        results_layout = widget.searchResultsGroup.layout()
        results_layout.removeWidget(self.search_table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.search_table)

        folder_group = QGroupBox("Folder Contents")
        folder_layout = QVBoxLayout()
        folder_layout.setContentsMargins(5, 5, 5, 5)
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabels(["Name"])
        self.folder_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.folder_tree.setAlternatingRowColors(True)
        self.folder_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.folder_tree.setRootIsDecorated(True)
        self.folder_tree.setExpandsOnDoubleClick(False)

        self.file_preview = FilePreviewWidget()
        self.file_preview.setMinimumHeight(80)

        contents_splitter = QSplitter(Qt.Orientation.Vertical)
        contents_splitter.addWidget(self.folder_tree)
        contents_splitter.addWidget(self.file_preview)
        contents_splitter.setSizes([200, 180])

        folder_layout.addWidget(contents_splitter)
        folder_group.setLayout(folder_layout)
        splitter.addWidget(folder_group)

        splitter.setSizes([400, 280])
        results_layout.insertWidget(0, splitter)
        results_layout.setStretchFactor(splitter, 1)

        # Setup table properties
        self.search_table.horizontalHeader().setStretchLastSection(True)
        self.search_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self.search_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        header.sectionClicked.connect(self._on_header_clicked)

        # Setup folder tree
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Hide progress bar and cancel button initially
        self.search_progress.hide()
        self.cancel_btn.hide()

        # Connect signals
        self.search_btn.clicked.connect(self.perform_search)
        self.cancel_btn.clicked.connect(self.cancel_search)
        self.search_edit.returnPressed.connect(self.perform_search)
        widget.clear_btn.clicked.connect(self.clear_search)
        self.search_all_radio.toggled.connect(self.update_search_field_checkboxes)
        self.search_strict_radio.toggled.connect(self.update_search_field_checkboxes)
        self.search_table.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_table.doubleClicked.connect(self.open_selected_search_job)
        self.search_table.itemSelectionChanged.connect(
            lambda: self._on_result_selected(self.search_table.currentRow())
        )
        self.folder_tree.doubleClicked.connect(self._on_tree_double_clicked)
        self.folder_tree.customContextMenuRequested.connect(self._show_file_context_menu)
        self.folder_tree.currentItemChanged.connect(self._on_folder_file_selected)
        self.folder_tree.itemExpanded.connect(self._on_tree_item_expanded)

        # Initialize UI state
        self.update_legacy_mode_ui()

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

    # ==================== UI State Management ====================

    def update_search_field_checkboxes(self):
        """Enable/disable field checkboxes based on search mode"""
        is_strict_mode = self.search_strict_radio.isChecked()

        self.search_customer_check.setEnabled(is_strict_mode)
        self.search_job_check.setEnabled(is_strict_mode)
        self.search_desc_check.setEnabled(is_strict_mode)
        self.search_drawing_check.setEnabled(is_strict_mode)

        # legacy_options_widget has no content — keep hidden
        self.legacy_options_widget.hide()

    def update_legacy_mode_ui(self):
        """Show/hide UI elements based on legacy mode setting"""
        is_legacy = self.app_context.get_setting('legacy_mode', True)

        # Show/hide "Search All Folders" option
        if is_legacy:
            self.mode_row_widget.setVisible(True)
        else:
            # Hide mode selection, force Strict Format
            self.mode_row_widget.setVisible(False)
            self.search_strict_radio.setChecked(True)

        # Update checkbox states
        self.update_search_field_checkboxes()

    # ==================== Search Functionality ====================

    def perform_search(self):
        """Perform search — uses SQLite index when available, filesystem walk as fallback."""
        search_term = self.search_edit.text().strip().lower()
        if len(search_term) < 2:
            self.show_error("Search", "Please enter at least 2 characters")
            return

        if self._worker and self._worker.isRunning():
            self.cancel_search()
            return

        self.search_table.setRowCount(0)
        self.search_results.clear()

        strict_mode = self.search_strict_radio.isChecked()
        include_blueprints = self.search_blueprints_check.isChecked()

        customer_dirs = self._get_customer_files_dirs()

        # Build blueprint dirs before the customer_dirs guard so a
        # blueprint-only install (no customer files dir) can still search.
        bp_dirs = self._get_blueprint_dirs() if include_blueprints else []

        if not customer_dirs and not bp_dirs:
            cf_dir = self.app_context.get_setting('customer_files_dir', '')
            itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
            if not cf_dir and not itar_cf_dir:
                self.show_error("Error", "No customer directories configured")
            else:
                self.show_error("Error", "Configured directories do not exist")
            return

        if strict_mode:
            search_customer = self.search_customer_check.isChecked()
            search_job = self.search_job_check.isChecked()
            search_desc = self.search_desc_check.isChecked()
            search_drawing = self.search_drawing_check.isChecked()
        else:
            search_customer = search_job = search_desc = search_drawing = True

        # Index is used for strict mode only. Legacy mode uses the filesystem walk
        # because it has different matching semantics (recursive, rel_path matching).
        index_ready = (
            strict_mode
            and self._index is not None
            and self._index.is_populated()
            and not (self._index_worker and self._index_worker.isRunning())
        )

        if index_ready:
            if self._search_from_index(
                search_term, search_customer, search_job,
                search_desc, search_drawing, include_blueprints,
            ):
                return
            # Index returned 0 results. Trust it — and skip the slow filesystem
            # walk entirely — if every customer directory currently on disk has
            # actually been indexed. Otherwise the index may just not have
            # caught up yet (e.g. a customer folder added after the last
            # background run), so fall back to a live filesystem search. A
            # failed query is not a confirmed zero-result, so never trust
            # coverage in that case — and self._index may now be None (set
            # by _search_from_index after repeated failures).
            if (
                self._index is not None
                and not self._index_query_failed
                and self._index.is_fully_covered(customer_dirs, bp_dirs)
            ):
                self.search_status_label.setText("Found 0 result(s)")
                return

        # --- Fallback: live filesystem walk ---
        dirs_to_search = list(customer_dirs) + bp_dirs

        self.search_progress.setMaximum(0)
        self.search_progress.show()
        self.search_status_label.setText("Searching…")
        self.search_btn.setEnabled(False)
        self.cancel_btn.show()

        self._worker = SearchWorker(
            dirs_to_search, search_term, strict_mode,
            search_customer, search_job, search_desc, search_drawing,
            self.app_context,
        )
        self._worker.result_found.connect(self._on_result_found)
        self._worker.progress_update.connect(self._on_progress_update)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.start()

    def _search_from_index(self, term, search_customer, search_job,
                           search_desc, search_drawing, include_blueprints) -> bool:
        """Query the SQLite index and populate results immediately.

        Returns True if results were found and displayed, False if the caller
        should fall back to a filesystem search.
        """
        try:
            results = self._index.search_jobs(
                term, search_customer, search_job, search_desc, search_drawing,
            )
            results += self._index.search_quotes(term, search_customer)
            if include_blueprints:
                results += self._index.search_bp(term)
        except Exception as exc:
            self._index_failures += 1
            self._index_query_failed = True
            logger.error(
                "search: index query failed (%s): %s (failure %d/3)",
                type(exc).__name__, exc, self._index_failures,
            )
            if self._index_failures >= 3:
                self._index = None  # disable index after repeated failures
            return False

        self._index_failures = 0
        self._index_query_failed = False

        if self.app_context.is_readonly():
            # Defense in depth against a stale local index: a machine
            # previously indexed as a Full install (before being reconfigured
            # to Read-Only) could still have ITAR rows on disk until the next
            # background re-index prunes them. Never display ITAR results on
            # a read-only kiosk regardless of what the index currently holds.
            results = [r for r in results if not r['customer'].startswith(_ITAR_LABEL_PREFIXES)]

        if not results:
            return False

        self.search_results = results
        self._apply_sort()
        self.search_status_label.setText(f"Found {len(results)} result(s)")
        return True

    # ==================== Sorting ====================

    _SORT_KEYS = MappingProxyType({
        0: lambda x: x['date'],
        1: lambda x: x['customer'].lower(),
        2: lambda x: x['job_number'].lower(),
        3: lambda x: x['po_number'].lower(),
        4: lambda x: x['description'].lower(),
        5: lambda x: ', '.join(x['drawings']).lower(),
    })

    def _on_header_clicked(self, column: int):
        selected_row = self.search_table.currentRow()
        selected_path = (
            self.search_results[selected_row]['path']
            if 0 <= selected_row < len(self.search_results)
            else None
        )

        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = column != 0  # date defaults descending, text ascending

        order = Qt.SortOrder.AscendingOrder if self._sort_ascending else Qt.SortOrder.DescendingOrder
        self.search_table.horizontalHeader().setSortIndicator(column, order)
        self._apply_sort(selected_path=selected_path)

    def _apply_sort(self, selected_path=None):
        key = self._SORT_KEYS.get(self._sort_column, lambda x: x['date'])
        self.search_results.sort(key=key, reverse=not self._sort_ascending)
        self._rebuild_table(selected_path)

    def _rebuild_table(self, selected_path=None):
        self.search_table.blockSignals(True)
        try:
            self.search_table.setRowCount(0)
            for result in self.search_results:
                row = self.search_table.rowCount()
                self.search_table.insertRow(row)
                self.search_table.setItem(row, 0, QTableWidgetItem(result['date'].strftime("%Y-%m-%d %H:%M")))
                self.search_table.setItem(row, 1, QTableWidgetItem(result['customer']))
                self.search_table.setItem(row, 2, QTableWidgetItem(result['job_number']))
                self.search_table.setItem(row, 3, QTableWidgetItem(result['po_number']))
                self.search_table.setItem(row, 4, QTableWidgetItem(result['description']))
                self.search_table.setItem(row, 5, QTableWidgetItem(', '.join(result['drawings'])))
        finally:
            self.search_table.blockSignals(False)
        if selected_path is not None:
            for i, result in enumerate(self.search_results):
                if result['path'] == selected_path:
                    self.search_table.selectRow(i)
                    break

    # ==================== Search Control ====================

    def cancel_search(self):
        """Cancel the running search or folder naming check"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.search_status_label.setText("Cancelling search...")
        if self._naming_worker and self._naming_worker.isRunning():
            self._naming_worker.cancel()
            self.search_status_label.setText("Cancelling folder naming check...")

    def check_folder_naming(self):
        """Scan customer directories for folders that don't match the
        configured job/PO naming convention and show them in a report.

        Not reachable through the UI at all on a read-only (search-only)
        kiosk install -- it's a main-menu item (see main.py's setup_menu())
        and that menu bar is never constructed when readonly_mode is set --
        but guarded here too as defense-in-depth (e.g. a stale/queued
        signal), matching every other readonly-gated action in this module.
        A kiosk user can't act on a naming-convention finding anyway (fixing
        it means renaming folders on the actual share), and the report's
        own reveal-in-Explorer actions are already disabled read-only, so
        the whole feature would just be a dead end for that install.
        """
        if self.app_context.is_readonly():
            return
        if self._naming_worker and self._naming_worker.isRunning():
            return

        customer_dirs = self._get_customer_files_dirs()
        if not customer_dirs:
            self.show_error("Error", "No customer directories configured")
            return

        self.cancel_btn.show()
        self.search_status_label.setText("Checking folder names…")

        self._naming_scan_id += 1
        scan_id = self._naming_scan_id
        self._naming_worker = FolderNamingCheckWorker(customer_dirs, self.app_context)
        self._naming_worker.progress_update.connect(
            lambda status, sid=scan_id: self._on_naming_progress_update(status, sid)
        )
        self._naming_worker.finished.connect(
            lambda results, cancelled, sid=scan_id: self._on_naming_check_finished_if_current(
                results, cancelled, sid
            )
        )
        self._naming_worker.start()

    def _on_naming_progress_update(self, status: str, scan_id: int):
        """Slot for FolderNamingCheckWorker.progress_update -- ignores a
        delivery already queued before clear_search()/cleanup() invalidated
        this scan (see _naming_scan_id)."""
        if scan_id != self._naming_scan_id:
            return
        self.search_status_label.setText(status)

    def _on_naming_check_finished_if_current(self, results: list, was_cancelled: bool, scan_id: int):
        """Wrapper connected to FolderNamingCheckWorker.finished -- ignores a
        delivery already queued before clear_search()/cleanup() invalidated
        this scan (see _naming_scan_id), so it can't run against UI state
        that's already been reset or torn down."""
        if scan_id != self._naming_scan_id:
            return
        self._on_naming_check_finished(results, was_cancelled)

    def _on_naming_check_finished(self, results: list, was_cancelled: bool):
        """Slot called when a folder naming check completes"""
        other_worker_active = self._worker and self._worker.isRunning()
        if not other_worker_active:
            self.cancel_btn.hide()

        if was_cancelled:
            # results only reflects customers scanned before cancellation --
            # showing it as "no issues found" or a complete report would be
            # misleading, so skip both and just report that it was cancelled.
            if not other_worker_active:
                self.search_status_label.setText("Folder naming check cancelled")
            return

        if not other_worker_active:
            self.search_status_label.setText("")

        if not results:
            QMessageBox.information(
                self._widget, "Folder Naming Check", "No naming issues found."
            )
            return

        dialog = FolderNamingReportDialog(self._widget, results, self.app_context)
        dialog.exec()

    def _on_result_found(self, result: dict):
        """Slot called when a search result is found"""
        self.search_results.append(result)

        # Add to table immediately
        row = self.search_table.rowCount()
        self.search_table.insertRow(row)
        self.search_table.setItem(row, 0, QTableWidgetItem(result['date'].strftime("%Y-%m-%d %H:%M")))
        self.search_table.setItem(row, 1, QTableWidgetItem(result['customer']))
        self.search_table.setItem(row, 2, QTableWidgetItem(result['job_number']))
        self.search_table.setItem(row, 3, QTableWidgetItem(result['po_number']))
        self.search_table.setItem(row, 4, QTableWidgetItem(result['description']))
        self.search_table.setItem(row, 5, QTableWidgetItem(', '.join(result['drawings'])))

    def _on_progress_update(self, status: str):
        """Slot called with progress updates"""
        self.search_status_label.setText(status)

    def _on_search_finished(self, result_count: int):
        """Slot called when search completes"""
        # Remember selected path so we can restore it after the table is rebuilt
        selected_row = self.search_table.currentRow()
        selected_path = (
            self.search_results[selected_row]['path']
            if 0 <= selected_row < len(self.search_results)
            else None
        )

        self._apply_sort(selected_path=selected_path)

        self.search_progress.hide()
        self.search_btn.setEnabled(True)
        if self._naming_worker and self._naming_worker.isRunning():
            # Leave cancel_btn and the status label alone -- the naming
            # check is still using them.
            return
        self.search_status_label.setText(f"Found {result_count} result(s)")
        self.cancel_btn.hide()

    def clear_search(self):
        """Clear search results and input"""
        # Cancel any running search or folder naming check -- otherwise the
        # scan keeps running with no cancellation control visible (cancel_btn
        # is about to be hidden below) and can still show a report dialog
        # after the user has already cleared the UI.
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        if self._naming_worker and self._naming_worker.isRunning():
            # progress_update/finished are queued cross-thread connections:
            # the worker can emit one (e.g. right as cancel() takes effect)
            # before wait() returns, but Qt only actually delivers it once
            # this method returns control to the event loop -- by which
            # point the UI reset below has already run. disconnect() does
            # NOT un-queue an already-posted delivery (Qt only guarantees it
            # stops *future* emissions from being queued), so bump the scan
            # id first -- _on_naming_progress_update()/
            # _on_naming_check_finished_if_current() check it and drop any
            # delivery that's now stale, instead of clobbering the reset
            # state with old text or a "cancelled" message.
            self._naming_scan_id += 1
            self._naming_worker.cancel()
            self._naming_worker.wait()

        self.search_edit.clear()
        self.search_table.setRowCount(0)
        self.search_results.clear()
        self.folder_tree.clear()
        if self.file_preview is not None:
            self.file_preview.clear()
        self.search_status_label.setText("")
        self.search_progress.hide()
        self.search_btn.setEnabled(True)
        self.cancel_btn.hide()

    # ==================== Helper Methods ====================

    def _get_customer_files_dirs(self):
        """Get list of (prefix, path) tuples for customer file directories.

        A read-only (search-only) install never searches or indexes the ITAR
        customer directory: it's meant for shared/shop-floor kiosk machines
        (see README), which must not surface export-controlled job data.
        """
        dirs = []
        cf_dir = self.app_context.get_setting('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs.append(('', cf_dir))
        if not self.app_context.is_readonly():
            itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
            if itar_cf_dir and os.path.exists(itar_cf_dir):
                dirs.append(('ITAR', itar_cf_dir))
        return dirs

    def _get_blueprint_dirs(self):
        """Get list of (prefix, path) tuples for blueprint directories.

        Same ITAR exclusion as _get_customer_files_dirs() on a read-only
        install — see that docstring.
        """
        keys = [('blueprints_dir', 'BP')]
        if not self.app_context.is_readonly():
            keys.append(('itar_blueprints_dir', 'ITAR-BP'))
        dirs = []
        for key, prefix in keys:
            d = self.app_context.get_setting(key, '')
            if d and os.path.exists(d):
                dirs.append((prefix, d))
        return dirs

    def _is_within_permitted_roots(self, path: str) -> bool:
        """True if path's canonical location is under a currently non-ITAR
        customer/blueprint root.

        Defense-in-depth for _open_item_externally(): the reparse-point
        filter in _populate_tree_level() is the primary guard against a
        junction/symlink escaping a permitted folder, but this catches
        anything that reaches here anyway by resolving the real path (which
        follows symlinks/junctions, unlike the raw path) and checking
        containment directly (CodeRabbit, PR #315).

        Uses os.path.commonpath() rather than a string-prefix check, and
        normcase()s both sides first -- Windows paths are case-insensitive
        and realpath() doesn't normalize case, so "C:\\Foo" and "c:\\foo"
        must still compare equal. commonpath() raises ValueError for paths
        on different drives; that's not a match, not an error.
        """
        real = os.path.normcase(os.path.realpath(path))
        roots = [os.path.realpath(d) for _, d in self._get_customer_files_dirs()]
        roots += [os.path.realpath(d) for _, d in self._get_blueprint_dirs()]
        for root in roots:
            root = os.path.normcase(root)
            try:
                if os.path.commonpath([real, root]) == root:
                    return True
            except ValueError:
                continue  # different drive/mount -- not a match
        return False

    # ==================== Context Menu ====================

    def show_search_context_menu(self, pos):
        """Show context menu on right-click.

        A read-only (search-only) install never offers a way to leave the
        app and browse the filesystem directly (Explorer) or copy a path
        that could be pasted into it — only printing/viewing individual
        files from the folder contents panel (_show_file_context_menu)
        is available. See open_selected_search_job()'s own guard for the
        defense-in-depth check.
        """
        row = self.search_table.currentRow()
        if row < 0:
            return

        if self.app_context.is_readonly():
            return

        menu = QMenu(self._widget)

        open_action = menu.addAction("Open Job Folder")
        open_action.triggered.connect(self.open_selected_search_job)

        open_bp_action = menu.addAction("Open Blueprints Folder")
        open_bp_action.triggered.connect(self.open_selected_blueprints)

        menu.addSeparator()

        copy_action = menu.addAction("Copy Path")
        copy_action.triggered.connect(self.copy_search_path)

        menu.exec(self.search_table.viewport().mapToGlobal(pos))

    def open_selected_search_job(self):
        """Open the selected job folder"""
        if self.app_context.is_readonly():
            # Defense in depth: the context menu doesn't offer this action on
            # read-only (search-only) installs, but double-click also routes
            # here, and the menu is data (still built even if never shown) —
            # never launch Explorer even if somehow reached.
            return
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            if os.path.exists(path):
                open_folder(path)
            else:
                self.show_error("Not Found", f"Folder not found: {path}")

    def open_selected_blueprints(self):
        """Open the blueprints folder for the selected job's customer"""
        if self.app_context.is_readonly():
            return
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            raw_customer = self.search_results[row]['customer']
            # Strip all known prefixes to get the bare customer name
            for prefix in ('[ITAR] ', '[ITAR-BP] ', '[BP] ', '[IR] ', '[Quote] ', '[ITAR Quote] '):
                raw_customer = raw_customer.replace(prefix, '')
            customer = raw_customer.strip()

            if not customer:
                self.show_error("Not Found", "Could not determine customer for this result")
                return

            customer_label = self.search_results[row]['customer']
            is_itar = customer_label.startswith(_ITAR_LABEL_PREFIXES)
            bp_dir = self.app_context.get_setting('itar_blueprints_dir' if is_itar else 'blueprints_dir', '')
            if bp_dir:
                customer_bp = os.path.join(bp_dir, customer)
                if os.path.exists(customer_bp):
                    open_folder(customer_bp)
                else:
                    self.show_error("Not Found", f"Blueprints for {customer} not found")

    def copy_search_path(self):
        """Copy the selected result's path to clipboard"""
        if self.app_context.is_readonly():
            return
        row = self.search_table.currentRow()
        if 0 <= row < len(self.search_results):
            path = self.search_results[row]['path']
            QApplication.clipboard().setText(path)
            self.search_status_label.setText("Path copied to clipboard")

    # ==================== Folder Contents Panel ====================

    def _on_folder_file_selected(self, current, previous):
        """Preview the file selected in the folder tree"""
        if self.file_preview is None:
            return
        if current is None:
            self.file_preview.clear()
            return
        path = current.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_preview.preview_file(path)
        else:
            self.file_preview.clear()

    def _on_result_selected(self, row: int):
        """Populate folder tree when a search result row is selected"""
        self.folder_tree.clear()
        if self.file_preview is not None:
            self.file_preview.clear()
        if row < 0 or row >= len(self.search_results):
            return

        path = self.search_results[row]['path']
        if not os.path.exists(path):
            item = QTreeWidgetItem(["(folder not found)"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.folder_tree.addTopLevelItem(item)
            return

        self._populate_tree_level(self.folder_tree.invisibleRootItem(), path)

    def _populate_tree_level(self, parent_item, dir_path: str):
        """Read one level of dir_path and add children to parent_item.
        Subdirectories get a placeholder child so Qt shows the expand arrow.

        On a read-only (search-only) install, symlinks/junctions are
        excluded entirely rather than followed — one planted under a
        permitted customer/blueprint folder could otherwise point at the
        excluded ITAR directory (or anywhere else) and bypass the
        exclusion (CodeRabbit, PR #315).

        Also validates dir_path itself before listing it, not just its
        children: recursive calls via _on_tree_item_expanded() only ever
        reach an already-filtered child, but the *root* call from
        _on_result_selected() passes a search result's path directly —
        live or index-derived, so a stale or reparse-point path there
        would otherwise have its contents listed before any check ran
        (CodeRabbit, PR #315).
        """
        readonly = self.app_context.is_readonly()
        if readonly and (is_reparse_point(dir_path) or not self._is_within_permitted_roots(dir_path)):
            return
        try:
            raw = os.listdir(dir_path)
        except OSError:
            return

        entries = sorted(
            [
                n for n in raw
                if not _is_hidden_file(os.path.join(dir_path, n), n)
                and not (readonly and is_reparse_point(os.path.join(dir_path, n)))
            ],
            key=lambda n: (not os.path.isdir(os.path.join(dir_path, n)), n.lower()),
        )

        for name in entries:
            full_path = os.path.join(dir_path, name)
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            if os.path.isdir(full_path):
                placeholder = QTreeWidgetItem([""])
                placeholder.setData(0, self._PLACEHOLDER_ROLE, True)
                item.addChild(placeholder)
            parent_item.addChild(item)

    def _on_tree_item_expanded(self, item):
        """Lazy-load children when a directory node is expanded for the first time."""
        if item.childCount() != 1:
            return
        child = item.child(0)
        if not child.data(0, self._PLACEHOLDER_ROLE):
            return
        item.removeChild(child)
        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if dir_path and os.path.isdir(dir_path):
            self._populate_tree_level(item, dir_path)

    def _on_tree_double_clicked(self, index):
        """Expand/collapse directories in-tree; open files externally.

        Delegates file-opening to _open_item_externally() rather than
        calling QDesktopServices directly, so the read-only temp-copy
        guard applies here too, not just from the context menu.
        """
        item = self.folder_tree.itemFromIndex(index)
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        if os.path.isdir(path):
            item.setExpanded(not item.isExpanded())
        else:
            self._open_item_externally(item)

    def _open_item_externally(self, item):
        """Open the given tree item's path in the OS.

        Refuses directories on a read-only (search-only) install: opening a
        directory via QDesktopServices launches Explorer on Windows, which
        is exactly the filesystem access a kiosk install must not offer.

        Files open from a temp copy on a read-only install, never the
        original path: the external viewer's own "Save As" / "Recent
        Files" would otherwise hand the user the real customer network
        path, working around every other restriction in this module. The
        previous temp copy (if any) is removed before making a new one —
        a kiosk left running for days must not accumulate one plaintext
        copy of every document ever viewed that session — with the
        _cleanup_kiosk_view_tmp_dirs atexit handler as a fallback for
        whichever copy is still open when the process exits, since
        QDesktopServices hands off to the OS shell association, not a
        process JobDocs can track to know when the viewer closes.

        Also refuses a path whose canonical location resolves outside the
        currently permitted (non-ITAR) roots — see
        _is_within_permitted_roots() — as defense-in-depth against a
        symlink/junction that reached this far anyway (CodeRabbit, PR #315).
        """
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            return
        readonly = self.app_context.is_readonly()
        if readonly and not self._is_within_permitted_roots(path):
            return
        if readonly and os.path.isdir(path):
            return
        if readonly and os.path.isfile(path):
            _cleanup_kiosk_view_tmp_dirs()
            try:
                tmp_dir = tempfile.mkdtemp(prefix='jobdocs_kiosk_view_')
                _kiosk_view_tmp_dirs.append(tmp_dir)
                tmp_path = os.path.join(tmp_dir, os.path.basename(path))
                shutil.copy2(path, tmp_path)
            except OSError as exc:
                logger.warning(
                    "_open_item_externally: temp copy failed (%s): %s", type(exc).__name__, exc
                )
                self.show_error("Error", f"Could not open file: {exc}")
                return
            path = tmp_path
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_file_context_menu(self, pos):
        """Context menu for the folder tree.

        A read-only (search-only) install only offers printing and opening
        individual files in their viewer — never "Open" on a directory
        (Explorer) or "Copy Path" (pasteable into Explorer's address bar).
        """
        item = self.folder_tree.itemAt(pos)
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        is_file = os.path.isfile(path)
        readonly = self.app_context.is_readonly()

        if readonly and not is_file:
            return  # nothing this install may offer for a directory

        menu = QMenu(self._widget)

        # Always valid here: the guard above already returned for the one
        # case that wouldn't be (a directory on a read-only install).
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._open_item_externally(item))

        if not readonly:
            copy_action = menu.addAction("Copy Path")
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(path))

        if is_file:
            menu.addSeparator()
            print_action = menu.addAction("Print Selected")
            print_action.triggered.connect(self._print_selected_folder_files)
            # "Blueprints Path" hard-links the file into the blueprints folder
            # (and can persist a settings change) — not available on read-only
            # (search-only) installs. See _blueprints_path_action()'s own
            # readonly_mode guard for the defense-in-depth check.
            if not readonly:
                bp_action = menu.addAction("Blueprints Path")
                bp_action.triggered.connect(lambda: self._blueprints_path_action(path))

        menu.exec(self.folder_tree.viewport().mapToGlobal(pos))

    def _print_selected_folder_files(self):
        """Print all selected files from the folder tree.

        Same permitted-roots check as _open_item_externally() on a
        read-only (search-only) install — printing reads file content just
        like opening does, so it needs the same defense-in-depth against a
        symlink/junction that reached the tree anyway (CodeRabbit, PR #315).
        """
        readonly = self.app_context.is_readonly()
        paths = []
        for item in self.folder_tree.selectedItems():
            p = item.data(0, Qt.ItemDataRole.UserRole)
            if p and os.path.isfile(p) and (not readonly or self._is_within_permitted_roots(p)):
                paths.append(p)
        if paths:
            print_files_with_dialog(paths, self._widget, self.app_context)

    def _get_customer_bp_info(self):
        """Return (customer_name, blueprints_dir) for the currently selected search result."""
        row = self.search_table.currentRow()
        if row < 0 or row >= len(self.search_results):
            return None, None

        raw_customer = self.search_results[row]['customer']
        for prefix in ('[ITAR] ', '[ITAR-BP] ', '[BP] ', '[IR] ', '[Quote] ', '[ITAR Quote] '):
            raw_customer = raw_customer.replace(prefix, '')
        customer = raw_customer.strip()
        if not customer:
            return None, None

        customer_label = self.search_results[row]['customer']
        is_itar = customer_label.startswith(_ITAR_LABEL_PREFIXES)
        bp_dir = self.app_context.get_setting(
            'itar_blueprints_dir' if is_itar else 'blueprints_dir', ''
        )
        return customer, bp_dir or None

    def _blueprints_path_action(self, source_path: str):
        """Hard link file to blueprints folder if not already there, then copy its path."""
        if self.app_context.readonly_mode:
            # Defense in depth: the context menu doesn't offer this action on
            # read-only (search-only) installs, but never perform the write
            # even if this is somehow reached (e.g. a stale/queued signal).
            self.show_error(
                "Read-Only Install",
                "This is a read-only (search-only) install; files cannot be linked "
                "into the blueprints folder."
            )
            return
        customer, bp_dir = self._get_customer_bp_info()
        if not customer or not bp_dir:
            self.show_error("Error", "Blueprints directory not configured or no job selected")
            return

        filename = os.path.basename(source_path)
        dest_dir = os.path.join(bp_dir, customer)
        bp_path = os.path.join(dest_dir, filename)

        did_link = False
        if os.path.exists(bp_path):
            try:
                same = os.path.samefile(source_path, bp_path)
            except OSError:
                same = False
            if not same:
                self.show_error(
                    "Blueprints Conflict",
                    f"A different file named '{filename}' is already linked in the blueprints folder.\n\n"
                    f"Existing: {bp_path}\n"
                    f"Source:   {source_path}\n\n"
                    f"Rename one of the files to avoid the conflict."
                )
                return
        else:
            try:
                os.makedirs(dest_dir, exist_ok=True)
                os.link(source_path, bp_path)
                did_link = True
            except OSError as e:
                import errno as _errno
                if e.errno == _errno.EXDEV:
                    self.show_error(
                        "Hard Link Failed",
                        f"Cannot create a hard link across different drives or filesystems.\n\n"
                        f"Source: {source_path}\n"
                        f"Destination: {bp_path}\n\n"
                        f"Ensure both paths are on the same drive."
                    )
                else:
                    self.show_error("Hard Link Failed", str(e))
                return

        QApplication.clipboard().setText(bp_path)

        if did_link:
            if not self.app_context.get_setting('suppress_bp_link_notification', False):
                msg = QMessageBox(self._widget)
                msg.setWindowTitle("Blueprints Path")
                msg.setText(f"'{filename}' was linked to the blueprints folder.\nPath copied to clipboard.")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                dont_show = QCheckBox("Don't show this again")
                msg.setCheckBox(dont_show)
                result = msg.exec()
                if result == QMessageBox.StandardButton.Ok and dont_show.isChecked():
                    self.app_context.set_setting('suppress_bp_link_notification', True)
                    self.app_context.save_settings()
            else:
                self.search_status_label.setText(f"Linked '{filename}' to blueprints and copied path")
        else:
            self.search_status_label.setText("Blueprints path copied to clipboard")

    def cleanup(self):
        """Cleanup resources"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        if self._index_worker and self._index_worker.isRunning():
            self._index_worker.cancel()
            self._index_worker.wait()
        if self._naming_worker and self._naming_worker.isRunning():
            # See clear_search()'s equivalent guard: a queued delivery could
            # otherwise run after teardown, against widgets that may already
            # be deleted.
            self._naming_scan_id += 1
            self._naming_worker.cancel()
            self._naming_worker.wait()
        self.search_results.clear()
        # Best-effort now, on normal shutdown; the atexit.register fallback
        # in _cleanup_kiosk_view_tmp_dirs still covers a hard exit/crash.
        _cleanup_kiosk_view_tmp_dirs()
