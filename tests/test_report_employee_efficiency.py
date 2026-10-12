"""Tests for Employee Efficiency (modules/reporting/reports/employee_efficiency.py).

Covers _rows_from_detail(), _rows_from_summary(), and the
_compute_adj_hrs_and_efficiency() stub -- all pure functions, no DB needed.
See that module's docstring for why "Adj E Hrs" is still excluded, and why
Job_Operation.Efficiency_Pct was tried and dropped again (confirmed garbage
against the real server -- flat 100.0 for every employee).
"""

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.employee_efficiency import (
    _EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY,
    _compute_adj_hrs_and_efficiency, _rows_from_detail, _rows_from_summary,
)


def test_both_types_are_registered():
    assert "Employee Efficiency - Detail" in REPORT_TYPES
    assert "Employee Efficiency - Summary" in REPORT_TYPES


def test_both_queries_exclude_indirect_jobs():
    # Regression guard: indirect (non-production) job time must never count
    # toward an employee's hours/efficiency. Checks the filter text is still
    # present, not that it's correct against live data (can't verify that
    # from here) -- catches someone accidentally dropping it later.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "JOIN Job j ON j.Job = jo.Job" in query
        assert "Type <> 'Indirect'" in query


def test_detail_formats_populated_row():
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Job': '30309', 'Work_Center': 'CNC MILL', 'Operation_Service': '20',
        'Setup_Act_Hrs': 1.5, 'Setup_Est_Hrs': 1.25,
        'Run_Act_Hrs': 4.0, 'Run_Est_Hrs': 3.75, 'Run_Qty': 50,
    }]
    rows = _rows_from_detail(raw)
    assert rows == [{
        'employee': 'John Smith', 'job': '30309', 'work_center': 'CNC MILL',
        'operation': '20', 'setup_act_hrs': '1.50', 'setup_est_hrs': '1.25',
        'run_act_hrs': '4.00', 'run_est_hrs': '3.75', 'run_qty': '50',
        # (1.25 + 3.75) / (1.5 + 4.0) * 100 = 5.0 / 5.5 * 100
        'est_act_pct': '90.9',
    }]


def test_detail_falls_back_to_employee_code_when_name_blank():
    raw = [{
        'Employee': 'A1234', 'First_Name': None, 'Last_Name': None,
        'Job': '1', 'Work_Center': '', 'Operation_Service': '',
        'Setup_Act_Hrs': None, 'Setup_Est_Hrs': None,
        'Run_Act_Hrs': None, 'Run_Est_Hrs': None, 'Run_Qty': None,
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['employee'] == 'A1234'
    assert rows[0]['setup_act_hrs'] == '0.00'
    assert rows[0]['run_qty'] == '0'
    assert rows[0]['est_act_pct'] == ''  # 0 Act Hrs -- nothing to divide by, not "0% efficient"


def test_summary_formats_populated_row():
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Total_Act_Hrs': 12.5, 'Total_Est_Hrs': 11.0,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{
        'employee': 'John Smith', 'total_act_hrs': '12.50', 'total_est_hrs': '11.00',
        'est_act_pct': '88.0',
    }]


def test_summary_handles_zero_hours_without_crashing():
    raw = [{'Employee': 'B5678', 'First_Name': None, 'Last_Name': None, 'Total_Act_Hrs': None, 'Total_Est_Hrs': None}]
    rows = _rows_from_summary(raw)
    assert rows == [{'employee': 'B5678', 'total_act_hrs': '0.00', 'total_est_hrs': '0.00', 'est_act_pct': ''}]


def test_adj_hrs_stub_always_returns_none():
    assert _compute_adj_hrs_and_efficiency(10.0, 8.0, 50) is None
    assert _compute_adj_hrs_and_efficiency(0.0, 0.0, None) is None
