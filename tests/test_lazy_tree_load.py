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

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

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
