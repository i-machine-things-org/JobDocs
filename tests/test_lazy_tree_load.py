"""Tests for deferred Add-to-Existing tree loading (issue #287).

Job/Quote modules used to walk the entire customer directory tree
unconditionally as soon as their widget was built (via populate_customer_lists()'s
dynamic populate_add_customer_list() dispatch), even though that data is only
shown on the "Add to Existing" sub-tab. Requires a real (offscreen) QApplication
since it exercises real widget/tab construction and real QThread workers —
every test must cancel+wait any worker it starts before returning, or the
still-running QThread crashes the interpreter on teardown.
"""

import os
import threading
import time

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import modules.job.module as job_module_ns  # noqa: E402
import modules.quote.module as quote_module_ns  # noqa: E402
from modules.job.module import JobModule  # noqa: E402
from modules.quote.module import QuoteModule  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context(tmp_path, cf_root):
    return AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(tmp_path / 'blueprints'),
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


def _cleanup_worker(m):
    """Cancel and wait for any real QThread the test started, or it crashes
    the interpreter on teardown while still running."""
    worker = getattr(m, '_worker', None)
    if worker is not None:
        worker.cancel()
        worker.wait()


class TestJobModuleLazyTreeLoad:
    def test_no_worker_spawned_until_add_tab_activated(self, qapp, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()  # builds the widget tree, starts on "Create New" sub-tab

            m.populate_add_customer_list()  # dynamically dispatched by main.py at startup
            assert m._worker is None
            assert m._add_tree_stale is True

            # Switching to the Add to Existing sub-tab should now trigger the load.
            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            assert m._worker is not None
            assert m._add_tree_stale is False
        finally:
            _cleanup_worker(m)

    def test_refresh_while_tab_visible_still_works(self, qapp, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()
            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            assert m._worker is not None  # activating the tab already started one

            # refresh_job_tree() cancels+waits any existing worker itself
            # before starting the next one, so calling it again must not hang.
            m.refresh_job_tree()
            assert m._worker is not None
        finally:
            _cleanup_worker(m)


class TestQuoteModuleLazyTreeLoad:
    def test_no_worker_spawned_until_add_tab_activated(self, qapp, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / 'Quotes' / '99001_Quote').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        m = QuoteModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m.populate_add_customer_list()
            assert m._worker is None
            assert m._add_tree_stale is True

            m._quote_tab_widget.setCurrentWidget(m._add_to_quote_tab)
            assert m._worker is not None
            assert m._add_tree_stale is False
        finally:
            _cleanup_worker(m)


def _make_hung_listdir(cf_root, release):
    """A stand-in for os.listdir() that blocks on `release` when called
    against cf_root, simulating a single hung syscall (dead/unresponsive
    network share) that no amount of is_cancelled() polling *around* it can
    interrupt -- only not blocking the GUI thread waiting for it can."""
    real_listdir = os.listdir
    target = os.path.normcase(str(cf_root))

    def hung_listdir(path, *a, **kw):
        if os.path.normcase(str(path)) == target:
            release.wait(2.0)
        return real_listdir(path, *a, **kw)

    return hung_listdir


class TestJobModuleRefreshDoesNotBlockOnHungWorker:
    """Regression tests for CodeRabbit's PR #317 promotion-review finding:
    refresh_job_tree()/search_jobs() used to call worker.cancel() followed
    by a *blocking* worker.wait(), which froze the whole GUI for as long as
    a stuck worker took to notice cancellation -- unbounded if it was stuck
    inside a single hung os.listdir() call, since is_cancelled() is only
    polled *between* items, never inside one blocking syscall. Follows up
    on issue #287/PR #304 (tests/test_tree_walk_cancellation.py), which
    fixed the "slow across many items" case but not this one.
    """

    def test_refresh_job_tree_does_not_block_on_a_hung_worker(self, qapp, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        release = threading.Event()
        monkeypatch.setattr(job_module_ns.os, 'listdir', _make_hung_listdir(cf_root, release))

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            # Starts a worker that immediately gets stuck in the hung
            # os.listdir() call above.
            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            first_worker = m._worker
            assert first_worker is not None
            assert first_worker.isRunning()

            start = time.monotonic()
            m.refresh_job_tree()
            elapsed = time.monotonic() - start

            assert elapsed < 0.5, f"refresh_job_tree() blocked for {elapsed:.2f}s on a hung worker"
            # The real restart is deferred, not started against the worker
            # that's still stuck.
            assert m._worker is first_worker
            assert m._pending_tree_action is not None
        finally:
            release.set()
            _cleanup_worker(m)

    def test_deferred_refresh_starts_once_stale_worker_actually_finishes(self, qapp, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        release = threading.Event()
        monkeypatch.setattr(job_module_ns.os, 'listdir', _make_hung_listdir(cf_root, release))

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            first_worker = m._worker
            assert first_worker is not None

            m.refresh_job_tree()  # deferred -- first_worker is still stuck
            assert m._pending_tree_action is not None
            assert m._worker is first_worker

            release.set()  # let the stuck worker actually finish

            # The deferred restart runs inside _on_loading_finished(), a
            # slot invoked via a queued cross-thread signal -- it only
            # fires once the Qt event loop processes it.
            deadline = time.monotonic() + 2.0
            while m._worker is first_worker and time.monotonic() < deadline:
                qapp.processEvents()
                time.sleep(0.01)

            assert m._worker is not None
            assert m._worker is not first_worker, "deferred refresh never started a replacement worker"
            assert m._pending_tree_action is None
        finally:
            release.set()
            _cleanup_worker(m)


class TestQuoteModuleRefreshDoesNotBlockOnHungWorker:
    def test_refresh_quote_tree_does_not_block_on_a_hung_worker(self, qapp, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root)

        release = threading.Event()
        monkeypatch.setattr(quote_module_ns.os, 'listdir', _make_hung_listdir(cf_root, release))

        m = QuoteModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m._quote_tab_widget.setCurrentWidget(m._add_to_quote_tab)
            first_worker = m._worker
            assert first_worker is not None
            assert first_worker.isRunning()

            start = time.monotonic()
            m.refresh_quote_tree()
            elapsed = time.monotonic() - start

            assert elapsed < 0.5, f"refresh_quote_tree() blocked for {elapsed:.2f}s on a hung worker"
            assert m._worker is first_worker
            assert m._pending_tree_action is not None
        finally:
            release.set()
            _cleanup_worker(m)
