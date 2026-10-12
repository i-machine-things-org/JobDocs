"""Tests for Report Builder's generic query-building and row-formatting in
experimental/db_integration.py.

Only covers the pure functions (_build_custom_report_query,
_rows_from_custom_report) -- no DB connection needed. The underlying columns
were validated by hand against a live JobBOSS schema as part of the "Job
Report" work (see experimental/README.md); this is pure recombination of
those same already-verified columns, selected dynamically.
"""

from datetime import datetime

from experimental.db_integration import (
    AVAILABLE_FIELDS,
    REPORT_TYPES,
    _build_custom_report_query,
    _rows_from_custom_report,
)


def test_report_builder_is_registered():
    assert "Report Builder" in REPORT_TYPES


def test_query_includes_delivery_join_only_when_promise_date_picked():
    query_without, keys_without = _build_custom_report_query(['job', 'customer'])
    assert 'OUTER APPLY' not in query_without
    assert keys_without == ['job', 'customer']

    query_with, keys_with = _build_custom_report_query(['job', 'promise_date'])
    assert 'OUTER APPLY' in query_with
    assert 'Delivery' in query_with
    assert keys_with == ['job', 'promise_date']


def test_unknown_field_keys_are_dropped_not_interpolated():
    query, valid_keys = _build_custom_report_query(['job', "'; DROP TABLE Job; --", 'bogus'])
    assert valid_keys == ['job']
    assert 'DROP TABLE' not in query
    assert 'bogus' not in query


def test_query_selects_every_requested_field_with_its_alias():
    all_keys = [key for key, _label, _expr in AVAILABLE_FIELDS]
    query, valid_keys = _build_custom_report_query(all_keys)
    assert valid_keys == all_keys
    for key, _label, expr in AVAILABLE_FIELDS:
        assert f"{expr} AS {key}" in query


def test_formats_populated_row():
    raw = [{'job': '30309', 'customer': 'BRADKEN', 'order_date': datetime(2026, 9, 24),
            'total_price': None}]
    rows = _rows_from_custom_report(raw, ['job', 'customer', 'order_date', 'total_price'])
    assert rows == [{
        'job': '30309', 'customer': 'BRADKEN',
        'order_date': '2026-09-24', 'total_price': '',
    }]


def test_formats_only_the_requested_keys():
    raw = [{'job': '1', 'customer': 'ACME', 'status': 'Active'}]
    rows = _rows_from_custom_report(raw, ['job'])
    assert rows == [{'job': '1'}]


def test_formats_blank_row_without_crashing():
    raw = [{'job': '1', 'customer': None, 'order_date': None}]
    rows = _rows_from_custom_report(raw, ['job', 'customer', 'order_date'])
    assert rows == [{'job': '1', 'customer': '', 'order_date': ''}]
