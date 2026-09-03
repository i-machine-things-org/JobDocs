"""Tests for SearchModule._search_from_index()'s failure bookkeeping.

A failed index query and a confirmed zero-result search both make
_search_from_index() return False. perform_search() distinguishes them via
self._index_query_failed before trusting self._index.is_fully_covered() —
otherwise a failed query could be reported as "Found 0 result(s)", or (after
the index is disabled following repeated failures) crash on None.is_fully_covered().
"""

import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

from modules.search.module import SearchModule


def _make_module() -> SearchModule:
    module = SearchModule()
    module._widget = None
    module.search_table = MagicMock()
    module.search_status_label = MagicMock()
    module._app_context = MagicMock(is_readonly=MagicMock(return_value=False))
    return module


def _make_module_for_naming_check() -> SearchModule:
    module = SearchModule()
    module._widget = MagicMock()
    module.cancel_btn = MagicMock()
    module.search_status_label = MagicMock()
    module._worker = None
    module._naming_worker = None
    return module


def _make_module_for_clear_search() -> SearchModule:
    module = SearchModule()
    module.search_edit = MagicMock()
    module.search_table = MagicMock()
    module.folder_tree = MagicMock()
    module.file_preview = None
    module.search_status_label = MagicMock()
    module.search_progress = MagicMock()
    module.search_btn = MagicMock()
    module.cancel_btn = MagicMock()
    module._worker = None
    module._naming_worker = None
    return module


def test_query_failure_sets_failed_flag_and_returns_false():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.side_effect = RuntimeError("boom")

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is False
    assert module._index_query_failed is True
    assert module._index_failures == 1
    assert module._index is not None  # not yet disabled before the 3rd failure


def test_third_consecutive_failure_disables_index():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.side_effect = RuntimeError("boom")

    for _ in range(3):
        result = module._search_from_index('term', True, True, True, True, False)
        assert result is False

    assert module._index_failures == 3
    assert module._index is None
    assert module._index_query_failed is True


def test_successful_query_clears_failed_flag():
    module = _make_module()
    module._index = MagicMock()
    module._index_query_failed = True
    module._index_failures = 2
    module._index.search_jobs.return_value = [{
        'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1',
        'po_number': '', 'description': 'Test', 'drawings': [],
    }]
    module._index.search_quotes.return_value = []

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is True
    assert module._index_query_failed is False
    assert module._index_failures == 0


def test_zero_results_leaves_failed_flag_false():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.return_value = []
    module._index.search_quotes.return_value = []

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is False


def _patched_naming_dialogs(mock_box, mock_dialog):
    # Patch via the target method's own __globals__ rather than a string
    # module path -- core/module_loader.py's dev-mode path can register a
    # second, distinct 'modules.search.module' object in sys.modules (see
    # CODING_NOTES.md "Plugins & Dynamic Loading"), which would make a
    # string-path patch silently target the wrong copy whenever another test
    # in the same session exercises that loader first. __globals__ is bound
    # to the actual module namespace this method's code object reads from,
    # so it's correct regardless of what sys.modules currently holds.
    return patch.dict(
        SearchModule._on_naming_check_finished.__globals__,
        {'QMessageBox': mock_box, 'FolderNamingReportDialog': mock_dialog},
    )


class TestCheckFolderNamingReadonlyGuard:
    """A read-only (search-only) kiosk install can't act on a naming-
    convention finding (fixing one means renaming folders on the actual
    share) and the report dialog's own reveal-in-Explorer actions are
    already disabled read-only, so the feature isn't reachable through the
    UI at all -- it's a main-menu item (main.py's setup_menu()) and that
    menu bar is never constructed on a readonly install. This guard is the
    defense-in-depth backstop if the method is somehow still reached (e.g.
    a stale/queued signal)."""

    def test_is_a_noop_when_readonly(self):
        module = _make_module_for_naming_check()
        module._app_context = MagicMock(is_readonly=MagicMock(return_value=True))

        module.check_folder_naming()

        module.cancel_btn.show.assert_not_called()
        assert module._naming_worker is None


class TestNamingCheckFinishedDistinguishesCancellation:
    """CodeRabbit finding on PR #325: a cancelled FolderNamingCheckWorker still
    emits whatever results it collected before cancellation -- showing that as
    "No naming issues found" or a complete report would be misleading, since
    customers after the cancellation point were never scanned at all."""

    def test_cancelled_scan_with_no_results_skips_the_no_issues_message(self):
        module = _make_module_for_naming_check()
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished([], True)

        mock_box.information.assert_not_called()
        mock_dialog.assert_not_called()
        module.search_status_label.setText.assert_called_with("Folder naming check cancelled")

    def test_cancelled_scan_with_partial_results_skips_the_report_dialog(self):
        module = _make_module_for_naming_check()
        results = [('Acme', r'C:\Acme\job documents\New folder', 'unrecognized folder')]
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished(results, True)

        mock_box.information.assert_not_called()
        mock_dialog.assert_not_called()

    def test_completed_scan_with_no_results_shows_no_issues_message(self):
        module = _make_module_for_naming_check()
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished([], False)

        mock_box.information.assert_called_once()
        mock_dialog.assert_not_called()

    def test_completed_scan_with_results_shows_report_dialog(self):
        module = _make_module_for_naming_check()
        results = [('Acme', r'C:\Acme\job documents\New folder', 'unrecognized folder')]
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished(results, False)

        mock_box.information.assert_not_called()
        mock_dialog.assert_called_once_with(module._widget, results, module.app_context)
        mock_dialog.return_value.exec.assert_called_once()


class TestClearSearchCancelsNamingWorkerToo:
    """CodeRabbit finding on PR #325: clear_search() cancelled/waited on the
    search worker but not a running folder naming check, then unconditionally
    hid cancel_btn -- the scan kept running with no way to cancel it, and
    could still pop a report dialog after the user had already cleared the
    UI."""

    def test_running_naming_worker_is_cancelled_and_waited_on(self):
        module = _make_module_for_clear_search()
        module._naming_worker = MagicMock()
        module._naming_worker.isRunning.return_value = True

        module.clear_search()

        module._naming_worker.cancel.assert_called_once()
        module._naming_worker.wait.assert_called_once()

    def test_no_naming_worker_running_is_a_no_op(self):
        module = _make_module_for_clear_search()
        module._naming_worker = None

        module.clear_search()  # must not raise

        module.cancel_btn.hide.assert_called_once()


class TestNamingScanIdInvalidatesStaleQueuedDeliveries:
    """CodeRabbit findings on PR #325: progress_update/finished are queued
    cross-thread connections, so the worker can emit one before wait()
    returns, but Qt only actually delivers it once control returns to the
    event loop -- after clear_search()/cleanup() have already reset the UI
    (or, for cleanup(), possibly deleted it). disconnect() alone doesn't
    prevent this: per Qt's own docs, it only stops *future* emissions from
    being queued, not ones already posted. clear_search()/cleanup() instead
    bump _naming_scan_id, and the connected wrapper slots drop any delivery
    whose captured scan id no longer matches -- correct regardless of
    whether the event was already queued before invalidation."""

    def test_clear_search_bumps_the_scan_id(self):
        module = _make_module_for_clear_search()
        module._naming_worker = MagicMock()
        module._naming_worker.isRunning.return_value = True
        module._naming_scan_id = 5

        module.clear_search()

        assert module._naming_scan_id == 6
        module._naming_worker.cancel.assert_called_once()
        module._naming_worker.wait.assert_called_once()

    def test_cleanup_bumps_the_scan_id(self):
        module = SearchModule()
        module._worker = None
        module._index_worker = None
        module._naming_worker = MagicMock()
        module._naming_worker.isRunning.return_value = True
        module._naming_scan_id = 5
        module.search_results = []

        module.cleanup()

        assert module._naming_scan_id == 6
        module._naming_worker.cancel.assert_called_once()
        module._naming_worker.wait.assert_called_once()

    def test_stale_progress_update_is_dropped(self):
        module = _make_module_for_naming_check()
        module._naming_scan_id = 2

        module._on_naming_progress_update("Checking Acme…", 1)  # scan 1, now stale

        module.search_status_label.setText.assert_not_called()

    def test_current_progress_update_is_applied(self):
        module = _make_module_for_naming_check()
        module._naming_scan_id = 2

        module._on_naming_progress_update("Checking Acme…", 2)

        module.search_status_label.setText.assert_called_once_with("Checking Acme…")

    def test_stale_finished_delivery_is_dropped(self):
        module = _make_module_for_naming_check()
        module._naming_scan_id = 2
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished_if_current([], False, 1)  # scan 1, now stale

        mock_box.information.assert_not_called()
        mock_dialog.assert_not_called()

    def test_current_finished_delivery_is_applied(self):
        module = _make_module_for_naming_check()
        module._naming_scan_id = 2
        mock_box, mock_dialog = MagicMock(), MagicMock()
        with _patched_naming_dialogs(mock_box, mock_dialog):
            module._on_naming_check_finished_if_current([], False, 2)

        mock_box.information.assert_called_once()


def _make_module_for_rebuild_index() -> SearchModule:
    module = SearchModule()
    module._index = MagicMock()
    module._index.clear_all.return_value = True
    module._index_worker = None
    module.start_indexer = MagicMock()
    module.show_error = MagicMock()
    return module


class TestRebuildSearchIndex:
    """rebuild_search_index() must force a genuinely full re-scan, not just
    delegate straight to update()'s normal incremental behavior -- that
    would silently skip every directory update() still believes is fresh,
    defeating the entire point of a manual rebuild."""

    def test_noop_when_index_unavailable(self):
        module = _make_module_for_rebuild_index()
        module._index = None

        module.rebuild_search_index()

        module.start_indexer.assert_not_called()

    def test_clears_index_then_restarts_indexer(self):
        module = _make_module_for_rebuild_index()

        module.rebuild_search_index()

        module._index.clear_all.assert_called_once()
        module.start_indexer.assert_called_once()

    def test_cancels_and_waits_on_an_in_flight_indexer_before_clearing(self):
        # Truncating jobs/bp_files/indexed_dirs while a background
        # IndexWorker is mid-transaction would race its own writes -- must
        # stop it first, same cancel()+wait() pattern used at teardown.
        module = _make_module_for_rebuild_index()
        module._index_worker = MagicMock()
        module._index_worker.isRunning.return_value = True

        module.rebuild_search_index()

        module._index_worker.cancel.assert_called_once()
        module._index_worker.wait.assert_called_once()
        module._index.clear_all.assert_called_once()

    def test_idle_indexer_is_left_alone(self):
        module = _make_module_for_rebuild_index()
        module._index_worker = MagicMock()
        module._index_worker.isRunning.return_value = False

        module.rebuild_search_index()

        module._index_worker.cancel.assert_not_called()
        module._index_worker.wait.assert_not_called()

    def test_failed_clear_shows_error_and_does_not_start_an_incremental_scan(self):
        # CodeRabbit finding, PR #328: proceeding to start_indexer() after a
        # failed clear_all() (e.g. the db was locked) would just run
        # update()'s normal incremental scan -- silently downgrading a
        # requested full rebuild into a no-op, with nothing telling the user
        # their rebuild didn't actually happen.
        module = _make_module_for_rebuild_index()
        module._index.clear_all.return_value = False

        module.rebuild_search_index()

        module.start_indexer.assert_not_called()
        module.show_error.assert_called_once()

    def test_clear_all_raising_shows_error_instead_of_crashing(self):
        # CodeRabbit finding, PR #328 (second round): clear_all() only
        # returns False for lock contention -- any other sqlite3.Error
        # (disk full, permission denied, corruption) it re-raises. This runs
        # synchronously on the GUI thread, so an uncaught exception here is
        # an unhandled exception in a Qt slot with nothing shown to the
        # user, the same silent-failure shape the bool-return fix addressed
        # for the lock case.
        module = _make_module_for_rebuild_index()
        module._index.clear_all.side_effect = sqlite3.OperationalError("disk I/O error")

        module.rebuild_search_index()  # must not raise

        module.start_indexer.assert_not_called()
        module.show_error.assert_called_once()
