"""Tests for JobDocsMainWindow.add_to_history() (issue #285) — quote (and any
non-'job') entries must not be silently dropped. Requires a real (offscreen)
QApplication since JobDocsMainWindow is a QMainWindow.
"""

import os

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_window(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'get_config_dir', lambda: tmp_path)
    return main.JobDocsMainWindow()


class TestAddToHistoryIsGeneric:
    def test_quote_entries_are_recorded_not_dropped(self, qapp, tmp_path, monkeypatch):
        win = _make_window(tmp_path, monkeypatch)

        win.add_to_history('quote', {
            'customer': 'Acme', 'quote_number': '99001', 'description': 'Bracket quote',
        })

        recent_quotes = win.history.get('recent_quotes', [])
        assert len(recent_quotes) == 1
        assert recent_quotes[0]['quote_number'] == '99001'
        assert recent_quotes[0]['customer'] == 'Acme'
        assert 'date' in recent_quotes[0]
        assert win.history['customers']['Acme']

    def test_job_entries_still_work_as_before(self, qapp, tmp_path, monkeypatch):
        win = _make_window(tmp_path, monkeypatch)

        win.add_to_history('job', {'customer': 'Acme', 'job_number': '12345'})

        recent_jobs = win.history.get('recent_jobs', [])
        assert len(recent_jobs) == 1
        assert recent_jobs[0]['job_number'] == '12345'

    def test_job_and_quote_histories_are_independent(self, qapp, tmp_path, monkeypatch):
        win = _make_window(tmp_path, monkeypatch)

        win.add_to_history('job', {'customer': 'Acme', 'job_number': '12345'})
        win.add_to_history('quote', {'customer': 'Acme', 'quote_number': '99001'})

        assert len(win.history.get('recent_jobs', [])) == 1
        assert len(win.history.get('recent_quotes', [])) == 1

    def test_arbitrary_plugin_entry_type_is_recorded_generically(self, qapp, tmp_path, monkeypatch):
        # Matches modules/_template/module.py's documented plugin example:
        # add_to_history('my_entry_type', {...}) should not silently no-op.
        win = _make_window(tmp_path, monkeypatch)

        win.add_to_history('my_entry_type', {'key': 'value'})

        assert win.history.get('recent_my_entry_types') == [
            {'key': 'value', 'date': win.history['recent_my_entry_types'][0]['date']}
        ]

    def test_entries_persist_to_disk(self, qapp, tmp_path, monkeypatch):
        win = _make_window(tmp_path, monkeypatch)
        win.add_to_history('quote', {'customer': 'Acme', 'quote_number': '99001'})

        import json
        saved = json.loads(win.history_file.read_text())
        assert saved['recent_quotes'][0]['quote_number'] == '99001'
