"""Tests for the "Job Report" row formatter in experimental/db_integration.py.

Only covers _rows_from_job_report(), a pure function -- no DB connection
needed. The query itself was validated by hand against a live JobBOSS
schema (see experimental/README.md's "Job Report field mapping" note).
"""

from datetime import datetime

from experimental.db_integration import REPORT_TYPES, _rows_from_job_report


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
        'Promised_Date': datetime(2027, 2, 24),
    }]
    rows = _rows_from_job_report(raw)
    assert rows == [{
        'classification': '', 'job': '30309', 'customer': 'BRADKEN',
        'po': '2102543', 'line': '1', 'drawing': 'DF56561',
        'part_number': 'M2550752-1  DF56561-1-2', 'revision': '7',
        'description': 'STBD END PLATE - ROUGH MACHINE',
        'order_date': '2026-09-24', 'order_qty': '1', 'sched_end': '',
        'promise_date': '2027-02-24', 'status': 'Active',
        'notes': 'DPAS  DO-A3',
    }]


def test_formats_blank_row_without_crashing():
    raw = [{
        'Job': '1', 'Customer': None, 'Customer_PO': None,
        'Customer_PO_LN': None, 'Drawing': None, 'Part_Number': None,
        'Rev': None, 'Description': None, 'Order_Date': None,
        'Order_Quantity': None, 'Sched_End': None, 'Status': None,
        'Note_Text': None, 'Promised_Date': None,
    }]
    rows = _rows_from_job_report(raw)
    assert rows == [{
        'classification': '', 'job': '1', 'customer': '', 'po': '',
        'line': '', 'drawing': '', 'part_number': '', 'revision': '',
        'description': '', 'order_date': '', 'order_qty': '', 'sched_end': '',
        'promise_date': '', 'status': '', 'notes': '',
    }]
