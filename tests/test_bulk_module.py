"""Tests for BulkCreateDialog: the duplicate-checking scan (issue #293,
finding 1) and the dialog-close guard during create_bulk_jobs() (issue #292).
Requires a real (offscreen) QApplication since BulkCreateDialog loads a .ui file.
"""

from types import SimpleNamespace

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QCloseEvent  # noqa: E402
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


# ---------------------------------------------------------------------------
# Issue #293: reuse the duplicate scan instead of re-querying disk per job
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Issue #292: block dialog close while create_bulk_jobs()'s processEvents()
# loop is in flight
# ---------------------------------------------------------------------------

def _make_dialog(qapp, tmp_path):
    cf_root = tmp_path / 'customer_files'
    cf_root.mkdir(parents=True)

    class _RecordingJobModule:
        def __init__(self):
            self.controls_enabled_during_call = None

        def create_single_job(
            self, customer, job_number, po_number, po_line,
            description, drawings, revision, is_itar, files,
        ):
            self.controls_enabled_during_call = dialog.create_bulk_btn.isEnabled()
            return True

    job_module = _RecordingJobModule()
    main_window = SimpleNamespace(
        modules=[job_module],
        refresh_history=lambda: None,
        populate_customer_lists=lambda: None,
    )
    ctx = _make_app_context(tmp_path, cf_root, main_window=main_window)
    dialog = BulkCreateDialog(ctx)
    return dialog, job_module


def test_controls_disabled_during_and_reenabled_after_creation(qapp, tmp_path, monkeypatch):
    dialog, job_module = _make_dialog(qapp, tmp_path)
    dialog.bulk_text.setPlainText("Acme,12345,PO1,New Bracket\n")

    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    assert dialog._bulk_create_in_progress is False
    dialog.create_bulk_jobs()

    # The stub job module recorded whether the create button was disabled
    # while create_single_job() (standing in for the per-job work inside the
    # processEvents() loop) was executing.
    assert job_module.controls_enabled_during_call is False
    assert dialog.create_bulk_btn.isEnabled() is True
    assert dialog.import_btn.isEnabled() is True
    assert dialog.bulk_text.isEnabled() is True
    assert dialog._bulk_create_in_progress is False


def test_close_event_ignored_while_creation_in_progress(qapp, tmp_path):
    dialog, _job_module = _make_dialog(qapp, tmp_path)

    dialog._bulk_create_in_progress = True
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert event.isAccepted() is False

    dialog._bulk_create_in_progress = False
    event2 = QCloseEvent()
    dialog.closeEvent(event2)
    assert event2.isAccepted() is True


def test_reject_ignored_while_creation_in_progress(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    dialog, _job_module = _make_dialog(qapp, tmp_path)

    calls = []
    monkeypatch.setattr(QDialog, 'reject', lambda self: calls.append(1))

    dialog._bulk_create_in_progress = True
    dialog.reject()
    assert calls == []  # base QDialog.reject() must not run while busy

    dialog._bulk_create_in_progress = False
    dialog.reject()
    assert calls == [1]


def test_bulk_create_still_works_end_to_end(qapp, tmp_path, monkeypatch):
    # Sanity check that the guard doesn't break the ordinary happy path.
    dialog, job_module = _make_dialog(qapp, tmp_path)
    dialog.bulk_text.setPlainText(
        "Acme,12345,PO1,New Bracket\n"
        "NewCo,55555,PO2,Another Job\n"
    )
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    dialog.create_bulk_jobs()
    assert dialog.create_bulk_btn.isEnabled() is True
