"""Tests for fine-grained cancellation of the Add-to-Existing tree walk.

Follow-up to issue #287 / PR #304. The original fix made refresh_job_tree()/
refresh_quote_tree() call worker.cancel() followed by a *blocking* worker.wait()
when the "Add to Existing" tab is not active. That's safe only if cancel()
takes effect quickly. But JobTreeWorker/QuoteTreeWorker's run() loop only
checked the cancellation flag *between* customers -- AppContext.find_job_folders()/
find_quote_folders() themselves (the per-customer directory scan) had no way
to observe cancellation at all. So a worker that was mid-scan on one large or
slow customer directory when cancel() was requested would keep scanning that
entire customer to completion before honoring cancellation, and the GUI-thread
wait() would block for exactly that long.

The fix threads an `is_cancelled` callable into find_job_folders()/
find_quote_folders() and polls it inside their per-item scan loops (PO
folders, job folders, quote folders), not just once per call. These tests
verify that plumbing end-to-end using a deliberately slow fake AppContext
standing in for a slow/large directory tree, and directly against the real
AppContext implementation.
"""

import os
import threading
import time

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QThread  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from modules.job.module import JobTreeWorker  # noqa: E402
from modules.quote.module import QuoteTreeWorker  # noqa: E402
from modules.search.module import FolderNamingCheckWorker, IndexWorker  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _SlowJobAppContext:
    """Stands in for a customer directory scan slow enough (huge tree /
    network share) that it would still be "in flight" when cancel() is
    requested. Mirrors the shape of AppContext.find_job_folders(): it must
    honor is_cancelled() *inside* its per-item loop for the worker's cancel()
    to take effect promptly."""

    def __init__(self, num_items=40, step_delay=0.05):
        self.num_items = num_items
        self.step_delay = step_delay

    def find_job_folders(self, customer_path, is_cancelled=None, **kwargs):
        cancelled = is_cancelled or (lambda: False)
        jobs = []
        for i in range(self.num_items):
            if cancelled():
                break
            time.sleep(self.step_delay)
            jobs.append((f"job{i}", customer_path))
        return jobs


class _SlowQuoteAppContext:
    def __init__(self, num_items=40, step_delay=0.05):
        self.num_items = num_items
        self.step_delay = step_delay

    def find_quote_folders(self, customer_path, is_cancelled=None, **kwargs):
        cancelled = is_cancelled or (lambda: False)
        quotes = []
        for i in range(self.num_items):
            if cancelled():
                break
            time.sleep(self.step_delay)
            quotes.append((f"quote{i}", customer_path))
        return quotes


def test_job_worker_cancel_does_not_block_on_slow_in_flight_customer(qapp, tmp_path):
    """Reproduces the reviewer's reachability path: cancel() is requested
    while the worker is mid-scan on a single slow customer. wait() must
    return quickly -- far sooner than the full (unbounded) scan would take --
    because find_job_folders() now polls is_cancelled() per item."""
    cf_root = tmp_path / 'customer_files'
    (cf_root / 'Acme').mkdir(parents=True)

    slow_ctx = _SlowJobAppContext(num_items=40, step_delay=0.05)  # ~2s if uninterrupted
    worker = JobTreeWorker([('', str(cf_root))], 'Acme', False, slow_ctx)
    worker.start()
    try:
        time.sleep(0.15)  # let it get into the middle of the slow scan
        start = time.monotonic()
        worker.cancel()
        finished = worker.wait(2000)
        elapsed = time.monotonic() - start
        assert finished, "worker did not finish within the wait timeout"
        assert elapsed < 1.0, (
            f"cancel()+wait() took {elapsed:.2f}s -- cancellation is not "
            "taking effect inside the per-customer scan"
        )
    finally:
        if worker.isRunning():
            worker.cancel()
            worker.wait()


def test_quote_worker_cancel_does_not_block_on_slow_in_flight_customer(qapp, tmp_path):
    cf_root = tmp_path / 'customer_files'
    (cf_root / 'Acme').mkdir(parents=True)

    slow_ctx = _SlowQuoteAppContext(num_items=40, step_delay=0.05)
    worker = QuoteTreeWorker([('', str(cf_root))], 'Acme', False, slow_ctx)
    worker.start()
    try:
        time.sleep(0.15)
        start = time.monotonic()
        worker.cancel()
        finished = worker.wait(2000)
        elapsed = time.monotonic() - start
        assert finished, "worker did not finish within the wait timeout"
        assert elapsed < 1.0, (
            f"cancel()+wait() took {elapsed:.2f}s -- cancellation is not "
            "taking effect inside the per-customer scan"
        )
    finally:
        if worker.isRunning():
            worker.cancel()
            worker.wait()


class _SlowNamingAppContext:
    """Stands in for a customer directory scan slow enough to still be "in
    flight" when cancel() is requested. Mirrors the shape of
    AppContext.find_job_folders(): must honor is_cancelled() *inside* its
    per-item loop -- CodeRabbit's finding on FolderNamingCheckWorker was that
    it never passed is_cancelled at all, so cancel() could only take effect
    between customers, not mid-scan on one large/slow one."""

    def __init__(self, num_items=40, step_delay=0.05):
        self.num_items = num_items
        self.step_delay = step_delay
        self.entered = threading.Event()

    def is_readonly(self):
        return False

    def find_job_folders(self, customer_path, is_cancelled=None, unrecognized=None, **kwargs):
        self.entered.set()
        cancelled = is_cancelled or (lambda: False)
        for _ in range(self.num_items):
            if cancelled():
                break
            time.sleep(self.step_delay)
        return []


def test_folder_naming_worker_cancel_does_not_block_on_slow_in_flight_customer(qapp, tmp_path):
    cf_root = tmp_path / 'customer_files'
    (cf_root / 'Acme').mkdir(parents=True)

    slow_ctx = _SlowNamingAppContext(num_items=40, step_delay=0.05)  # ~2s if uninterrupted
    worker = FolderNamingCheckWorker([('', str(cf_root))], slow_ctx)
    worker.start()
    try:
        # Synchronize on actual scan entry rather than a fixed sleep -- a
        # late-starting worker could otherwise let this test pass even if
        # cancellation only takes effect between customers, not mid-scan.
        assert slow_ctx.entered.wait(timeout=2), "worker never entered find_job_folders()"
        start = time.monotonic()
        worker.cancel()
        finished = worker.wait(2000)
        elapsed = time.monotonic() - start
        assert finished, "worker did not finish within the wait timeout"
        assert elapsed < 1.0, (
            f"cancel()+wait() took {elapsed:.2f}s -- cancellation is not "
            "taking effect inside the per-customer scan"
        )
    finally:
        if worker.isRunning():
            worker.cancel()
            worker.wait()


def test_stale_naming_worker_deliveries_are_ignored_after_clear_search(qapp, tmp_path):
    """Real-Qt regression test (CodeRabbit, PR #325) for the queued-signal
    race: progress_update/finished are cross-thread queued connections, so
    the worker can emit one before wait() returns, but Qt only actually
    delivers it once control returns to the event loop -- after
    clear_search() has already reset the status label. This is
    deterministic, not timing-flaky: QThread.wait() never pumps the event
    loop, so a queued emission during it is *always* deferred past the
    caller's return, every run.

    An earlier fix tried disconnecting the signal before cancel()+wait(),
    but Qt's own docs say disconnect() only stops *future* emissions from
    being queued -- it does not un-queue one already posted. The actual fix
    is the _naming_scan_id guard clear_search() bumps and the connected
    wrapper slots check; this test wires the worker up exactly the way
    check_folder_naming() does (scan id + lambda-wrapped connections) rather
    than connecting the bare slot, so it exercises the real protection
    mechanism, not a simplified stand-in for it.
    """
    from unittest.mock import MagicMock

    from modules.search.module import SearchModule

    cf_root = tmp_path / 'customer_files'
    (cf_root / 'Acme').mkdir(parents=True)

    module = SearchModule()
    module.search_edit = MagicMock()
    module.search_table = MagicMock()
    module.folder_tree = MagicMock()
    module.file_preview = None
    module.search_status_label = MagicMock()
    module.search_progress = MagicMock()
    module.search_btn = MagicMock()
    module.cancel_btn = MagicMock()
    module.search_results = []
    module._worker = None

    slow_ctx = _SlowNamingAppContext(num_items=20, step_delay=0.05)
    module._naming_scan_id += 1
    scan_id = module._naming_scan_id
    module._naming_worker = FolderNamingCheckWorker([('', str(cf_root))], slow_ctx)
    module._naming_worker.progress_update.connect(
        lambda status, sid=scan_id: module._on_naming_progress_update(status, sid)
    )
    module._naming_worker.finished.connect(
        lambda results, cancelled, sid=scan_id: module._on_naming_check_finished_if_current(
            results, cancelled, sid
        )
    )
    module._naming_worker.start()
    try:
        assert slow_ctx.entered.wait(timeout=2), "worker never entered find_job_folders()"

        module.clear_search()
        qapp.processEvents()  # let anything still queued get delivered

        # clear_search() itself sets "" last; a stale progress_update or
        # finished delivery would have overwritten it (with old "Checking…"
        # text or "Folder naming check cancelled" respectively).
        module.search_status_label.setText.assert_called_with("")
    finally:
        if module._naming_worker.isRunning():
            module._naming_worker.cancel()
            module._naming_worker.wait()


def test_job_worker_uses_inherited_finished_signal_not_a_shadowing_one(qapp):
    """Regression test (CodeRabbit, PR #321 follow-up on the non-blocking-
    cancel fix in PR #317's promotion review): JobTreeWorker used to declare
    and manually emit its own `finished` signal as the last statement inside
    run(). That's a queued cross-thread delivery -- Qt's event loop can
    process it before the thread has actually finished returning from
    run(), so a connected slot wasn't guaranteed to see isRunning() as
    False yet. The deferred-restart logic in refresh_job_tree()/
    search_jobs() depends on that guarantee: if it re-checks isRunning()
    while still (technically) True, it re-defers against a worker that will
    never signal completion again, and the pending action is stuck forever.

    A timing-based reproduction is inherently racy (CodeRabbit's own repro
    needed an artificial QThread.msleep() to reliably widen the window) --
    assert the actual fix directly instead: JobTreeWorker must not shadow
    QThread.finished with a class-level signal of its own, so
    `.finished.connect(...)` always binds to the inherited one Qt guarantees
    fires only after run() has truly returned.
    """
    assert 'finished' not in JobTreeWorker.__dict__
    assert JobTreeWorker.finished is QThread.finished


def test_quote_worker_uses_inherited_finished_signal_not_a_shadowing_one(qapp):
    assert 'finished' not in QuoteTreeWorker.__dict__
    assert QuoteTreeWorker.finished is QThread.finished


def _make_app_context(tmp_path, cf_root):
    return AppContext(
        settings={
            'job_folder_structure': '{customer}/{po_number}/{job_folder}',
            'customer_files_dir': str(cf_root),
        },
        history={},
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )


def test_find_job_folders_honors_is_cancelled_mid_scan(tmp_path):
    """Direct unit test of AppContext.find_job_folders(): with PO/job
    structure and several PO folders each containing several job folders, an
    is_cancelled callable that returns True after the first poll must stop
    the scan well short of visiting every folder."""
    cf_root = tmp_path / 'customer_files'
    for po in range(5):
        for job in range(5):
            (cf_root / 'Acme' / f'PO{po}' / f'{job}_Job').mkdir(parents=True)
    ctx = _make_app_context(tmp_path, cf_root)

    calls = {'n': 0}

    def is_cancelled():
        calls['n'] += 1
        return calls['n'] > 1  # cancel on the second poll

    jobs = ctx.find_job_folders(str(cf_root / 'Acme'), is_cancelled=is_cancelled)

    # 25 folders exist total across 5 PO folders of 5 jobs each. Cancelling
    # after the second poll must yield fewer than 5 -- if cancellation only
    # took effect between PO folders (not per-job), all 5 jobs of the first
    # PO folder would still come back (5 < 25 would wrongly pass).
    assert len(jobs) < 5


def test_find_quote_folders_honors_is_cancelled_mid_scan(tmp_path):
    cf_root = tmp_path / 'customer_files'
    for q in range(25):
        (cf_root / 'Acme' / 'Quotes' / f'{q}_Quote').mkdir(parents=True)
    ctx = AppContext(
        settings={
            'quote_folder_path': 'Quotes',
            'customer_files_dir': str(cf_root),
        },
        history={},
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )

    calls = {'n': 0}

    def is_cancelled():
        calls['n'] += 1
        return calls['n'] > 1

    quotes = ctx.find_quote_folders(str(cf_root / 'Acme'), is_cancelled=is_cancelled)

    assert len(quotes) < 25


class _SlowIndex:
    """Stands in for SearchIndex when update() needs to still be "in
    flight" (mirrors _SlowJobAppContext/_SlowNamingAppContext above) --
    IndexWorker.run() calls this exactly like the real SearchIndex.update()."""

    def __init__(self, num_items=40, step_delay=0.05):
        self.num_items = num_items
        self.step_delay = step_delay
        self.entered = threading.Event()
        self.cleared = threading.Event()
        self.clear_all_calls = 0

    def clear_all(self):
        self.clear_all_calls += 1
        self.cleared.set()
        return True

    def update(self, cf_dirs, bp_dirs, app_context, progress=None, cancelled=None):
        self.entered.set()
        is_cancelled = cancelled or (lambda: False)
        for _ in range(self.num_items):
            if is_cancelled():
                return
            time.sleep(self.step_delay)

    def job_count(self):
        return 0


def test_index_worker_cancel_does_not_block_on_slow_update(qapp):
    """Real-Qt regression test (CodeRabbit, PR #329): rebuild_search_index()
    used to call worker.cancel() followed by a blocking worker.wait() on
    the GUI thread, freezing the app for as long as update()'s current
    filesystem operation took to return. Proves cancellation actually takes
    effect promptly inside update()'s scan loop, the same way the other
    workers in this file are proven."""
    slow_index = _SlowIndex(num_items=40, step_delay=0.05)  # ~2s if uninterrupted
    worker = IndexWorker(slow_index, [], [], app_context=None)
    worker.start()
    try:
        assert slow_index.entered.wait(timeout=2), "worker never entered update()"
        start = time.monotonic()
        worker.cancel()
        finished = worker.wait(2000)
        elapsed = time.monotonic() - start
        assert finished, "worker did not finish within the wait timeout"
        assert elapsed < 1.0, (
            f"cancel()+wait() took {elapsed:.2f}s -- cancellation is not "
            "taking effect inside update()'s scan loop"
        )
    finally:
        if worker.isRunning():
            worker.cancel()
            worker.wait()


def test_index_worker_uses_inherited_finished_signal_not_a_shadowing_one(qapp):
    """Regression test (CodeRabbit, PR #329): IndexWorker used to declare
    its own `finished = pyqtSignal(int)` and emit it manually as the last
    statement in run() -- the same shadowing bug already fixed for
    JobTreeWorker/QuoteTreeWorker (see their identical tests above). The
    job count moved to a separate `result` signal so the deferred-restart
    trigger (_on_index_worker_stopped(), wired to `.finished`) gets Qt's
    real guarantee that it fires only after run() has truly returned."""
    assert 'finished' not in IndexWorker.__dict__
    assert IndexWorker.finished is QThread.finished


class TestIndexWorkerClearFirst:
    """IndexWorker.run()'s clear_first branch (used by rebuild_search_index())
    must not run update() at all if clear_all() didn't actually succeed --
    proceeding would silently downgrade a requested full rebuild into an
    ordinary incremental scan. Calls run() directly (not start()) since
    there's no slow/threaded behavior to prove here, just the branching
    logic -- these run synchronously on the test's own thread."""

    def _make_worker(self, index, clear_first=True):
        return IndexWorker(index, [], [], app_context=None, clear_first=clear_first)

    def test_successful_clear_runs_update(self, qapp):
        index = _SlowIndex(num_items=0)
        worker = self._make_worker(index)
        results = []
        worker.result.connect(results.append)
        failures = []
        worker.clear_failed.connect(failures.append)

        worker.run()

        assert index.clear_all_calls == 1
        assert index.entered.is_set(), "update() was never called"
        assert results == [0]
        assert failures == []

    def test_clear_returning_false_skips_update(self, qapp):
        class _LockedIndex(_SlowIndex):
            def clear_all(self):
                self.clear_all_calls += 1
                return False

        index = _LockedIndex(num_items=0)
        worker = self._make_worker(index)
        results = []
        worker.result.connect(results.append)
        failures = []
        worker.clear_failed.connect(failures.append)

        worker.run()

        assert index.clear_all_calls == 1
        assert not index.entered.is_set(), "update() ran despite a failed clear_all()"
        assert results == [0]
        assert len(failures) == 1 and "busy" in failures[0]

    def test_clear_raising_skips_update(self, qapp):
        import sqlite3

        class _ErroringIndex(_SlowIndex):
            def clear_all(self):
                self.clear_all_calls += 1
                raise sqlite3.OperationalError("disk I/O error")

        index = _ErroringIndex(num_items=0)
        worker = self._make_worker(index)
        results = []
        worker.result.connect(results.append)
        failures = []
        worker.clear_failed.connect(failures.append)

        worker.run()  # must not raise -- the error must be reported via the signal instead

        assert index.clear_all_calls == 1
        assert not index.entered.is_set(), "update() ran despite clear_all() raising"
        assert results == [0]
        assert len(failures) == 1 and "disk I/O error" in failures[0]


def test_rebuild_search_index_defers_to_a_fresh_worker_once_the_old_one_stops(qapp, tmp_path):
    """Real-Qt end-to-end regression test (CodeRabbit, PR #329):
    rebuild_search_index() must return immediately (never block on an
    in-flight indexer) and only actually start the rebuild once the old
    worker's real QThread.finished confirms it has stopped -- proving the
    full cancel -> defer -> restart path wired up in SearchModule, not just
    the individual pieces in isolation."""
    from unittest.mock import MagicMock

    from modules.search.module import SearchModule

    module = SearchModule()
    module.search_status_label = MagicMock()
    module._worker = None
    module.show_error = MagicMock()
    module._app_context = MagicMock()

    slow_index = _SlowIndex(num_items=40, step_delay=0.05)  # ~2s if uninterrupted
    module._index = slow_index
    module._get_customer_files_dirs = MagicMock(return_value=[('', str(tmp_path))])
    module._get_blueprint_dirs = MagicMock(return_value=[])

    module.start_indexer()
    try:
        assert slow_index.entered.wait(timeout=2), "initial indexer never entered update()"

        start = time.monotonic()
        module.rebuild_search_index()
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, (
            f"rebuild_search_index() took {elapsed:.2f}s to return -- it must "
            "never block the GUI thread on an in-flight indexer"
        )
        assert module._rebuild_pending is True

        old_worker = module._index_worker
        assert old_worker.wait(2000), "in-flight indexer did not stop promptly after cancel()"
        qapp.processEvents()  # deliver the queued finished signal

        assert module._rebuild_pending is False
        assert module._index_worker is not None
        assert module._index_worker is not old_worker, "deferred rebuild never actually started"
        assert slow_index.cleared.wait(timeout=2), "deferred rebuild's clear_all() was never called"
        assert slow_index.clear_all_calls == 1
    finally:
        if module._index_worker and module._index_worker.isRunning():
            module._index_worker.cancel()
            module._index_worker.wait()
