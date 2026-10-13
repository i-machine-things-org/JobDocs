"""Tests for Employee Efficiency (modules/reporting/reports/employee_efficiency.py).

Covers _rows_from_detail() and _rows_from_summary() -- pure functions, no DB
needed. See that module's docstring for the real JobBOSS formula (ECI KB
article #000012591: Adj Hrs = Act_Run_Qty * Est_Run_Per_Part, % Eff =
Adj Hrs / Act_Run_Hrs -- Setup excluded entirely), the three earlier wrong
attempts it replaces, the qty-sanity guard added after a real operation
(Est_Required_Qty=1, Act_Run_Qty=5,629) blew one employee's % Eff up to
796%, and the two rules confirmed directly from JobBOSS's own report source
(Rework_Time=0, and quantity zeroed when Run Act Hrs is 0).
"""

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.employee_efficiency import (
    _EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY, _QTY_SANITY_MULTIPLIER,
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
    # Run_Qty * Est_Run_Per_Part, not the raw SUM()/MAX() inline, since both
    # are computed once in a CTE (see test_both_queries_zero_run_qty_when_no_run_act_hrs).
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "Run_Qty * " in query and "Est_Run_Per_Part" in query


def test_both_queries_exclude_rework_time():
    # Regression guard: confirmed from JobBOSS's own report source
    # (LR_EmployeeEfficiency_Rpt.htm) -- every query there filters
    # Rework_Time=0. Rework entries never counted toward Act hours or Adj
    # Hrs here before this was found; must never silently come back.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "jot.Rework_Time = 0" in query


def test_both_queries_zero_run_qty_when_no_run_act_hrs():
    # Regression guard: also confirmed from JobBOSS's own report source --
    # IIF(ARHSum=0, 0, ARQSum). If an employee logged zero actual run hours
    # for an operation, the reported quantity must be forced to 0 too,
    # regardless of what Act_Run_Qty itself summed to.
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        assert "WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty" in query


def test_both_queries_guard_against_implausible_run_qty():
    # Regression guard for the qty-sanity fix -- a real operation
    # (Est_Required_Qty=1, Act_Run_Qty=5,629) produced a 796% % Eff for one
    # employee until this landed. Checks the guard references
    # Est_Required_Qty and the shared multiplier constant, not that it's the
    # right multiplier (can't verify that from here).
    for query in (_EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY):
        formatted = query.format(employee_clause="1=1", qty_multiplier=_QTY_SANITY_MULTIPLIER)
        assert "Est_Required_Qty" in formatted
        assert f"* {_QTY_SANITY_MULTIPLIER}" in formatted


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
    # Adj_Hrs is None here (no Run_Act_Hrs to begin with) -- blank, not "0.00"
    assert rows[0]['adj_hrs'] == ''
    assert rows[0]['pct_eff'] == ''


def test_detail_blanks_adj_hrs_and_pct_eff_when_sql_flags_the_row():
    # The SQL returns Adj_Hrs = NULL (not 0) for a row the qty-sanity guard
    # excludes -- same signal as "no Run component at all". The formatter
    # must not coerce this to 0 and compute a fake "0.0%"; it must blank
    # both cells, even though Run Act Hrs is a real, nonzero, informational
    # number that's still shown.
    raw = [{
        'Employee': '***REDACTED***', 'First_Name': 'Tyler', 'Last_Name': 'Smith',
        'Job': '29718', 'Work_Center': 'CNC HMC', 'Operation_Service': 'OP6',
        'Setup_Act_Hrs': 2.0, 'Setup_Est_Hrs': 1.5,
        'Run_Act_Hrs': 10.0, 'Run_Est_Hrs': 1.75, 'Run_Qty': 5629,
        'Adj_Hrs': None,  # flagged: 5629 >> Est_Required_Qty(1) * multiplier
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['run_act_hrs'] == '10.00'  # still shown -- real hours were logged
    assert rows[0]['adj_hrs'] == ''
    assert rows[0]['pct_eff'] == ''


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
