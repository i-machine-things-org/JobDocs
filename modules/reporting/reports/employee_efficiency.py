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

NOT included: "Adj Hrs" / "% Eff", the real JobBOSS report's own headline
numbers. Three attempts tried and dropped, in order -- don't repeat any of
them without actual DB row access to verify against directly, not another
exported-report inference:
  1. A naive Est/Act ratio of the Hours columns already shown. Rejected:
     swings wildly whenever a job's actual run quantity differs from its
     original estimated quantity (a real employee's full-history ratio
     this way was 62.0%, vs. their real report's 96.4% %Eff).
  2. Job_Operation.Efficiency_Pct, a real stored column. Rejected: live-
     tested as a flat 100.0 for every employee regardless of real
     performance -- a static scheduling default, not a computed value.
  3. Adj Hrs = Est Hrs * Setup_Pct_Complete/Run_Pct_Complete / 100 (both
     real stored columns on Job_Operation). Looked promising in an offline
     cross-check against ~1000 rows of a real exported report (94% exact
     match on Setup, one employee's full-history total within a few points
     of their real %Eff) -- but live-tested a day later against the SAME
     historical date range and came back near-zero for most employees
     (people with 1000+ real hours showing 0.0-5% "efficient"). Root cause:
     Setup_Pct_Complete/Run_Pct_Complete are per-OPERATION fields reflecting
     whether the *operation itself* has since been fully closed out, not
     how much of an employee's historically-logged time represented real
     progress -- querying them today only credits operations that happen to
     be 100% complete as of today, zeroing out any employee with
     substantial real hours logged against work that's still open (i.e.
     most people, most of the time). Not a precision problem -- the field
     doesn't mean what the formula needed it to mean for a retrospective,
     date-range report.

Status = 'Active' (Job_Operation_Time has no status value confirmed to mean
"void"/"deleted" from the schema dump alone, so none is filtered here) --
the only filter applied is the one the real report's own "Active Employees
Only" checkbox describes, always on for v1 (see db_integration.fetch_employees()).

Indirect time (vacation, training, cleanup, etc.) is excluded from both
queries via Work_Center.Type <> 'Indirect' -- confirmed directly from this
shop's own Work Center setup screen: Work_Center has a real Type column
(Direct/Indirect), and it's the *work center* that's marked Indirect, not
the job. Joins the Work_Center table (Job_Operation stores the work center
code but not its Type) for this. Always on, not a checkbox -- indirect time
counting toward an employee's hours is a correctness bug, not an optional
view. This filter (unlike the three above) is unaffected by the Adj Hrs
reversion -- it's independently verified and stays.
"""

from __future__ import annotations

from typing import Any, Dict, List

from experimental.db_integration import connect, employee_filter_clause
from modules.reporting.reports.base import ReportDefinition

_EMPLOYEE_EFFICIENCY_DETAIL_QUERY = """
SELECT jot.Employee, e.First_Name, e.Last_Name, jo.Job, jo.Work_Center, jo.Operation_Service,
       SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
       SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
       SUM(jot.Act_Run_Qty) AS Run_Qty
FROM Job_Operation_Time jot
JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
JOIN Employee e ON e.Employee = jot.Employee
WHERE jot.Work_Date BETWEEN %s AND %s AND e.Status = 'Active'
      AND (wc.Type IS NULL OR wc.Type <> 'Indirect') AND {employee_clause}
GROUP BY jot.Employee, e.First_Name, e.Last_Name, jo.Job, jo.Work_Center, jo.Operation_Service
ORDER BY e.Last_Name, e.First_Name, jo.Job
"""

# op_rollup groups by (Employee, Job_Operation) first, exactly like Detail's
# GROUP BY -- same reason, so each operation's estimate is only counted once
# before rolling the per-operation rows up to one row per employee. Joins
# Work_Center here too (not just in the outer query) so the Indirect
# exclusion applies before the rollup, not after -- an indirect work
# center's hours must never enter the SUM.
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH op_rollup AS (
    SELECT jot.Employee, jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect')
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


def _rows_from_detail(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        setup_act = r.get('Setup_Act_Hrs') or 0
        setup_est = r.get('Setup_Est_Hrs') or 0
        run_act = r.get('Run_Act_Hrs') or 0
        run_est = r.get('Run_Est_Hrs') or 0
        qty = r.get('Run_Qty') or 0
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
