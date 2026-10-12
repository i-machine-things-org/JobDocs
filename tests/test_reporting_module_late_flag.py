"""Tests for Job Report's "Scheduled End Date past Promise Date" flag.

Only covers _is_past_promise(), a pure function -- no DB/QApplication needed.
See experimental/README.md / modules/reporting/module.py for where it's
applied (report_table cell background, and the matching xlsx export fill).
"""

from modules.reporting.module import _is_past_promise


def test_flags_scheduled_end_after_promise():
    assert _is_past_promise('2026-06-01', '2026-05-01') is True


def test_does_not_flag_scheduled_end_before_promise():
    assert _is_past_promise('2026-04-01', '2026-05-01') is False


def test_does_not_flag_equal_dates():
    assert _is_past_promise('2026-05-01', '2026-05-01') is False


def test_does_not_flag_when_scheduled_end_is_blank():
    assert _is_past_promise('', '2026-05-01') is False


def test_does_not_flag_when_promise_date_is_blank():
    assert _is_past_promise('2026-05-01', '') is False


def test_does_not_flag_when_both_blank():
    assert _is_past_promise('', '') is False
