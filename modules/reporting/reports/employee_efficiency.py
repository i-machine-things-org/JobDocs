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

Job_Operation.Est_Setup_Hrs/Est_Run_Hrs/Est_Run_Per_Part are properties of
the *operation*, not of each Job_Operation_Time row -- an employee who
worked the same operation across several days has multiple
Job_Operation_Time rows for it, so summing the estimate naively would
multiply-count it. Both queries group by (Employee, Job_Operation) first,
via a CTE (op_detail for Detail, op_rollup for Summary), so MAX(Est_*)
picks up that one fixed per-operation value exactly once no matter how many
time entries it has.

"Adj Hrs" / "% Eff" -- the real JobBOSS report's own headline numbers -- are
now computed from the actual documented JobBOSS formula (ECI knowledge base
article "JobBOSS - Employee Efficiency Report", #000012591), not another
reverse-engineered guess:

    Adj Hrs = Act_Run_Qty * Est_Run_Per_Part
    % Eff = Adj Hrs / Act_Run_Hrs * 100

Confirmed with the article's own worked example: Make Qty 100 at 30
parts/hr -> Est_Run_Per_Part = (100/30)/100 = 0.0333 hrs/part; a time entry
of 2 Act Hrs with Run Qty 25 gives Adj Hrs = 25 * 0.0333 = 0.83, % Eff =
0.83/2 = 41.5%.

Two things this corrects from three earlier (wrong) attempts, all now
removed -- a naive Est/Act ratio, Job_Operation.Efficiency_Pct (confirmed
static garbage), and an Adj Hrs formula based on
Setup_Pct_Complete/Run_Pct_Complete (conceptually wrong -- those reflect
whether the operation is closed out as of *today*, not historical progress,
and collapsed to near-zero for anyone with real hours still logged against
open work):

  1. **Setup is excluded from the efficiency calculation entirely** -- per
     the KB article ("Employee Efficiency does not consider the Setup
     Estimate Time -- subtract the setup time for these calculations").
     Setup Act/Est Hrs are still shown (informational, matching the real
     report's own layout), but only Run feeds Adj Hrs / % Eff.
  2. **Act_Run_Hrs (not Act_Run_Labor_Hrs) is correct** -- the KB article
     notes "The report uses the Machine Hours, not Labor Hours"; this
     schema has both Act_Run_Hrs and a separate Act_Run_Labor_Hrs on
     Job_Operation_Time, and this module has used Act_Run_Hrs throughout.

ISNULL-guards the Adj Hrs computation (Act_Run_Qty * Est_Run_Per_Part) so
one operation with a NULL Est_Run_Per_Part (e.g. a setup-only time entry
with no run component at all) contributes 0, not NULL, to an employee's
SUM -- matching the KB article's "operations without Adj E Hrs are not
included" without one unscoreable operation nulling out every other
operation's real contribution.

**Bad-data guard**: one real operation found live (Job 29718, CNC HMC OP6)
has Act_Run_Qty = 5,629 against Est_Required_Qty = 1 -- the job needed one
part, 5,629 are logged as run, in 10 total hours. Confirmed via the real
JobBOSS report that this does NOT count toward that employee's %Eff (their
real number is sane; ours wasn't, until this guard), but there's no boolean
"exclude this" column anywhere on Job_Operation -- checked every one of its
~100 columns directly. _QTY_SANITY_MULTIPLIER below is a pragmatic
stand-in, not JobBOSS's real exclusion logic: an operation's Run_Qty is
excluded from Adj Hrs / % Eff (not from the informational Hours columns)
when it's more than that many times Est_Required_Qty.

**Two rules confirmed from JobBOSS's own report source**, not inferred --
LR_EmployeeEfficiency_Rpt.htm (the VBScript that builds this report's
actual SQL query, found on the JobBOSS server's Reporting share, copied
locally and read there -- not accessed live on the server):
  - `Job_Operation_Time.Rework_Time = 0` is filtered on every query. Rework
    time entries never counted toward Act hours or Adj Hrs here before --
    a real gap, now fixed, independent of the qty-sanity guard above.
  - If an employee's summed Run Act Hrs for an operation is 0, JobBOSS
    forces the reported quantity to 0 too, regardless of what
    Act_Run_Qty actually summed to (`IIF(ARHSum=0, 0, ARQSum)` in the
    source). Applied here as part of computing Run_Qty itself, before the
    qty-sanity guard and before Adj Hrs.
The actual Adj E Hrs / % Eff Crystal Reports formula itself is still not
recovered -- the .rpt file's formula definitions are compiled to a
proprietary bytecode (confirmed via OLE-stream extraction: near-uniform
byte-value distribution across the Contents stream, no plain text, no
standard compression), not stored as readable text. Reading that back out
needs Crystal Reports itself, not available here.

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
view. (The KB article notes Work Center Type doesn't affect the report's
own calculations -- this exclusion is this module's own choice, to keep
non-production time out of an employee's hours at all, independent of how
JobBOSS's canned report happens to treat it.)
"""

from __future__ import annotations

from typing import Any, Dict, List

from experimental.db_integration import connect, employee_filter_clause
from modules.reporting.reports.base import ReportDefinition

# See the module docstring's "Bad-data guard" section -- not a JobBOSS-
# confirmed rule, a pragmatic stand-in chosen to favor robustness over
# precision given one confirmed real example (5,629x) and no way to find
# JobBOSS's own exclusion logic from here.
_QTY_SANITY_MULTIPLIER = 10

# op_detail groups by (Employee, Job, Work_Center, Operation_Service) first
# so Run_Qty's ARHSum-zero guard (next line) and the qty-sanity guard are
# each computed exactly once per operation, not repeated across the SELECT
# list -- SQL Server can't reference a sibling SELECT-list alias, so without
# this CTE the same CASE expression would need writing out three times.
_EMPLOYEE_EFFICIENCY_DETAIL_QUERY = """
WITH op_detail AS (
    SELECT jot.Employee, jo.Job, jo.Work_Center, jo.Operation_Service,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
           CASE WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty,
           MAX(jo.Est_Required_Qty) AS Est_Required_Qty, MAX(jo.Est_Run_Per_Part) AS Est_Run_Per_Part
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect') AND {employee_clause}
    GROUP BY jot.Employee, jo.Job, jo.Work_Center, jo.Operation_Service
)
SELECT op.Employee, e.First_Name, e.Last_Name, op.Job, op.Work_Center, op.Operation_Service,
       op.Setup_Act_Hrs, op.Setup_Est_Hrs, op.Run_Act_Hrs, op.Run_Est_Hrs, op.Run_Qty,
       CASE WHEN op.Est_Required_Qty > 0 AND op.Run_Qty > op.Est_Required_Qty * {qty_multiplier}
            THEN NULL ELSE op.Run_Qty * op.Est_Run_Per_Part
       END AS Adj_Hrs
FROM op_detail op
JOIN Employee e ON e.Employee = op.Employee
WHERE e.Status = 'Active'
ORDER BY e.Last_Name, e.First_Name, op.Job
"""

# op_rollup groups by (Employee, Job_Operation) first, exactly like Detail's
# GROUP BY -- same reason, so Run_Qty's ARHSum-zero guard and Est_Run_Per_Part
# are each applied to this employee's work on this one operation exactly
# once, not once per Job_Operation_Time row. Joins Work_Center here too (not
# just in the outer query) so the Indirect exclusion applies before the
# rollup, not after. op_scored applies the qty-sanity check per operation,
# so a flagged operation's Act Hours AND Adj Hrs both drop out of the % Eff
# ratio together -- Total_Act_Hrs still includes them (informational:
# "hours actually logged" is still true even when the quantity isn't).
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH op_rollup AS (
    SELECT jot.Employee, jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
           CASE WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty,
           MAX(jo.Est_Required_Qty) AS Est_Required_Qty, MAX(jo.Est_Run_Per_Part) AS Est_Run_Per_Part
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect')
    GROUP BY jot.Employee, jot.Job_Operation
),
op_scored AS (
    SELECT Employee, Setup_Act_Hrs, Setup_Est_Hrs, Run_Act_Hrs, Run_Est_Hrs,
           CASE WHEN Est_Required_Qty > 0 AND Run_Qty > Est_Required_Qty * {qty_multiplier}
                THEN 0 ELSE Run_Act_Hrs END AS Scored_Run_Act_Hrs,
           CASE WHEN Est_Required_Qty > 0 AND Run_Qty > Est_Required_Qty * {qty_multiplier}
                THEN 0 ELSE Run_Qty * Est_Run_Per_Part END AS Scored_Adj_Hrs
    FROM op_rollup
)
SELECT op.Employee, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs + op.Run_Act_Hrs) AS Total_Act_Hrs,
       SUM(op.Setup_Est_Hrs + op.Run_Est_Hrs) AS Total_Est_Hrs,
       SUM(op.Scored_Run_Act_Hrs) AS Run_Act_Hrs,
       SUM(op.Scored_Adj_Hrs) AS Adj_Hrs
FROM op_scored op
JOIN Employee e ON e.Employee = op.Employee
WHERE e.Status = 'Active' AND {employee_clause}
GROUP BY op.Employee, e.First_Name, e.Last_Name
ORDER BY e.Last_Name, e.First_Name
"""

DETAIL_COLUMNS = (
    'employee', 'job', 'work_center', 'operation', 'setup_act_hrs',
    'setup_est_hrs', 'run_act_hrs', 'run_est_hrs', 'run_qty', 'adj_hrs', 'pct_eff',
)
DETAIL_HEADERS = [
    'Employee', 'Job', 'Work Center', 'Operation', 'Setup Act Hrs',
    'Setup Est Hrs', 'Run Act Hrs', 'Run Est Hrs', 'Run Qty', 'Adj Hrs', '% Eff',
]
# Total Act/Est Hrs include Setup (informational, "how many hours did they
# log in total"); Run Act Hrs / Adj Hrs / % Eff are shown separately since
# % Eff is Run-only -- lining Total Act Hrs up next to % Eff would imply a
# relationship that isn't there (Setup is excluded from the ratio).
SUMMARY_COLUMNS = ('employee', 'total_act_hrs', 'total_est_hrs', 'run_act_hrs', 'adj_hrs', 'pct_eff')
SUMMARY_HEADERS = ['Employee', 'Total Act Hrs', 'Total Est Hrs', 'Run Act Hrs', 'Adj Hrs', '% Eff']


def _pct_or_blank(numerator: float, denominator: float) -> str:
    """numerator/denominator * 100 as a 1-decimal string, or '' if
    denominator is 0/falsy (nothing actually worked yet -- not 0% efficient,
    just not comparable).
    """
    if not denominator:
        return ''
    return f"{(numerator / denominator) * 100:.1f}"


def _rows_from_detail(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        setup_act = r.get('Setup_Act_Hrs') or 0
        setup_est = r.get('Setup_Est_Hrs') or 0
        run_act = r.get('Run_Act_Hrs') or 0
        run_est = r.get('Run_Est_Hrs') or 0
        qty = r.get('Run_Qty') or 0
        # None (not 0) means either no Run component at all (Est_Run_Per_Part
        # unset) or the qty-sanity guard flagged this operation -- blank, not
        # "0.00"/"0.0", since both mean "not scoreable", not "scored at zero".
        adj = r.get('Adj_Hrs')
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
            'adj_hrs': f"{adj:.2f}" if adj is not None else '',
            'pct_eff': _pct_or_blank(adj, run_act) if adj is not None else '',
        })
    return rows


def _rows_from_summary(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        act = r.get('Total_Act_Hrs') or 0
        est = r.get('Total_Est_Hrs') or 0
        run_act = r.get('Run_Act_Hrs') or 0
        adj = r.get('Adj_Hrs') or 0
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'total_act_hrs': f"{act:.2f}",
            'total_est_hrs': f"{est:.2f}",
            'run_act_hrs': f"{run_act:.2f}",
            'adj_hrs': f"{adj:.2f}",
            'pct_eff': _pct_or_blank(adj, run_act),
        })
    return rows


def _fetch_detail(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    clause, employee_params = employee_filter_clause(filters.get('employees'), column='jot.Employee')
    query = _EMPLOYEE_EFFICIENCY_DETAIL_QUERY.format(employee_clause=clause, qty_multiplier=_QTY_SANITY_MULTIPLIER)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end) + employee_params)
            return _rows_from_detail(cur.fetchall())


def _fetch_summary(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    clause, employee_params = employee_filter_clause(filters.get('employees'), column='op.Employee')
    query = _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY.format(employee_clause=clause, qty_multiplier=_QTY_SANITY_MULTIPLIER)
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
    resize_mode="interactive",
    uses_dates=True,
    dates_required=True,
    uses_employee_filter=True,
)
