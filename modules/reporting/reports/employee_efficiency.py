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

Still NOT included: "Adj E Hrs", the JobBOSS-report column feeding its real
"% Eff" (Adj E Hrs / Act Hrs * 100, per that report's own PDF footnote).
Neither Job_Operation nor Job_Operation_Time has any column named
Adj_E_Hrs -- confirmed against the schema dump; the best inferred formula
(Setup Adj Hrs == Est_Setup_Hrs; Run Adj Hrs == Act_Run_Qty *
Est_Run_Per_Part) is still just an inference, not a verified stored value.
See _compute_adj_hrs_and_efficiency() for where that plugs back in once
validated.

Two DIFFERENT %Eff-shaped columns ARE included, deliberately both at once
and deliberately unlabeled as "the real one" -- this is a live A/B
comparison, not a final decision:
  - 'Est/Act %' -- (Setup Est Hrs + Run Est Hrs) / (Setup Act Hrs + Run Act
    Hrs) * 100. Zero inference: it's a ratio of the two Hours columns
    already shown. Will NOT match the real report wherever actual qty run
    differs from the job's original estimated qty (that's exactly the gap
    "Adjusted" closes and this doesn't).
  - 'JobBOSS Eff%' -- Job_Operation.Efficiency_Pct, a real stored column
    missed in the original design. Unverified whether it means the same
    thing as the canned report's %Eff (it's scoped to the whole operation
    across every employee/day, not this one employee's slice -- same
    caveat as Est_Setup_Hrs/Est_Run_Hrs already shown) or is actually a
    scheduling-input field (see also Job_Operation.SB_Efficiency, not used
    here). Detail shows the operation's own value directly; Summary shows
    a plain (unweighted) average across the employee's distinct operations
    -- also unverified as the right rollup.
Compare both against a real employee's known LR_EmployeeEfficiency.xlsx
number before trusting either for real use.

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
       SUM(jot.Act_Run_Qty) AS Run_Qty, MAX(jo.Efficiency_Pct) AS Jb_Efficiency_Pct
FROM Job_Operation_Time jot
JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
JOIN Employee e ON e.Employee = jot.Employee
WHERE jot.Work_Date BETWEEN %s AND %s AND e.Status = 'Active' AND {employee_clause}
GROUP BY jot.Employee, e.First_Name, e.Last_Name, jo.Job, jo.Work_Center, jo.Operation_Service
ORDER BY e.Last_Name, e.First_Name, jo.Job
"""

# op_rollup groups by (Employee, Job_Operation) first, exactly like Detail's
# GROUP BY -- same reason, so each operation's estimate (and Efficiency_Pct,
# also a per-operation value) is only counted once before rolling the
# per-operation rows up to one row per employee. AVG(), not SUM(), for
# Jb_Efficiency_Pct in the outer query -- it's a percentage, rolling multiple
# operations' percentages up by summing them would be meaningless.
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH op_rollup AS (
    SELECT jot.Employee, jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
           MAX(jo.Efficiency_Pct) AS Jb_Efficiency_Pct
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    WHERE jot.Work_Date BETWEEN %s AND %s
    GROUP BY jot.Employee, jot.Job_Operation
)
SELECT op.Employee, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs + op.Run_Act_Hrs) AS Total_Act_Hrs,
       SUM(op.Setup_Est_Hrs + op.Run_Est_Hrs) AS Total_Est_Hrs,
       AVG(op.Jb_Efficiency_Pct) AS Avg_Jb_Efficiency_Pct
FROM op_rollup op
JOIN Employee e ON e.Employee = op.Employee
WHERE e.Status = 'Active' AND {employee_clause}
GROUP BY op.Employee, e.First_Name, e.Last_Name
ORDER BY e.Last_Name, e.First_Name
"""

DETAIL_COLUMNS = (
    'employee', 'job', 'work_center', 'operation', 'setup_act_hrs',
    'setup_est_hrs', 'run_act_hrs', 'run_est_hrs', 'run_qty',
    'est_act_pct', 'jb_efficiency_pct',
)
DETAIL_HEADERS = [
    'Employee', 'Job', 'Work Center', 'Operation', 'Setup Act Hrs',
    'Setup Est Hrs', 'Run Act Hrs', 'Run Est Hrs', 'Run Qty',
    'Est/Act %', 'JobBOSS Eff%',
]
SUMMARY_COLUMNS = ('employee', 'total_act_hrs', 'total_est_hrs', 'est_act_pct', 'jb_efficiency_pct')
SUMMARY_HEADERS = ['Employee', 'Total Act Hrs', 'Total Est Hrs', 'Est/Act %', 'JobBOSS Eff%']


def _pct_or_blank(numerator: float, denominator: float) -> str:
    """numerator/denominator * 100 as a 1-decimal string, or '' if
    denominator is 0/falsy (nothing actually worked yet -- not 0% efficient,
    just not comparable).
    """
    if not denominator:
        return ''
    return f"{(numerator / denominator) * 100:.1f}"


def _jb_pct_or_blank(value: Optional[float]) -> str:
    """Job_Operation.Efficiency_Pct (or its AVG) is nullable -- blank, not
    '0.0', when JobBOSS itself never set/computed it for this operation.
    """
    return f"{value:.1f}" if value is not None else ''


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
            'est_act_pct': _pct_or_blank(setup_est + run_est, setup_act + run_act),
            'jb_efficiency_pct': _jb_pct_or_blank(r.get('Jb_Efficiency_Pct')),
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
            'est_act_pct': _pct_or_blank(est, act),
            'jb_efficiency_pct': _jb_pct_or_blank(r.get('Avg_Jb_Efficiency_Pct')),
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
