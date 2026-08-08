"""Tests for BulkCreateDialog's duplicate-checking scan (issue #293, finding 1).

Requires a real (offscreen) QApplication since BulkCreateDialog loads a .ui file.
"""

from types import SimpleNamespace

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from modules.bulk.module import BulkCreateDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context(tmp_path, cf_root, main_window=None):
    return AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(tmp_path / 'blueprints'),
            'allow_duplicate_jobs': False,
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
        main_window=main_window,
    )


class _StubJobModule:
    def __init__(self):
        self.calls = []

    def create_single_job(
        self, customer, job_number, po_number, po_line,
        description, drawings, revision, is_itar, files,
    ):
        self.calls.append((customer, job_number))
        return True


def test_bulk_create_does_not_rescan_filesystem_per_job(qapp, tmp_path, monkeypatch):
    cf_root = tmp_path / 'customer_files'
    # Pre-existing job on disk — should be detected as a duplicate and skipped.
    (cf_root / 'Acme' / '12345_Existing').mkdir(parents=True)

    job_module = _StubJobModule()
    main_window = SimpleNamespace(
        modules=[job_module],
        refresh_history=lambda: None,
        populate_customer_lists=lambda: None,
    )
    ctx = _make_app_context(tmp_path, cf_root, main_window=main_window)

    dialog = BulkCreateDialog(ctx)
    dialog.bulk_itar_check.setChecked(False)
    dialog.bulk_text.setPlainText(
        "Acme,12345,PO1,Existing Bracket\n"
        "Acme,99999,PO2,New Widget\n"
        "Acme,99999,PO2,New Widget\n"  # intra-batch duplicate of the row above
        "NewCo,55555,PO3,Another New Job\n"
    )

    call_count = {'n': 0}
    original_job_exists = dialog.job_exists

    def counting_job_exists(*args, **kwargs):
        call_count['n'] += 1
        return original_job_exists(*args, **kwargs)

    monkeypatch.setattr(dialog, 'job_exists', counting_job_exists)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    dialog.create_bulk_jobs()

    # One job_exists() call per parsed job (4) during the initial duplicate
    # scan, and zero further calls during creation — the creation pass reuses
    # that scan's results instead of re-querying the filesystem per job.
    assert call_count['n'] == 4

    # 12345 (pre-existing) and the second 99999 (intra-batch dup) are skipped;
    # 99999 (first occurrence) and 55555 are created.
    assert sorted(job_module.calls) == [('Acme', '99999'), ('NewCo', '55555')]
