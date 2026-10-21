"""Tests for Employee Efficiency (modules/reporting/reports/employee_efficiency.py).

Covers _rows_from_detail() and _rows_from_summary() -- pure functions, no DB
needed. See that module's docstring for the full evidence trail; in short:

    Adj Hrs = Est Hrs(operation) * Act Hrs(employee) / SUM(Act Hrs, all employees)
    % Eff = Adj Hrs / Act Hrs(employee) * 100

reverse-engineered by parsing two real xlsx exports cell-by-cell (JobBOSS's
own canned report and this module's own export for the same date range),
applied identically to Setup and Run. Replaces the ECI KB-article Run
formula and the "Setup Adj Hrs = Setup Est Hrs" approximation, both
confirmed wrong by live data (55.2% of real rows have Quantity=0 with a
real nonzero Adj E Hrs; Setup % Eff over 1000% for several employees under
the old approximation). Also covers the Detail grouping-key fix (group by
jot.Job_Operation, not the non-unique descriptive Job/Work_Center/
Operation_Service triple) and the two rules confirmed directly from
JobBOSS's own report source (Rework_Time=0, and Run Qty forced to 0 when
Run Act Hrs is 0).
"""

from modules.reporting.reports import REPORT_TYPES
from modules.reporting.reports.employee_efficiency import (
    EMPLOYEE_EFFICIENCY_DETAIL, EMPLOYEE_EFFICIENCY_SUMMARY,
    _EMPLOYEE_EFFICIENCY_DETAIL_QUERY, _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY, _OP_TOTALS_CTE,
    _rows_from_detail, _rows_from_summary,
)

# Both raw query strings hold {op_totals}/{employee_clause} placeholders
# (see module docstring on why .format(), not string concatenation) --
# format them once here with a harmless employee_clause so every other test
# below can just substring-match the real, fully-assembled SQL.
_DETAIL_SQL = _EMPLOYEE_EFFICIENCY_DETAIL_QUERY.format(op_totals=_OP_TOTALS_CTE, employee_clause="1=1")
_SUMMARY_SQL = _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY.format(op_totals=_OP_TOTALS_CTE, employee_clause="1=1")


def test_both_types_are_registered():
    assert "Employee Efficiency - Detail" in REPORT_TYPES
    assert "Employee Efficiency - Summary" in REPORT_TYPES


def test_both_queries_exclude_indirect_work_centers():
    # Regression guard: indirect (non-production) time must never count
    # toward an employee's hours. It's the WORK CENTER that's marked
    # Indirect (Work_Center.Type), not the job.
    for sql in (_DETAIL_SQL, _SUMMARY_SQL):
        assert "JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center" in sql
        assert "wc.Type <> 'Indirect'" in sql


def test_both_queries_exclude_rework_time():
    # Regression guard: confirmed from JobBOSS's own report source
    # (LR_EmployeeEfficiency_Rpt.htm) -- every query there filters
    # Rework_Time=0.
    for sql in (_DETAIL_SQL, _SUMMARY_SQL):
        assert "jot.Rework_Time = 0" in sql


def test_both_queries_zero_run_qty_when_no_run_act_hrs():
    # Regression guard: also confirmed from JobBOSS's own report source --
    # IIF(ARHSum=0, 0, ARQSum). Detail still shows Run Qty as an
    # informational column; Summary doesn't show it at all, but the SQL
    # computing it (Detail only) must still apply this rule.
    assert "WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty" in _DETAIL_SQL


def test_detail_groups_by_job_operation_not_descriptive_triple():
    # Regression guard for the grouping-key fix: Detail used to group by
    # (Job, Work_Center, Operation_Service), which isn't unique -- 303 real
    # (employee, Job, Work_Center, Operation_Service) combinations in a real
    # export turned out to be two genuinely distinct operations sharing a
    # display label. Must group by jot.Job_Operation like Summary always did.
    assert "GROUP BY jot.Employee, jot.Job_Operation, jo.Job, jo.Work_Center, jo.Operation_Service" in _DETAIL_SQL


def test_both_queries_compute_adj_hrs_via_proportional_share():
    # Regression guard for the real formula: Est Hrs * this employee's Act
    # Hrs / SUM(Act Hrs across every employee on that operation) -- for
    # both Setup and Run. Catches someone reintroducing a quantity-based
    # formula (the ECI KB article's, or "Setup Adj Hrs = Setup Est Hrs"),
    # both confirmed wrong against real data.
    for sql in (_DETAIL_SQL, _SUMMARY_SQL):
        assert "Total_Setup_Act_Hrs" in sql and "Total_Run_Act_Hrs" in sql
        assert "Setup_Est_Hrs * " in sql and "Setup_Act_Hrs / ot.Total_Setup_Act_Hrs" in sql
        assert "Run_Est_Hrs * " in sql and "Run_Act_Hrs / ot.Total_Run_Act_Hrs" in sql


def test_op_totals_denominator_is_not_employee_filtered():
    # Regression guard: the proportional-share denominator must sum Act Hrs
    # across EVERY employee who touched an operation, not just the ones the
    # Employee filter picked -- otherwise the share calculation is circular.
    # The raw (unformatted) query templates carry {employee_clause} only in
    # op_detail/op_rollup, never in _OP_TOTALS_CTE itself.
    assert "{employee_clause}" not in _OP_TOTALS_CTE


def test_both_queries_select_department_from_employee_not_work_center():
    # Department is Employee.Department -- the employee's own assigned
    # department -- not Work_Center.Department ("where the work happened").
    # Confirmed live: Employee.Work_Center is NULL for every active employee
    # on this install, so there's no deriving one from the other; they are
    # genuinely different columns. It's also an export-split option
    # (base.ReportDefinition.uses_department_tabs), not a query filter --
    # every department's rows are always fetched, so neither raw template
    # may carry a department-filter placeholder.
    assert "e.Department" in _EMPLOYEE_EFFICIENCY_DETAIL_QUERY
    assert "e.Department" in _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY
    assert "wc.Department" not in _EMPLOYEE_EFFICIENCY_DETAIL_QUERY
    assert "wc.Department" not in _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY
    assert "department_clause" not in _EMPLOYEE_EFFICIENCY_DETAIL_QUERY
    assert "department_clause" not in _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY


def test_summary_department_does_not_change_the_one_row_per_employee_grain():
    # Department is a 1:1 attribute of the employee (not of the operation),
    # so adding e.Department to the GROUP BY (required by SQL Server
    # whenever a non-aggregated column is selected) doesn't split a given
    # employee into multiple rows -- Summary stays one row per employee,
    # same as before Department existed, just with the column attached.
    assert "GROUP BY op.Employee, e.Department, e.First_Name, e.Last_Name" in _SUMMARY_SQL


def test_both_employee_efficiency_types_declare_department_tabs():
    assert EMPLOYEE_EFFICIENCY_DETAIL.uses_department_tabs is True
    assert EMPLOYEE_EFFICIENCY_SUMMARY.uses_department_tabs is True


def test_op_totals_excludes_inactive_employees():
    # Regression guard: confirmed live -- an inactive employee (***REDACTED***) had
    # real historical hours on an operation an active employee also worked;
    # including them in the denominator under-credited the active
    # employee's Adj Hrs, since the real report's population is Active-
    # employees-only throughout, never a mix.
    assert "te.Status = 'Active'" in _OP_TOTALS_CTE


def test_summary_never_blends_setup_and_run_hours():
    # Regression guard: Summary must never combine Setup+Run into "Total Act
    # Hrs"/"Total Est Hrs" -- the real report never does this (Setup isn't
    # part of any combined score), and Detail never did either.
    assert "Setup_Act_Hrs + " not in _SUMMARY_SQL
    assert "Setup_Est_Hrs + " not in _SUMMARY_SQL
    assert "Total_Act_Hrs" not in _SUMMARY_SQL.replace(
        "Total_Setup_Act_Hrs", "").replace("Total_Run_Act_Hrs", "")


def test_detail_formats_populated_row():
    # An operation with 2 employees contributing Run Act Hrs: this one did
    # 4.0 of a 10.0-hr total, so Adj Hrs = Run_Est(3.75) * 4.0/10.0 = 1.5,
    # % Eff = 1.5/4.0*100 = 37.5. Same shape for Setup: 1.25 of a 2.0-hr
    # total -> Adj = 1.5 * 1.25/2.0 = 0.9375, % Eff = 0.9375/1.25*100 = 75.0.
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith',
        'Job': '30309', 'Work_Center': 'CNC MILL', 'Department': 'MACHINING', 'Operation_Service': '20',
        'Setup_Act_Hrs': 1.25, 'Setup_Est_Hrs': 1.5, 'Setup_Adj_Hrs': 0.9375,
        'Run_Act_Hrs': 4.0, 'Run_Est_Hrs': 3.75, 'Run_Qty': 50, 'Run_Adj_Hrs': 1.5,
    }]
    rows = _rows_from_detail(raw)
    assert rows == [{
        'employee': 'John Smith', 'job': '30309', 'work_center': 'CNC MILL', 'department': 'MACHINING',
        'operation': '20', 'setup_act_hrs': '1.25', 'setup_est_hrs': '1.50',
        'setup_adj_hrs': '0.94', 'setup_pct_eff': '75.0',
        'run_act_hrs': '4.00', 'run_est_hrs': '3.75', 'run_qty': '50',
        'run_adj_hrs': '1.50', 'run_pct_eff': '37.5',
    }]


def test_detail_matches_real_two_employee_job_exactly():
    # Job 27652, CNC LATHE OP6 -- queried directly off the live database,
    # the strongest confirmation of the formula in this module: two real
    # employees, Setup Est/Run Est shared at 1.25 each, and the formula's
    # predicted Adj Hrs for both matches JobBOSS's own real exported values
    # exactly (see module docstring). SQL would compute Setup_Adj_Hrs/
    # Run_Adj_Hrs directly; asserted here as the pre-computed values a real
    # query would return.
    raw = [
        {
            'Employee': '***REDACTED***', 'First_Name': 'Andrew', 'Last_Name': 'Adams',
            'Job': '27652', 'Work_Center': 'CNC LATHE', 'Operation_Service': 'OP6',
            'Setup_Act_Hrs': 1.0, 'Setup_Est_Hrs': 1.25, 'Setup_Adj_Hrs': 0.5,
            'Run_Act_Hrs': 2.5, 'Run_Est_Hrs': 1.25, 'Run_Qty': 0, 'Run_Adj_Hrs': 0.78125,
        },
        {
            'Employee': '***REDACTED***', 'First_Name': 'Ryan', 'Last_Name': 'Wilmoth',
            'Job': '27652', 'Work_Center': 'CNC LATHE', 'Operation_Service': 'OP6',
            'Setup_Act_Hrs': 1.5, 'Setup_Est_Hrs': 1.25, 'Setup_Adj_Hrs': 0.75,
            'Run_Act_Hrs': 1.5, 'Run_Est_Hrs': 1.25, 'Run_Qty': 0, 'Run_Adj_Hrs': 0.46875,
        },
    ]
    rows = _rows_from_detail(raw)
    assert rows[0]['setup_adj_hrs'] == '0.50'
    assert rows[0]['run_adj_hrs'] == '0.78'
    assert rows[1]['setup_adj_hrs'] == '0.75'
    assert rows[1]['run_adj_hrs'] == '0.47'


def test_detail_falls_back_to_employee_code_when_name_blank():
    raw = [{
        'Employee': 'A1234', 'First_Name': None, 'Last_Name': None,
        'Job': '1', 'Work_Center': '', 'Operation_Service': '',
        'Setup_Act_Hrs': None, 'Setup_Est_Hrs': None, 'Setup_Adj_Hrs': None,
        'Run_Act_Hrs': None, 'Run_Est_Hrs': None, 'Run_Qty': None, 'Run_Adj_Hrs': None,
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['employee'] == 'A1234'
    assert rows[0]['setup_act_hrs'] == '0.00'
    assert rows[0]['run_qty'] == '0'
    # Setup_Adj_Hrs/Run_Adj_Hrs are both None (SQL returned NULL -- nobody,
    # across all employees, logged any Act Hrs on this operation) -- blank,
    # not "0.00"/"0.0".
    assert rows[0]['setup_adj_hrs'] == ''
    assert rows[0]['setup_pct_eff'] == ''
    assert rows[0]['run_adj_hrs'] == ''
    assert rows[0]['run_pct_eff'] == ''


def test_detail_blanks_adj_hrs_and_pct_eff_when_sql_returns_null():
    # Confirmed real case: an operation with real, nonzero Act Hrs logged,
    # but Adj Hrs is still NULL from SQL (e.g. Total_Run_Act_Hrs computed as
    # 0 for a reason that doesn't affect this row's own Act Hrs directly --
    # see module docstring's NULL-propagation note). Act Hrs must still show
    # as a real number; Adj Hrs/% Eff must blank, not show "0.00"/"0.0".
    raw = [{
        'Employee': '***REDACTED***', 'First_Name': 'Tyler', 'Last_Name': 'Smith',
        'Job': '29718', 'Work_Center': 'CNC HMC', 'Operation_Service': 'OP6',
        'Setup_Act_Hrs': 2.0, 'Setup_Est_Hrs': 1.5, 'Setup_Adj_Hrs': None,
        'Run_Act_Hrs': 10.0, 'Run_Est_Hrs': 1.75, 'Run_Qty': 5629, 'Run_Adj_Hrs': None,
    }]
    rows = _rows_from_detail(raw)
    assert rows[0]['setup_act_hrs'] == '2.00'
    assert rows[0]['setup_adj_hrs'] == ''
    assert rows[0]['setup_pct_eff'] == ''
    assert rows[0]['run_act_hrs'] == '10.00'  # still shown -- real hours were logged
    assert rows[0]['run_adj_hrs'] == ''
    assert rows[0]['run_pct_eff'] == ''


def test_summary_formats_populated_row():
    # Department included: Summary's grain is now (Employee, Department) --
    # see test_summary_grain_includes_department_not_just_employee -- so one
    # row here means one employee's hours within one department.
    raw = [{
        'Employee': 'A1234', 'First_Name': 'John', 'Last_Name': 'Smith', 'Department': 'MACHINING',
        'Setup_Act_Hrs': 2.0, 'Setup_Est_Hrs': 2.5, 'Setup_Adj_Hrs': 2.0,
        'Run_Act_Hrs': 10.0, 'Run_Est_Hrs': 9.0, 'Run_Adj_Hrs': 8.0,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{
        'employee': 'John Smith', 'department': 'MACHINING', 'setup_act_hrs': '2.00', 'setup_est_hrs': '2.50',
        'setup_adj_hrs': '2.00', 'setup_pct_eff': '100.0',  # 2.0 / 2.0 * 100
        'run_act_hrs': '10.00', 'run_est_hrs': '9.00',
        'run_adj_hrs': '8.00', 'run_pct_eff': '80.0',  # 8.0 / 10.0 * 100
    }]


def test_summary_handles_zero_hours_without_crashing():
    raw = [{
        'Employee': 'B5678', 'First_Name': None, 'Last_Name': None, 'Department': None,
        'Setup_Act_Hrs': None, 'Setup_Est_Hrs': None, 'Setup_Adj_Hrs': None,
        'Run_Act_Hrs': None, 'Run_Est_Hrs': None, 'Run_Adj_Hrs': None,
    }]
    rows = _rows_from_summary(raw)
    assert rows == [{
        'employee': 'B5678', 'department': '', 'setup_act_hrs': '0.00', 'setup_est_hrs': '0.00',
        'setup_adj_hrs': '0.00', 'setup_pct_eff': '',
        'run_act_hrs': '0.00', 'run_est_hrs': '0.00',
        'run_adj_hrs': '0.00', 'run_pct_eff': '',
    }]
