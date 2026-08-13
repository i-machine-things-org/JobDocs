"""Tests for HistoryModule showing both jobs and quotes (issue #285)."""

import os

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from modules.history.module import HistoryModule  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_context(history):
    return AppContext(
        settings={},
        history=history,
        config_dir=None,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )


def test_history_table_shows_jobs_and_quotes_sorted_by_date(qapp):
    history = {
        'recent_jobs': [
            {'date': '2026-08-01T10:00:00', 'customer': 'Acme', 'job_number': '12345', 'po_number': 'PO1'},
        ],
        'recent_quotes': [
            {'date': '2026-08-02T10:00:00', 'customer': 'Acme', 'quote_number': '99001'},
        ],
    }
    m = HistoryModule()
    m.initialize(_make_context(history))
    m.get_widget()
    m.refresh_history()

    assert m.history_table.rowCount() == 2
    # Newest first: the quote (08-02) before the job (08-01).
    assert m.history_table.item(0, 1).text() == 'Quote'
    assert m.history_table.item(0, 3).text() == '99001'
    assert m.history_table.item(1, 1).text() == 'Job'
    assert m.history_table.item(1, 3).text() == '12345'
    assert m.history_table.item(1, 4).text() == 'PO1'


def test_refresh_history_tolerates_null_date(qapp):
    """Regression test (blind review finding on PR #307): a malformed/hand-edited
    or merge-conflicted history.json can have a 'date' key present but set to
    JSON null (Python None) rather than absent. datetime.fromisoformat(None)
    raises TypeError, not ValueError -- refresh_history()'s _sort_key() helper
    must not let that propagate, since an uncaught exception here aborts the
    whole app (no custom sys.excepthook is installed).
    """
    history = {
        'recent_jobs': [
            {'date': None, 'customer': 'Acme', 'job_number': '12345'},
        ],
        'recent_quotes': [
            {'date': '2026-08-02T10:00:00', 'customer': 'Acme', 'quote_number': '99001'},
        ],
    }
    m = HistoryModule()
    m.initialize(_make_context(history))
    m.get_widget()

    # Must not raise.
    m.refresh_history()

    assert m.history_table.rowCount() == 2
    # The null-date job sorts as the oldest (float('-inf') fallback) and its
    # display column falls back to "Unknown" rather than crashing.
    assert m.history_table.item(0, 1).text() == 'Quote'
    assert m.history_table.item(1, 1).text() == 'Job'
    assert m.history_table.item(1, 0).text() == 'Unknown'


def test_refresh_history_tolerates_mixed_naive_and_aware_dates(qapp):
    """Regression test (CodeRabbit finding on PR #307): entries.sort() raises
    TypeError if _sort_key() returns raw datetime objects with inconsistent
    tzinfo-awareness -- e.g. a synced entry with an offset ("+00:00") next to
    a locally-written naive one. Returning a numeric timestamp instead keeps
    every key directly comparable regardless of awareness.
    """
    history = {
        'recent_jobs': [
            {'date': '2026-08-01T10:00:00', 'customer': 'Acme', 'job_number': '12345'},
        ],
        'recent_quotes': [
            {'date': '2026-08-02T10:00:00+00:00', 'customer': 'Acme', 'quote_number': '99001'},
        ],
    }
    m = HistoryModule()
    m.initialize(_make_context(history))
    m.get_widget()

    # Must not raise TypeError from comparing naive vs. offset-aware datetimes.
    m.refresh_history()

    assert m.history_table.rowCount() == 2
    # Newest first: the offset-aware quote (08-02) before the naive job (08-01).
    assert m.history_table.item(0, 1).text() == 'Quote'
    assert m.history_table.item(1, 1).text() == 'Job'


def test_clear_history_clears_both_jobs_and_quotes(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    history = {
        'recent_jobs': [{'date': '2026-08-01T10:00:00', 'customer': 'Acme', 'job_number': '12345'}],
        'recent_quotes': [{'date': '2026-08-01T10:00:00', 'customer': 'Acme', 'quote_number': '99001'}],
    }
    m = HistoryModule()
    m.initialize(_make_context(history))
    m.get_widget()

    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a, **k: None)

    m.clear_history()

    assert history['recent_jobs'] == []
    assert history['recent_quotes'] == []
    assert m.history_table.rowCount() == 0
