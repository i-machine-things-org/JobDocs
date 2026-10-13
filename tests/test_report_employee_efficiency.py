"""Tests for Employee Efficiency (modules/reporting/reports/employee_efficiency.py).

Covers _rows_from_detail() and _rows_from_summary() -- pure functions, no DB
needed. See that module's docstring for the three Adj Hrs / % Eff formulas
tried and dropped (naive Est/Act ratio, Job_Operation.Efficiency_Pct,
Setup/Run_Pct_Complete-based) -- v1 ships only directly-sourced Hours/Qty
columns.
"""

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.employee_efficiency import (
    _EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY,
    _rows_from_detail, _rows_from_summary,
)


def test_both_types_are_registered():
    assert "Employee Efficiency - Detail" in REPORT_TYPES
    assert "Employee Efficiency - Summary" in REPORT_TYPES


def test_both_queries_exclude_indirect_work_centers():
    # Regression guard: indirect (non-production) time must never count
    # toward an employee's hours. It's the WORK CENTER that's marked
    # Indirect (Work_Center.Type), not the job -- confirmed directly from
    # this shop's Work Center setup screen after an earlier wrong attempt
    # filtered on Job.Type instead, which doesn't carry this value. Checks
    # the filter text is still present, not that it's correct against live
    # data (can't verify that from here) -- catches someone accidentally
    # dropping it, or reverting to the wrong Job.Type version, later.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center" in query
        assert "wc.Type <> 'Indirect'" in query


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


def test_summary_formats_populated_row():
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Total_Act_Hrs': 12.5, 'Total_Est_Hrs': 11.0,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{'employee': 'John Smith', 'total_act_hrs': '12.50', 'total_est_hrs': '11.00'}]


def test_summary_handles_zero_hours_without_crashing():
    raw = [{'Employee': 'B5678', 'First_Name': None, 'Last_Name': None, 'Total_Act_Hrs': None, 'Total_Est_Hrs': None}]
    rows = _rows_from_summary(raw)
    assert rows == [{'employee': 'B5678', 'total_act_hrs': '0.00', 'total_est_hrs': '0.00'}]
