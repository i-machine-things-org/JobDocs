"""Tests for Job Report (modules/reporting/reports/job_report.py).

Covers _rows_from_job_report() and _is_past_promise(), both pure functions --
no DB/QApplication needed. The query itself was validated by hand against a
live JobBOSS schema (see modules/reporting/README.md's "Job Report" section).
"""

from datetime import datetime

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.job_report import (
    _JOB_REPORT_QUERY, _is_past_promise, _rows_from_job_report, _strip_blank_lines,
)


def test_job_report_is_registered():
    assert "Job Report" in REPORT_TYPES


def test_query_selects_promise_date_and_shipping_instructions_from_same_delivery_row():
    """_rows_from_job_report() is tested below by feeding it a raw dict
    directly, which would still pass even if the query itself stopped
    selecting Shipping Instructions, or started pulling it from a different
    Delivery row than Promise Date. Assert the query text itself, so a
    regression there is caught independently of that row-formatter test.
    """
    assert "dlv.Promised_Date, dlv.Comment AS Shipping_Instructions, cur.Curr_WC" in _JOB_REPORT_QUERY
    assert (
        "SELECT TOP 1 d.Promised_Date, d.Comment\n"
        "    FROM Delivery d\n"
        "    WHERE d.Job = j.Job\n"
        "    ORDER BY CASE WHEN d.Remaining_Quantity > 0 THEN 0 ELSE 1 END, d.Promised_Date ASC"
    ) in _JOB_REPORT_QUERY


def test_formats_populated_row():
    raw = [{
        'Job': '30309', 'Customer': 'BRADKEN', 'Customer_PO': '2102543',
        'Customer_PO_LN': '1', 'Drawing': 'DF56561',
        'Part_Number': 'M2550752-1  DF56561-1-2', 'Rev': '7',
        'Description': 'STBD END PLATE - ROUGH MACHINE',
        'Order_Date': datetime(2026, 9, 24), 'Order_Quantity': 1,
        'Sched_End': None, 'Status': 'Active', 'Note_Text': 'DPAS  DO-A3',
        'Promised_Date': datetime(2027, 2, 24), 'Curr_WC': 'CNC MILL',
        'Shipping_Instructions': 'DPAS  DO-A3\r\nSN#M250054-10\r\nN1\r\n',
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
        'shipping_instructions': 'DPAS  DO-A3\nSN#M250054-10\nN1',
    }]


def test_formats_blank_row_without_crashing():
    raw = [{
        'Job': '1', 'Customer': None, 'Customer_PO': None,
        'Customer_PO_LN': None, 'Drawing': None, 'Part_Number': None,
        'Rev': None, 'Description': None, 'Order_Date': None,
        'Order_Quantity': None, 'Sched_End': None, 'Status': None,
        'Note_Text': None, 'Promised_Date': None, 'Curr_WC': None,
        'Shipping_Instructions': None,
    }]
    rows = _rows_from_job_report(raw)
    assert rows == [{
        'classification': '', 'job': '1', 'customer': '', 'po': '',
        'line': '', 'drawing': '', 'part_number': '', 'revision': '',
        'description': '', 'order_date': '', 'order_qty': '', 'sched_end': '',
        'promise_date': '', 'status': '', 'curr_wc': '', 'notes': '',
        'shipping_instructions': '',
    }]


def test_notes_also_strips_blank_lines():
    """Note_Text gets the same blank-line treatment as Shipping Instructions
    -- both are free-text JobBOSS fields entered the same blank-separated way.
    """
    raw = [{
        'Job': '30309', 'Customer': 'BRADKEN', 'Customer_PO': None,
        'Customer_PO_LN': None, 'Drawing': None, 'Part_Number': None,
        'Rev': None, 'Description': None, 'Order_Date': None,
        'Order_Quantity': None, 'Sched_End': None, 'Status': 'Active',
        'Note_Text': 'DPAS  D0-A3\r\n\r\nSN#M250054-10\r\n',
        'Promised_Date': None, 'Curr_WC': None, 'Shipping_Instructions': None,
    }]
    rows = _rows_from_job_report(raw)
    assert rows[0]['notes'] == 'DPAS  D0-A3\nSN#M250054-10'


def test_strip_blank_lines_drops_gaps_between_entries():
    """Delivery.Comment is typically entered one instruction per line with a
    blank line between each (e.g. "MTL ORDERED\\r\\n\\r\\nADVANCED BRONZE\\r\\n\\r\\n11/9/26")
    -- a table cell has no room to reproduce those gaps faithfully, so they're
    dropped while keeping each real line on its own line.
    """
    raw = 'MTL ORDERED\r\n\r\nADVANCED BRONZE\r\n\r\n11/9/26\r\n'
    assert _strip_blank_lines(raw) == 'MTL ORDERED\nADVANCED BRONZE\n11/9/26'


def test_strip_blank_lines_empty_string():
    assert _strip_blank_lines('') == ''


def test_strip_blank_lines_keeps_leading_indentation_on_continuation_lines():
    """Only the blank-line gaps should go -- a continuation line indented to
    show it belongs under the line above (e.g. a sub-item) must keep that
    indentation, not just its non-blank content.
    """
    raw = 'MAIN ITEM\r\n  - sub item\r\n\r\nSECOND ITEM\r\n'
    assert _strip_blank_lines(raw) == 'MAIN ITEM\n  - sub item\nSECOND ITEM'


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
