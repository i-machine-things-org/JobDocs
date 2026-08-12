"""Tests for BulkCreateDialog's dialog-close guard during create_bulk_jobs()
(issue #292) and its duplicate-checking scan (issue #293, finding 1).
Requires a real (offscreen) QApplication since BulkCreateDialog loads a .ui
file.
"""

from types import SimpleNamespace

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtGui import QCloseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

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
            self.status_label_during_call = None
            self.calls = []

        def create_single_job(
            self, customer, job_number, po_number, po_line,
            description, drawings, revision, is_itar, files,
        ):
            self.controls_enabled_during_call = dialog.create_bulk_btn.isEnabled()
            self.status_label_during_call = dialog.bulk_status_label.text()
            self.calls.append(job_number)
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
    # Status feedback (issue #292 review finding: user can't tell "working"
    # from "frozen") was visible while the job was in flight.
    assert job_module.status_label_during_call == "Processing job 1 of 1..."
    assert dialog.create_bulk_btn.isEnabled() is True
    assert dialog.import_btn.isEnabled() is True
    assert dialog.bulk_text.isEnabled() is True
    assert dialog._bulk_create_in_progress is False
    # Cancel button is hidden again once the batch finishes.
    assert dialog.bulk_cancel_btn.isVisible() is False


def test_close_event_ignored_while_creation_in_progress(qapp, tmp_path, monkeypatch):
    dialog, _job_module = _make_dialog(qapp, tmp_path)

    # closeEvent while busy must never fall through to a real close — even
    # when the user declines the confirm-cancel prompt.
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)
    dialog._bulk_create_in_progress = True
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert event.isAccepted() is False
    assert dialog._bulk_cancel_requested is False

    dialog._bulk_create_in_progress = False
    event2 = QCloseEvent()
    dialog.closeEvent(event2)
    assert event2.isAccepted() is True


def test_close_event_offers_confirm_cancel_escape_while_in_progress(qapp, tmp_path, monkeypatch):
    """Review finding: an unconditional close-block with no escape route
    turns a bad batch (bad path / dead network share) into an unkillable
    hang. Confirming the prompt must request cancellation as the way out."""
    dialog, _job_module = _make_dialog(qapp, tmp_path)

    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    dialog._bulk_create_in_progress = True
    event = QCloseEvent()
    dialog.closeEvent(event)

    # The dialog itself isn't torn down synchronously mid-batch (the loop
    # still owns teardown), but the escape hatch — cancellation — is armed.
    assert event.isAccepted() is False
    assert dialog._bulk_cancel_requested is True
    assert dialog.bulk_cancel_btn.isEnabled() is False


def test_reject_ignored_while_creation_in_progress(qapp, tmp_path, monkeypatch):
    dialog, _job_module = _make_dialog(qapp, tmp_path)

    calls = []
    monkeypatch.setattr(QDialog, 'reject', lambda self: calls.append(1))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)

    dialog._bulk_create_in_progress = True
    dialog.reject()
    assert calls == []  # base QDialog.reject() must not run while busy
    assert dialog._bulk_cancel_requested is False

    dialog._bulk_create_in_progress = False
    dialog.reject()
    assert calls == [1]


def test_done_guarded_while_creation_in_progress(qapp, tmp_path, monkeypatch):
    """Review finding: the guard originally only covered closeEvent()/
    reject(), not done()/accept() — an easy gap for a future contributor who
    adds a QDialogButtonBox. done() is the common choke point both funnel
    through, so guard it there too."""
    dialog, _job_module = _make_dialog(qapp, tmp_path)

    calls = []
    monkeypatch.setattr(QDialog, 'done', lambda self, result: calls.append(result))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)

    dialog._bulk_create_in_progress = True
    dialog.done(QDialog.DialogCode.Accepted)
    assert calls == []  # base QDialog.done() must not run while busy

    dialog._bulk_create_in_progress = False
    dialog.done(QDialog.DialogCode.Accepted)
    assert calls == [QDialog.DialogCode.Accepted]


def test_cancel_button_stops_batch_after_current_job(qapp, tmp_path, monkeypatch):
    """The Cancel button is the primary escape route for a runaway batch
    (bad/dead directory, per-job blocking error dialogs, etc.): requesting
    cancellation must stop the loop before the next job, not mid-job."""
    dialog, job_module = _make_dialog(qapp, tmp_path)
    dialog.bulk_text.setPlainText(
        "Acme,12345,PO1,New Bracket\n"
        "NewCo,55555,PO2,Another Job\n"
    )
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)

    info_calls = []
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: info_calls.append(a))

    orig_create_single_job = job_module.create_single_job

    def _create_and_cancel(*args, **kwargs):
        result = orig_create_single_job(*args, **kwargs)
        dialog.request_bulk_cancel()
        return result

    job_module.create_single_job = _create_and_cancel

    dialog.create_bulk_jobs()

    assert job_module.calls == ["12345"]  # second job never started
    assert info_calls and info_calls[0][1] == "Cancelled"
    assert dialog.create_bulk_btn.isEnabled() is True
    assert dialog.bulk_cancel_btn.isVisible() is False
    assert dialog._bulk_create_in_progress is False
    assert dialog._bulk_cancel_requested is False


def test_close_attempt_during_processing_loop_is_handled_gracefully(qapp, tmp_path, monkeypatch):
    """Reproduces the original issue #292 crash scenario end-to-end: an
    actual close attempt (not a direct closeEvent()/reject() call) delivered
    while create_bulk_jobs()'s QApplication.processEvents() call is pumping
    the event queue, fired from a slot connected during the loop itself."""
    dialog, job_module = _make_dialog(qapp, tmp_path)
    dialog.bulk_text.setPlainText(
        "Acme,12345,PO1,New Bracket\n"
        "NewCo,55555,PO2,Another Job\n"
    )

    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    orig_create_single_job = job_module.create_single_job
    close_scheduled = []

    def _schedule_close_then_create(*args, **kwargs):
        result = orig_create_single_job(*args, **kwargs)
        if not close_scheduled:
            close_scheduled.append(True)
            # Queues a real close() for delivery the next time the event
            # loop spins — exactly what happens when a user clicks the
            # title-bar X while create_bulk_jobs()'s processEvents() is
            # pumping the queue (the original issue #292 crash path).
            QTimer.singleShot(0, dialog.close)
        return result

    job_module.create_single_job = _schedule_close_then_create

    # Must not raise. The original bug was a RuntimeError from a disposed
    # C++ object once the queued close event was delivered mid-loop.
    dialog.create_bulk_jobs()

    assert close_scheduled == [True]
    # The dialog survived the close attempt (cancelled cleanly, not torn
    # down mid-batch) — widgets are still live, not deleted C++ objects.
    assert dialog.create_bulk_btn.isEnabled() is True
    assert dialog._bulk_create_in_progress is False
    assert job_module.calls == ["12345"]  # second job never started


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
    # scan. Because a duplicate was found, the confirmation dialog is shown,
    # so the post-dialog recheck (finding 2 fix) re-verifies the 2 unique
    # (customer, job_number) keys that weren't already flagged as duplicates
    # (Acme/99999 and NewCo/55555 — the second 99999 row is deduped, and
    # Acme/12345 is skipped since it's already known to be a duplicate).
    # Zero further calls happen during creation — the loop reuses pre_existing.
    assert call_count['n'] == 6

    # 12345 (pre-existing) and the second 99999 (intra-batch dup) are skipped;
    # 99999 (first occurrence) and 55555 are created.
    assert sorted(job_module.calls) == [('Acme', '99999'), ('NewCo', '55555')]


def test_bulk_create_catches_duplicate_created_during_confirmation_wait(qapp, tmp_path, monkeypatch):
    """Regression test for review finding 2 (issue #293): the duplicate
    confirmation dialog blocks indefinitely with no timeout. A job matching
    a row that *wasn't* flagged as a duplicate by the initial scan can still
    be created externally (e.g. another workstation on a shared network
    path) while that dialog is open. The post-dialog recheck must catch it
    so create_single_job() isn't called for it a second time.
    """
    cf_root = tmp_path / 'customer_files'
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
        "Acme,77777,PO2,Created During Wait\n"
        "NewCo,55555,PO3,Genuinely New Job\n"
    )

    def question_creates_job_externally(*args, **kwargs):
        # Simulates another workstation creating this job on disk while the
        # confirmation dialog is blocking on user input here.
        (cf_root / 'Acme' / '77777_CreatedExternally').mkdir(parents=True)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, 'question', question_creates_job_externally)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    dialog.create_bulk_jobs()

    # 77777 was clean during the initial scan but created externally during
    # the confirmation wait — the recheck must catch it and skip it, not
    # call create_single_job() on top of the folder that now already exists.
    assert job_module.calls == [('NewCo', '55555')]
