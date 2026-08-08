"""Tests for BulkCreateDialog's dialog-close guard during create_bulk_jobs()
(issue #292). Requires a real (offscreen) QApplication since BulkCreateDialog
loads a .ui file.
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
