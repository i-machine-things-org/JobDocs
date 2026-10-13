"""Tests for Employee Efficiency (modules/reporting/reports/employee_efficiency.py).

Covers _rows_from_detail() and _rows_from_summary() -- pure functions, no DB
needed. See that module's docstring for the real JobBOSS formula (ECI KB
article #000012591: Adj Hrs = Act_Run_Qty * Est_Run_Per_Part, % Eff =
Adj Hrs / Act_Run_Hrs -- Setup excluded entirely) and the three earlier
wrong attempts it replaces.
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
    # Indirect (Work_Center.Type), not the job.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center" in query
        assert "wc.Type <> 'Indirect'" in query


def test_both_queries_compute_adj_hrs_from_run_qty_times_est_run_per_part():
    # Regression guard for the real formula (ECI KB #000012591) -- catches
    # someone reintroducing one of the three rejected formulas instead.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "Act_Run_Qty) * MAX(jo.Est_Run_Per_Part)" in query


def test_detail_formats_populated_row():
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Job': '30309', 'Work_Center': 'CNC MILL', 'Operation_Service': '20',
        'Setup_Act_Hrs': 1.5, 'Setup_Est_Hrs': 1.25,
        'Run_Act_Hrs': 4.0, 'Run_Est_Hrs': 3.75, 'Run_Qty': 50,
        'Adj_Hrs': 3.6,
    }]
    rows = _rows_from_detail(raw)
    assert rows == [{
        'employee': 'John Smith', 'job': '30309', 'work_center': 'CNC MILL',
        'operation': '20', 'setup_act_hrs': '1.50', 'setup_est_hrs': '1.25',
        'run_act_hrs': '4.00', 'run_est_hrs': '3.75', 'run_qty': '50',
        'adj_hrs': '3.60',
        # 3.6 / 4.0 * 100 -- Setup Act Hrs (1.5) does NOT enter this ratio
        'pct_eff': '90.0',
    }]


def test_detail_matches_eci_kb_worked_example():
    # ECI KB 000012591's own worked example: Make Qty 100 @ 30 parts/hr ->
    # Est_Run_Per_Part = (100/30)/100; a 2 Act Hr entry with Run Qty 25
    # gives Adj Hrs ~0.83, % Eff ~41.5%. Adj_Hrs here is what the query
    # would compute (Act_Run_Qty * Est_Run_Per_Part), not re-derived.
    est_run_per_part = (100 / 30) / 100
    raw = [{
        'Employee': 'E1', 'First_Name': None, 'Last_Name': None,
        'Job': 'J1', 'Work_Center': 'WC1', 'Operation_Service': 'OP1',
        'Setup_Act_Hrs': 0, 'Setup_Est_Hrs': 0,
        'Run_Act_Hrs': 2.0, 'Run_Est_Hrs': 3.33, 'Run_Qty': 25,
        'Adj_Hrs': 25 * est_run_per_part,
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['adj_hrs'] == '0.83'
    assert rows[0]['pct_eff'] == '41.7'  # article hand-rounds to 41.5% using a truncated intermediate


def test_detail_falls_back_to_employee_code_when_name_blank():
    raw = [{
        'Employee': 'A1234', 'First_Name': None, 'Last_Name': None,
        'Job': '1', 'Work_Center': '', 'Operation_Service': '',
        'Setup_Act_Hrs': None, 'Setup_Est_Hrs': None,
        'Run_Act_Hrs': None, 'Run_Est_Hrs': None, 'Run_Qty': None,
        'Adj_Hrs': None,
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['employee'] == 'A1234'
    assert rows[0]['setup_act_hrs'] == '0.00'
    assert rows[0]['run_qty'] == '0'
    assert rows[0]['adj_hrs'] == '0.00'
    assert rows[0]['pct_eff'] == ''  # 0 Run Act Hrs -- nothing to divide by


def test_summary_formats_populated_row():
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Total_Act_Hrs': 12.5, 'Total_Est_Hrs': 11.0, 'Run_Act_Hrs': 10.0, 'Adj_Hrs': 8.0,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{
        'employee': 'John Smith', 'total_act_hrs': '12.50', 'total_est_hrs': '11.00',
        'run_act_hrs': '10.00', 'adj_hrs': '8.00',
        # 8.0 / 10.0 * 100 -- NOT 8.0 / 12.5 (Total Act Hrs includes Setup, % Eff must not)
        'pct_eff': '80.0',
    }]


def test_summary_handles_zero_hours_without_crashing():
    raw = [{
        'Employee': 'B5678', 'First_Name': None, 'Last_Name': None,
        'Total_Act_Hrs': None, 'Total_Est_Hrs': None, 'Run_Act_Hrs': None, 'Adj_Hrs': None,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{
        'employee': 'B5678', 'total_act_hrs': '0.00', 'total_est_hrs': '0.00',
        'run_act_hrs': '0.00', 'adj_hrs': '0.00', 'pct_eff': '',
    }]
