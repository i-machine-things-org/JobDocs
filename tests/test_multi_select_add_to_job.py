"""Tests for multi-select on the Add to Existing job tree.

job_tree previously defaulted to QAbstractItemView.SingleSelection, so
only one job folder could be targeted per "Add Files to Job" click.
Requires a real (offscreen) QApplication since it exercises real widget
construction, selection signals, and the background JobTreeWorker --
see tests/test_lazy_tree_load.py for the same pattern.
"""

import os
import time

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QAbstractItemView, QApplication  # noqa: E402

from modules.job.module import JobModule  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context(tmp_path, cf_root, bp_root):
    return AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(bp_root),
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


def _load_tree_synchronously(m, qapp):
    """Block for the background JobTreeWorker started by activating the
    Add to Existing tab, then pump the event loop so its queued
    customer_loaded/finished signals actually populate job_tree."""
    worker = m._worker
    assert worker is not None
    worker.wait()
    deadline = time.monotonic() + 2.0
    while m.job_tree.topLevelItemCount() == 0 and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def _cleanup_worker(m):
    worker = getattr(m, '_worker', None)
    if worker is not None:
        worker.cancel()
        worker.wait()


class TestJobTreeMultiSelect:
    def test_job_tree_allows_extended_selection(self, qapp, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '111_Bracket').mkdir(parents=True)
        (cf_root / 'Acme' / '222_Housing').mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root, tmp_path / 'blueprints')

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()
            assert m.job_tree.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
        finally:
            _cleanup_worker(m)

    def test_selecting_two_jobs_updates_label_and_adds_to_both(self, qapp, tmp_path):
        cf_root = tmp_path / 'customer_files'
        bp_root = tmp_path / 'blueprints'
        job1 = cf_root / 'Acme' / '111_Bracket'
        job2 = cf_root / 'Acme' / '222_Housing'
        job1.mkdir(parents=True)
        job2.mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root, bp_root)

        src_file = tmp_path / 'drawing.pdf'
        src_file.write_text('fake pdf content')

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            _load_tree_synchronously(m, qapp)

            customer_item = m.job_tree.topLevelItem(0)
            assert customer_item is not None
            assert customer_item.childCount() == 2

            job_item_1 = customer_item.child(0)
            job_item_2 = customer_item.child(1)
            job_item_1.setSelected(True)
            job_item_2.setSelected(True)

            assert len(m.job_tree.selectedItems()) == 2
            assert m.selected_job_label.text() == "Selected: 2 jobs"

            m.dest_job_radio.setChecked(True)
            m.add_files = [str(src_file)]

            m.add_files_to_job()

            assert (job1 / 'drawing.pdf').exists()
            assert (job2 / 'drawing.pdf').exists()
            assert m.add_status_label.text() == "Added: 2, Skipped: 0"
        finally:
            _cleanup_worker(m)

    def test_job_only_dest_succeeds_without_blueprints_dir_configured(self, qapp, tmp_path):
        """dest == 'job' never touches the blueprints dir, so a job-only add
        must not be skipped just because blueprint storage isn't configured
        (CodeRabbit, PR #331)."""
        cf_root = tmp_path / 'customer_files'
        job1 = cf_root / 'Acme' / '111_Bracket'
        job1.mkdir(parents=True)
        ctx = _make_app_context(tmp_path, cf_root, tmp_path / 'blueprints')
        ctx.settings['blueprints_dir'] = ''

        src_file = tmp_path / 'drawing.pdf'
        src_file.write_text('fake pdf content')

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            _load_tree_synchronously(m, qapp)

            customer_item = m.job_tree.topLevelItem(0)
            job_item_1 = customer_item.child(0)
            job_item_1.setSelected(True)

            m.dest_job_radio.setChecked(True)
            m.add_files = [str(src_file)]

            m.add_files_to_job()

            assert (job1 / 'drawing.pdf').exists()
            assert m.add_status_label.text() == "Added: 1, Skipped: 0"
        finally:
            _cleanup_worker(m)

    def test_mixed_selection_skips_job_without_blueprints_dir_but_keeps_files(self, qapp, tmp_path):
        """A mixed selection (e.g. a standard job plus one that resolves as
        ITAR) where one job's blueprints directory isn't configured must not
        silently drop that job's files, and must not clear the pending
        add_files list -- the user needs to be able to retry the skipped job
        without re-adding every file (CodeRabbit, PR #334)."""
        cf_root = tmp_path / 'customer_files'
        bp_root = tmp_path / 'blueprints'
        job1 = cf_root / 'Acme' / '111_Bracket'
        itar_cf_root = cf_root / 'ItarCo'
        job2 = itar_cf_root / '222_Widget'
        job1.mkdir(parents=True)
        job2.mkdir(parents=True)

        ctx = _make_app_context(tmp_path, cf_root, bp_root)
        ctx._settings['itar_customer_files_dir'] = str(itar_cf_root)
        # itar_blueprints_dir intentionally left unset: job2's bp_dir resolves empty

        errors = []
        ctx._show_error = lambda title, message: errors.append((title, message))

        src_file = tmp_path / 'drawing.pdf'
        src_file.write_text('fake pdf content')

        m = JobModule()
        try:
            m.initialize(ctx)
            m.get_widget()

            m._job_tab_widget.setCurrentWidget(m._add_to_job_tab)
            _load_tree_synchronously(m, qapp)

            job_item_1 = None
            job_item_2 = None
            for i in range(m.job_tree.topLevelItemCount()):
                customer_item = m.job_tree.topLevelItem(i)
                if customer_item.text(0) == 'Acme':
                    job_item_1 = customer_item.child(0)
                elif customer_item.text(0) == 'ItarCo':
                    job_item_2 = customer_item.child(0)
            assert job_item_1 is not None and job_item_2 is not None

            job_item_1.setSelected(True)
            job_item_2.setSelected(True)

            m.dest_blueprints_radio.setChecked(True)
            m.add_files = [str(src_file)]

            m.add_files_to_job()

            assert (bp_root / 'Acme' / 'drawing.pdf').exists()
            assert not (bp_root / 'ItarCo' / 'drawing.pdf').exists()
            assert m.add_status_label.text() == "Added: 1, Skipped: 1"

            # The skipped job's files must not be dropped from the pending
            # list -- clear_add_files() must not have run.
            assert m.add_files == [str(src_file)]

            assert len(errors) == 1
            title, message = errors[0]
            assert title == "Jobs Skipped"
            assert "222_Widget" in message
        finally:
            _cleanup_worker(m)
