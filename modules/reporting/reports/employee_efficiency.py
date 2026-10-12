"""Employee Efficiency -- Detail (one row per employee/job/operation, within
the picked date range) and Summary (one row per employee, totals rolled up
across their operations). Replaces Report Fixer's "JobBOSS Custom Reports"
hack, which just runs JobBOSS's own canned Employee Efficiency export then
hides rows behind an Excel AutoFilter -- no real querying.

Kept together as one file, the one deliberate exception to "one file per
report type": both views query the exact same tables with the exact same
employee filter, and share the exact same reasoning for what's deliberately
left out (see below) -- splitting them would just duplicate that context
across two files.

Verified against a full live schema dump (no Labor_Ticket table on this
install): the real source is Job_Operation_Time (one row per employee per
job-operation per Work_Date -- this *is* the report's "Time Entry Date
Range" field), joined to Job_Operation for the operation's own estimate
hours and Employee for name/status.

Job_Operation.Est_Setup_Hrs/Est_Run_Hrs are properties of the *operation*,
not of each Job_Operation_Time row -- an employee who worked the same
operation across several days has multiple Job_Operation_Time rows for it,
so summing the estimate naively would multiply-count it. Both queries group
by (Employee, Job_Operation) first -- directly via GROUP BY for Detail, via
the op_rollup CTE for Summary -- so MAX(Est_*_Hrs) picks up that one fixed
per-operation estimate exactly once no matter how many time entries it has.

Deliberately NOT included: "Adj E Hrs" / "% Eff", the two columns the real
JobBOSS report leads with. Neither Job_Operation nor Job_Operation_Time has
any column named Adj_E_Hrs -- confirmed against the schema dump. The best
inferred formula (cross-checked against a real exported report: Setup Adj
Hrs == Est_Setup_Hrs; Run Adj Hrs == Act_Run_Qty * Est_Run_Per_Part; % Eff =
Adj E Hrs / Act Hrs * 100, per the export's own PDF footnote) is still just
an inference, not a verified stored value or confirmed JobBOSS calculation
-- too uncertain to show as an employee's "Efficiency %". Per explicit
decision, v1 ships only the directly-sourced Hours/Qty columns below; see
_compute_adj_hrs_and_efficiency() for where that calculation plugs back in
once it's been validated against a live query.

Status = 'Active' (Job_Operation_Time has no status value confirmed to mean
"void"/"deleted" from the schema dump alone, so none is filtered here) --
the only filter applied is the one the real report's own "Active Employees
Only" checkbox describes, always on for v1 (see db_integration.fetch_employees()).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from experimental.db_integration import connect, employee_filter_clause
from modules.reporting.reports.base import ReportDefinition

_EMPLOYEE_EFFICIENCY_DETAIL_QUERY = """
SELECT jot.Employee, e.First_Name, e.Last_Name, jo.Job, jo.Work_Center, jo.Operation_Service,
       SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
       SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
       SUM(jot.Act_Run_Qty) AS Run_Qty
FROM Job_Operation_Time jot
JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
JOIN Employee e ON e.Employee = jot.Employee
WHERE jot.Work_Date BETWEEN %s AND %s AND e.Status = 'Active' AND {employee_clause}
GROUP BY jot.Employee, e.First_Name, e.Last_Name, jo.Job, jo.Work_Center, jo.Operation_Service
ORDER BY e.Last_Name, e.First_Name, jo.Job
"""

# op_rollup groups by (Employee, Job_Operation) first, exactly like Detail's
# GROUP BY -- same reason, so each operation's estimate is only counted once
# before rolling the per-operation rows up to one row per employee.
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH op_rollup AS (
    SELECT jot.Employee, jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    WHERE jot.Work_Date BETWEEN %s AND %s
    GROUP BY jot.Employee, jot.Job_Operation
)
SELECT op.Employee, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs + op.Run_Act_Hrs) AS Total_Act_Hrs,
       SUM(op.Setup_Est_Hrs + op.Run_Est_Hrs) AS Total_Est_Hrs
FROM op_rollup op
JOIN Employee e ON e.Employee = op.Employee
WHERE e.Status = 'Active' AND {employee_clause}
GROUP BY op.Employee, e.First_Name, e.Last_Name
ORDER BY e.Last_Name, e.First_Name
"""

DETAIL_COLUMNS = (
    'employee', 'job', 'work_center', 'operation', 'setup_act_hrs',
    'setup_est_hrs', 'run_act_hrs', 'run_est_hrs', 'run_qty',
)
DETAIL_HEADERS = [
    'Employee', 'Job', 'Work Center', 'Operation', 'Setup Act Hrs',
    'Setup Est Hrs', 'Run Act Hrs', 'Run Est Hrs', 'Run Qty',
]
SUMMARY_COLUMNS = ('employee', 'total_act_hrs', 'total_est_hrs')
SUMMARY_HEADERS = ['Employee', 'Total Act Hrs', 'Total Est Hrs']


def _compute_adj_hrs_and_efficiency(est_hrs: float, act_hrs: float, qty: Optional[int]) -> None:
    """STUB -- not called for its return value by either formatter below.

    Placeholder for JobBOSS's real Employee Efficiency "Adj E Hrs" / "% Eff"
    calculation, intentionally left out of v1 (see this module's docstring
    for the full reasoning). Confirmed from the real LR_EmployeeEfficiency.pdf
    export's own footnote: "Efficiency Calculations use Adj E Hrs / Act
    Hrs"; "Adj E Hrs = Adjusted Estimated Hrs" -- so % Eff = Adj E Hrs / Act
    Hrs * 100. The best-effort formula inferred by cross-checking real
    export rows (Setup Adj Hrs == Est_Setup_Hrs; Run Adj Hrs == qty *
    Est_Run_Per_Part) is NOT a verified stored column or a confirmed JobBOSS
    calculation. Pick this up by implementing the body here (needs
    Est_Run_Per_Part added to both SQL queries' SELECT/GROUP BY) and wiring
    its result into two new columns in both row-formatters below -- once the
    formula has been validated against a live query's numbers, not before.
    """
    return None


def _rows_from_detail(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        setup_act = r.get('Setup_Act_Hrs') or 0
        setup_est = r.get('Setup_Est_Hrs') or 0
        run_act = r.get('Run_Act_Hrs') or 0
        run_est = r.get('Run_Est_Hrs') or 0
        qty = r.get('Run_Qty') or 0
        # Stub call only -- result unused. See _compute_adj_hrs_and_efficiency's docstring.
        _compute_adj_hrs_and_efficiency(setup_est + run_est, setup_act + run_act, qty)
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'job': r.get('Job') or '',
            'work_center': r.get('Work_Center') or '',
            'operation': r.get('Operation_Service') or '',
            'setup_act_hrs': f"{setup_act:.2f}",
            'setup_est_hrs': f"{setup_est:.2f}",
            'run_act_hrs': f"{run_act:.2f}",
            'run_est_hrs': f"{run_est:.2f}",
            'run_qty': str(qty),
        })
    return rows


def _rows_from_summary(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        act = r.get('Total_Act_Hrs') or 0
        est = r.get('Total_Est_Hrs') or 0
        # Stub call only -- result unused. See _compute_adj_hrs_and_efficiency's docstring.
        _compute_adj_hrs_and_efficiency(est, act, None)
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'total_act_hrs': f"{act:.2f}",
            'total_est_hrs': f"{est:.2f}",
        })
    return rows


def _fetch_detail(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    clause, employee_params = employee_filter_clause(filters.get('employees'), column='jot.Employee')
    query = _EMPLOYEE_EFFICIENCY_DETAIL_QUERY.format(employee_clause=clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end) + employee_params)
            return _rows_from_detail(cur.fetchall())


def _fetch_summary(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    clause, employee_params = employee_filter_clause(filters.get('employees'), column='op.Employee')
    query = _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY.format(employee_clause=clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end) + employee_params)
            return _rows_from_summary(cur.fetchall())


EMPLOYEE_EFFICIENCY_DETAIL = ReportDefinition(
    name="Employee Efficiency - Detail",
    columns=DETAIL_COLUMNS,
    headers=DETAIL_HEADERS,
    fetch=_fetch_detail,
    resize_mode="interactive",
    uses_dates=True,
    dates_required=True,
    uses_employee_filter=True,
)
EMPLOYEE_EFFICIENCY_SUMMARY = ReportDefinition(
    name="Employee Efficiency - Summary",
    columns=SUMMARY_COLUMNS,
    headers=SUMMARY_HEADERS,
    fetch=_fetch_summary,
    uses_dates=True,
    dates_required=True,
    uses_employee_filter=True,
)
