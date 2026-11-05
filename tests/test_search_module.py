"""Tests for SearchModule._search_from_index()'s failure bookkeeping.

A failed index query and a confirmed zero-result search both make
_search_from_index() return False. perform_search() distinguishes them via
self._index_query_failed before trusting self._index.is_fully_covered() —
otherwise a failed query could be reported as "Found 0 result(s)", or (after
the index is disabled following repeated failures) crash on None.is_fully_covered().
"""

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
    module._index_worker = None
    module._rebuild_pending = False
    module.start_indexer = MagicMock()
    module.show_error = MagicMock()
    return module


class TestRebuildSearchIndex:
    """rebuild_search_index() must never block the GUI thread on an
    in-flight indexer (CodeRabbit, PR #329) -- a cancel()+wait() here would
    freeze the app for as long as the *current* filesystem operation takes
    to return, which is unbounded on a slow/hung network share. If a worker
    is running, this only requests cancellation and flags the rebuild as
    pending; _on_index_worker_stopped() (real-Qt coverage in
    tests/test_tree_walk_cancellation.py) starts the actual rebuild once
    the old worker's inherited QThread.finished confirms it stopped.
    clear_all() itself now runs inside IndexWorker's background thread
    (also covered there), not here."""

    def test_noop_when_index_unavailable(self):
        module = _make_module_for_rebuild_index()
        module._index = None

        module.rebuild_search_index()

        module.start_indexer.assert_not_called()

    def test_starts_a_rebuild_indexer_when_nothing_is_running(self):
        module = _make_module_for_rebuild_index()

        module.rebuild_search_index()

        module.start_indexer.assert_called_once_with(rebuild=True)
        assert module._rebuild_pending is False

    def test_in_flight_indexer_is_cancelled_without_blocking(self):
        module = _make_module_for_rebuild_index()
        module._index_worker = MagicMock()
        module._index_worker.isRunning.return_value = True

        module.rebuild_search_index()

        module._index_worker.cancel.assert_called_once()
        module._index_worker.wait.assert_not_called()
        assert module._rebuild_pending is True
        module.start_indexer.assert_not_called()

    def test_idle_indexer_is_started_directly(self):
        module = _make_module_for_rebuild_index()
        module._index_worker = MagicMock()
        module._index_worker.isRunning.return_value = False

        module.rebuild_search_index()

        module._index_worker.cancel.assert_not_called()
        module.start_indexer.assert_called_once_with(rebuild=True)


class TestIndexWorkerStoppedDeferredRestart:
    """_on_index_worker_stopped() is wired to the just-finished worker's
    real QThread.finished -- the deferred-rebuild trigger rebuild_search_index()
    relies on when it couldn't start immediately."""

    def test_pending_rebuild_starts_on_stop_and_clears_the_flag(self):
        module = _make_module_for_rebuild_index()
        module._rebuild_pending = True

        module._on_index_worker_stopped()

        module.start_indexer.assert_called_once_with(rebuild=True)
        assert module._rebuild_pending is False

    def test_no_pending_rebuild_is_a_noop(self):
        module = _make_module_for_rebuild_index()
        module._rebuild_pending = False

        module._on_index_worker_stopped()

        module.start_indexer.assert_not_called()


class TestIndexResultStatusText:
    def test_pending_rebuild_suppresses_stale_ready_text(self):
        # A fresh rebuild worker is about to start (from
        # _on_index_worker_stopped, wired to this same worker's finished) --
        # don't flash a "ready" status for the scan being superseded.
        module = _make_module_for_rebuild_index()
        module._rebuild_pending = True
        module.search_status_label = MagicMock()
        module._worker = None

        module._on_index_result(42)

        module.search_status_label.setText.assert_not_called()

    def test_normal_completion_shows_ready_text(self):
        module = _make_module_for_rebuild_index()
        module.search_status_label = MagicMock()
        module._worker = None

        module._on_index_result(42)

        module.search_status_label.setText.assert_called_once_with("Index ready — 42 jobs")


class TestIndexClearFailed:
    def test_shows_error_with_the_given_message(self):
        module = _make_module_for_rebuild_index()

        module._on_index_clear_failed("some message")

        module.show_error.assert_called_once_with("Rebuild Search Index", "some message")


class TestPassesActiveFilter:
    """_passes_active_filter() backs the "Active Jobs Only" search checkbox.
    Only real job-folder results are matched against JobBOSS's
    Job.Status='Active' set (self._active_job_filter); blueprint/quote
    results have no corresponding Job row at all, so they always pass
    through regardless of what's in the set."""

    def test_job_result_in_active_set_passes(self):
        module = SearchModule()
        module._active_job_filter = {'27173H', '1001'}

        assert module._passes_active_filter({'customer': 'Acme', 'job_number': '27173h'}) is True

    def test_job_result_not_in_active_set_is_filtered_out(self):
        module = SearchModule()
        module._active_job_filter = {'1001'}

        assert module._passes_active_filter({'customer': 'Acme', 'job_number': '27173H'}) is False

    def test_itar_job_result_is_still_checked_against_active_set(self):
        module = SearchModule()
        module._active_job_filter = set()

        assert module._passes_active_filter({'customer': '[ITAR] Acme', 'job_number': '27173H'}) is False

    def test_blueprint_result_always_passes(self):
        module = SearchModule()
        module._active_job_filter = set()  # empty -- would fail a real job check

        assert module._passes_active_filter({'customer': '[BP] Acme', 'job_number': 'drawing-1'}) is True

    def test_quote_result_always_passes(self):
        module = SearchModule()
        module._active_job_filter = set()

        assert module._passes_active_filter({'customer': '[Quote] Acme', 'job_number': 'Q-100'}) is True


class TestSearchFromIndexActiveFilter:
    """_search_from_index() applies self._active_job_filter (set by a
    preceding ActiveJobsWorker fetch) to its combined jobs/quotes/bp results,
    same point the existing readonly ITAR-prune already runs at."""

    def test_filters_out_job_not_in_active_set(self):
        module = _make_module()
        module._index = MagicMock()
        module._index.search_jobs.return_value = [
            {'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1001',
             'po_number': '', 'description': '', 'drawings': []},
            {'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1002',
             'po_number': '', 'description': '', 'drawings': []},
        ]
        module._index.search_quotes.return_value = []
        module._active_job_filter = {'1001'}

        result = module._search_from_index('term', True, True, True, True, False)

        assert result is True
        assert [r['job_number'] for r in module.search_results] == ['1001']

    def test_filter_none_keeps_every_result(self):
        module = _make_module()
        module._index = MagicMock()
        module._index.search_jobs.return_value = [
            {'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1001',
             'po_number': '', 'description': '', 'drawings': []},
        ]
        module._index.search_quotes.return_value = []
        module._active_job_filter = None

        result = module._search_from_index('term', True, True, True, True, False)

        assert result is True
        assert len(module.search_results) == 1

    def test_filtering_down_to_zero_results_falls_back_like_a_real_zero_match(self):
        module = _make_module()
        module._index = MagicMock()
        module._index.search_jobs.return_value = [
            {'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1002',
             'po_number': '', 'description': '', 'drawings': []},
        ]
        module._index.search_quotes.return_value = []
        module._active_job_filter = {'1001'}

        result = module._search_from_index('term', True, True, True, True, False)

        assert result is False


class TestOnResultFoundActiveFilter:
    """_on_result_found() (the live/legacy SearchWorker's per-result slot)
    applies self._active_job_filter the same way _search_from_index() does,
    so the two search paths stay consistent."""

    def test_non_matching_job_result_is_dropped(self):
        module = _make_module()
        module.search_results = []
        module._active_job_filter = {'1001'}

        module._on_result_found({
            'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1002',
            'po_number': '', 'description': '', 'drawings': [],
        })

        assert module.search_results == []
        module.search_table.insertRow.assert_not_called()

    def test_matching_job_result_is_kept(self):
        module = _make_module()
        module.search_results = []
        module.search_table.rowCount.return_value = 0
        module._active_job_filter = {'1001'}

        module._on_result_found({
            'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1001',
            'po_number': '', 'description': '', 'drawings': [],
        })

        assert len(module.search_results) == 1
        module.search_table.insertRow.assert_called_once()

    def test_non_job_result_is_kept_even_though_it_cannot_match(self):
        module = _make_module()
        module.search_results = []
        module.search_table.rowCount.return_value = 0
        module._active_job_filter = set()

        module._on_result_found({
            'date': datetime(2026, 1, 1), 'customer': '[BP] Acme', 'job_number': 'drawing-1',
            'po_number': '', 'description': '', 'drawings': [],
        })

        assert len(module.search_results) == 1


def _make_module_for_perform_search() -> SearchModule:
    module = SearchModule()
    module.search_edit = MagicMock()
    module.search_edit.text.return_value = 'acme'
    module._worker = None
    module.search_active_only_check = MagicMock()
    module.show_error = MagicMock()
    module.search_status_label = MagicMock()
    module.search_btn = MagicMock()
    module._execute_search = MagicMock()
    # Deliberately unconfigured (empty strings) unless a test patches
    # is_configured() itself -- db_integration.is_configured() requires a
    # stored keyring password too, which no unit test should depend on.
    module._app_context = MagicMock(get_setting=MagicMock(return_value=''))
    return module


class TestPerformSearchActiveJobsGating:
    """perform_search() defers to a background ActiveJobsWorker fetch before
    running the real search whenever "Active Jobs Only" is checked, instead
    of running the search immediately -- mirrors the cooperative-ownership
    pattern _naming_worker already uses elsewhere in this module."""

    def test_checkbox_unchecked_runs_search_directly_and_clears_any_stale_filter(self):
        module = _make_module_for_perform_search()
        module.search_active_only_check.isChecked.return_value = False
        module._active_job_filter = {'1001'}  # left over from a previous active-only search

        module.perform_search()

        assert module._active_job_filter is None
        module._execute_search.assert_called_once()

    def test_checkbox_checked_but_db_not_configured_shows_error_and_does_not_search(self):
        module = _make_module_for_perform_search()
        module.search_active_only_check.isChecked.return_value = True

        module.perform_search()

        module.show_error.assert_called_once()
        module._execute_search.assert_not_called()
        assert module._active_jobs_worker is None

    def test_checkbox_checked_with_fetch_already_running_is_a_noop(self):
        module = _make_module_for_perform_search()
        module.search_active_only_check.isChecked.return_value = True
        module._active_jobs_worker = MagicMock()
        module._active_jobs_worker.isRunning.return_value = True

        module.perform_search()

        module.show_error.assert_not_called()
        module._execute_search.assert_not_called()

    def test_checkbox_checked_and_configured_starts_fetch_instead_of_searching(self):
        module = _make_module_for_perform_search()
        module.search_active_only_check.isChecked.return_value = True
        mock_worker_cls = MagicMock()

        # Patched via __globals__, not a string module path -- see
        # _patched_naming_dialogs()'s own comment above: core/module_loader.py's
        # dev-mode path can register a second, distinct 'modules.search.module'
        # object in sys.modules, which would make '@patch("modules.search.module.…")'
        # silently target the wrong copy whenever another test in this session
        # exercises that loader first. __globals__ is bound to the actual
        # module namespace the methods' code objects read from, so it's
        # correct regardless of what sys.modules currently holds.
        real_db_integration = SearchModule.perform_search.__globals__['db_integration']
        with patch.object(real_db_integration, 'is_configured', return_value=True), \
                patch.dict(SearchModule._start_active_jobs_fetch.__globals__, {'ActiveJobsWorker': mock_worker_cls}):
            module.perform_search()

        mock_worker_cls.return_value.start.assert_called_once()
        module._execute_search.assert_not_called()
        module.search_btn.setEnabled.assert_called_with(False)


class TestActiveJobsWorkerIsNeverWiredToDeleteLater:
    """Regression test for a real crash hit by a live run of the app:
    _start_active_jobs_fetch() originally wired
    `self._active_jobs_worker.finished.connect(self._active_jobs_worker.deleteLater)`.
    deleteLater() destroys the underlying C/C++ QObject once the thread
    finishes, but self._active_jobs_worker is never reassigned until the
    *next* fetch starts (unlike _worker/_index_worker/_naming_worker
    elsewhere in this module, which are only ever reassigned from inside
    their own finished handler) -- so after the first fetch completed, a
    second "Active Jobs Only" search hit
    `RuntimeError: wrapped C/C++ object of type ActiveJobsWorker has been
    deleted` on perform_search()'s `self._active_jobs_worker.isRunning()`
    guard. Python's own refcounting is enough to free the old worker once
    _start_active_jobs_fetch() reassigns the attribute to a new instance;
    deleteLater() must never be wired to this particular worker."""

    def test_does_not_connect_finished_to_delete_later(self):
        module = _make_module_for_perform_search()
        mock_worker_cls = MagicMock()

        with patch.dict(SearchModule._start_active_jobs_fetch.__globals__, {'ActiveJobsWorker': mock_worker_cls}):
            module._start_active_jobs_fetch()

        mock_worker_cls.return_value.finished.connect.assert_not_called()


class TestActiveJobsEpochInvalidatesStaleDeliveries:
    """Same staleness-guard pattern as _naming_scan_id (see
    TestNamingScanIdInvalidatesStaleQueuedDeliveries above): a delivery
    captured against an older _active_jobs_epoch is dropped instead of
    kicking off (or erroring out) a search against UI state a newer search
    or a clear has already moved past."""

    def _module(self) -> SearchModule:
        module = SearchModule()
        module._execute_search = MagicMock()
        module.show_error = MagicMock()
        module.search_btn = MagicMock()
        module.search_status_label = MagicMock()
        return module

    def test_stale_fetched_delivery_is_dropped(self):
        module = self._module()
        module._active_jobs_epoch = 2

        module._on_active_jobs_fetched({'1001'}, 1)

        assert module._active_job_filter is None
        module._execute_search.assert_not_called()

    def test_current_fetched_delivery_stores_filter_and_runs_search(self):
        module = self._module()
        module._active_jobs_epoch = 2

        module._on_active_jobs_fetched({'1001'}, 2)

        assert module._active_job_filter == {'1001'}
        module._execute_search.assert_called_once()

    def test_stale_error_delivery_is_dropped(self):
        module = self._module()
        module._active_jobs_epoch = 2

        module._on_active_jobs_error("boom", 1)

        module.show_error.assert_not_called()

    def test_current_error_delivery_shows_error_and_re_enables_search(self):
        module = self._module()
        module._active_jobs_epoch = 2

        module._on_active_jobs_error("boom", 2)

        module.show_error.assert_called_once_with("Active Jobs Only", "boom")
        module.search_btn.setEnabled.assert_called_once_with(True)


class TestClearSearchAndCleanupHandleActiveJobsWorker:
    """A running ActiveJobsWorker has no cancel() (see
    _start_active_jobs_fetch()'s docstring). clear_search() (an interactive,
    GUI-triggered reset) must bump _active_jobs_epoch (so a late delivery is
    dropped, same mechanism as TestActiveJobsEpochInvalidatesStaleDeliveries)
    without blocking on wait() -- unlike cleanup() below, there's no app-exit
    thread-lifetime concern to trade responsiveness against here."""

    def test_clear_search_bumps_epoch_without_waiting(self):
        module = _make_module_for_clear_search()
        module._active_jobs_worker = MagicMock()
        module._active_jobs_worker.isRunning.return_value = True
        module._active_jobs_epoch = 3

        module.clear_search()

        assert module._active_jobs_epoch == 4
        module._active_jobs_worker.wait.assert_not_called()

    def test_clear_search_leaves_epoch_alone_when_nothing_is_running(self):
        module = _make_module_for_clear_search()
        module._active_jobs_worker = None
        module._active_jobs_epoch = 3

        module.clear_search()  # must not raise

        assert module._active_jobs_epoch == 3

    def test_cleanup_bumps_epoch_and_waits_with_a_bound(self):
        # Unlike clear_search(), cleanup() runs at app/module teardown, where
        # an un-joined thread logs Qt's "Destroyed while thread is still
        # running" warning -- a *bounded* wait(2000) covers the common fast
        # case (a single SELECT) without risking an indefinite shutdown hang
        # on a slow/unreachable DB.
        module = SearchModule()
        module._worker = None
        module._index_worker = None
        module._naming_worker = None
        module._active_jobs_worker = MagicMock()
        module._active_jobs_worker.isRunning.return_value = True
        module._active_jobs_epoch = 3
        module.search_results = []

        module.cleanup()

        assert module._active_jobs_epoch == 4
        module._active_jobs_worker.wait.assert_called_once_with(2000)
