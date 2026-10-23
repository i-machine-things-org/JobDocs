"""Tests for Job Report (modules/reporting/reports/job_report.py).

Covers _rows_from_job_report() and _is_past_promise(), both pure functions --
no DB/QApplication needed. The query itself was validated by hand against a
live JobBOSS schema (see modules/reporting/README.md's "Job Report" section).
"""

from datetime import datetime

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.job_report import _is_past_promise, _rows_from_job_report


def test_job_report_is_registered():
    assert "Job Report" in REPORT_TYPES


def test_formats_populated_row():
    raw = [{
        'Job': '30309', 'Customer': 'BRADKEN', 'Customer_PO': '2102543',
        'Customer_PO_LN': '1', 'Drawing': 'DF56561',
        'Part_Number': 'M2550752-1  DF56561-1-2', 'Rev': '7',
        'Description': 'STBD END PLATE - ROUGH MACHINE',
        'Order_Date': datetime(2026, 9, 24), 'Order_Quantity': 1,
        'Sched_End': None, 'Status': 'Active', 'Note_Text': 'DPAS  DO-A3',
        'Promised_Date': datetime(2027, 2, 24), 'Curr_WC': 'CNC MILL',
    }]
    rows = _rows_from_job_report(raw)
    assert rows == [{
        'classification': '', 'job': '30309', 'customer': 'BRADKEN',
        'po': '2102543', 'line': '1', 'drawing': 'DF56561',
        'part_number': 'M2550752-1  DF56561-1-2', 'revision': '7',
        'description': 'STBD END PLATE - ROUGH MACHINE',
        'order_date': '2026-09-24', 'order_qty': '1', 'sched_end': '',
        'promise_date': '2027-02-24', 'status': 'Active',
        'curr_wc': 'CNC MILL', 'notes': 'DPAS  DO-A3',
    }]


def test_formats_blank_row_without_crashing():
    raw = [{
        'Job': '1', 'Customer': None, 'Customer_PO': None,
        'Customer_PO_LN': None, 'Drawing': None, 'Part_Number': None,
        'Rev': None, 'Description': None, 'Order_Date': None,
        'Order_Quantity': None, 'Sched_End': None, 'Status': None,
        'Note_Text': None, 'Promised_Date': None, 'Curr_WC': None,
    }]
    rows = _rows_from_job_report(raw)
    assert rows == [{
        'classification': '', 'job': '1', 'customer': '', 'po': '',
        'line': '', 'drawing': '', 'part_number': '', 'revision': '',
        'description': '', 'order_date': '', 'order_qty': '', 'sched_end': '',
        'promise_date': '', 'status': '', 'curr_wc': '', 'notes': '',
    }]


def test_curr_wc_blank_when_job_has_no_open_operation():
    """OUTER APPLY, not CROSS APPLY -- a job with no non-complete
    Job_Operation row (or no operations at all) still appears in the report,
    just with a blank Current Work Center, rather than being silently
    dropped. Simulated here as the DB simply returning no Curr_WC key/value
    for that row (same as the SQL producing NULL).
    """
    raw = [{
        'Job': '2', 'Customer': 'ACME', 'Customer_PO': None,
        'Customer_PO_LN': None, 'Drawing': None, 'Part_Number': None,
        'Rev': None, 'Description': None, 'Order_Date': None,
        'Order_Quantity': None, 'Sched_End': None, 'Status': 'Active',
        'Note_Text': None, 'Promised_Date': None, 'Curr_WC': None,
    }]
    rows = _rows_from_job_report(raw)
    assert rows[0]['job'] == '2'
    assert rows[0]['curr_wc'] == ''


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
