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
shown separately for Setup and Run, exactly like the real report's own
layout (two parallel blocks, each with Est/Act/Adj/%Eff), per the real
report's own footer: "Efficiency Calculations use Adj E Hrs / Act Hrs" --
stated once, generically, confirming the same formula applies
independently to each block, not just Run.

**Run** uses the actual documented JobBOSS formula (ECI knowledge base
article "JobBOSS - Employee Efficiency Report", #000012591), not a
reverse-engineered guess:

    Run Adj Hrs = Act_Run_Qty * Est_Run_Per_Part
    Run % Eff = Run Adj Hrs / Act_Run_Hrs * 100

Confirmed with the article's own worked example: Make Qty 100 at 30
parts/hr -> Est_Run_Per_Part = (100/30)/100 = 0.0333 hrs/part; a time entry
of 2 Act Hrs with Run Qty 25 gives Adj Hrs = 25 * 0.0333 = 0.83, % Eff =
0.83/2 = 41.5%.

**Setup** has no quantity to adjust by (it's a one-time "did you do the
setup" cost, not scaled per part), so:

    Setup Adj Hrs = Setup Est Hrs
    Setup % Eff = Setup Adj Hrs / Act_Setup_Hrs * 100

This is the empirically-verified DEFAULT case (not a new guess): a real
single-employee export's individual rows showed Setup Est Hrs == Setup Adj
E Hrs exactly in ~94% of rows. The remaining ~6% diverge for an unknown
reason -- deliberately NOT modeled as Setup_Pct_Complete scaling, which has
the same "reflects today, not history" flaw already proven wrong for Run
(see below). Setup % Eff here is therefore exact ~94% of the time and only
approximately right the rest -- better than showing nothing, not claimed
to be precise.

Per the KB article ("Employee Efficiency does not consider the Setup
Estimate Time -- subtract the setup time for these calculations"), Setup's
% Eff is informational only -- it does not feed any combined/overall score,
and there isn't one; Setup and Run are always two independent numbers, per
the real report's own layout, never blended into one.

One correction from three earlier (wrong) attempts at Run's formula, all
now removed -- a naive Est/Act ratio, Job_Operation.Efficiency_Pct
(confirmed static garbage), and an Adj Hrs formula based on
Setup_Pct_Complete/Run_Pct_Complete (conceptually wrong -- those reflect
whether the operation is closed out as of *today*, not historical progress,
and collapsed to near-zero for anyone with real hours still logged against
open work): **Act_Run_Hrs (not Act_Run_Labor_Hrs) is correct** for Run --
the KB article notes "The report uses the Machine Hours, not Labor Hours";
this schema has both Act_Run_Hrs and a separate Act_Run_Labor_Hrs on
Job_Operation_Time, and this module has used Act_Run_Hrs throughout.

**"Operations without Adj E Hrs are not included" -- the report's own
footnote -- is now precisely confirmed to be real and material, even
though its exact trigger condition is still unknown.** Cross-checked a
real single-employee xlsx export cell-by-cell against its own "Employee
Total" row: summing every individual row's Run Act Hrs gives a bigger
number than the Employee Total's own Run Act Hrs (1218.08 vs 1072.13 for
one real employee) -- the gap (145.95) is exactly the Act Hrs from the rows
whose exported Adj E Hrs cell was blank, confirmed by matching "Adj E Hrs
is present" sum to the Employee Total's Run Act Hrs to the cent. Tried and
disproved: Quantity = 0 -- 18 counter-example rows have Quantity = 0 *and*
a real, present, nonzero Adj E Hrs (e.g. Qty=0, Adj E Hrs=0.135059088351154,
an oddly-precise value that doesn't come from qty * a per-part rate at
all). Whatever JobBOSS actually checks isn't visible from the exported
columns available here, and isn't implemented -- shipping a guessed rule
after disproving the first guess would repeat the exact mistake this
disproof just caught. The gap between this module's Act/Adj Hrs and
JobBOSS's own is real and not fully closed; _QTY_SANITY_MULTIPLIER below
remains the one guard actually shipped, for the one failure mode actually
confirmed (next paragraph).

**Bad-data guard**: one real operation found live (Job 29718, CNC HMC OP6)
has Act_Run_Qty = 5,629 against Est_Required_Qty = 1 -- the job needed one
part, 5,629 are logged as run, in 10 total hours. There's no boolean
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
# ratio together. Setup Act/Est Hrs and Run Est Hrs are never "scored" --
# like Detail, they're plain informational sums, not inputs to % Eff, so a
# flagged operation's hours still show there even though they're excluded
# from Run Act Hrs/Adj Hrs. Setup and Run are kept as separate columns here
# too, never summed into one blended "Total" -- the real report never does
# that either, and blending them would silently combine an excluded
# category (Setup) with the one that actually drives % Eff (Run).
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
    SELECT Employee, Setup_Act_Hrs, Setup_Est_Hrs, Run_Est_Hrs,
           CASE WHEN Est_Required_Qty > 0 AND Run_Qty > Est_Required_Qty * {qty_multiplier}
                THEN 0 ELSE Run_Act_Hrs END AS Scored_Run_Act_Hrs,
           CASE WHEN Est_Required_Qty > 0 AND Run_Qty > Est_Required_Qty * {qty_multiplier}
                THEN 0 ELSE Run_Qty * Est_Run_Per_Part END AS Scored_Adj_Hrs
    FROM op_rollup
)
SELECT op.Employee, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs) AS Setup_Act_Hrs,
       SUM(op.Setup_Est_Hrs) AS Setup_Est_Hrs,
       SUM(op.Scored_Run_Act_Hrs) AS Run_Act_Hrs,
       SUM(op.Run_Est_Hrs) AS Run_Est_Hrs,
       SUM(op.Scored_Adj_Hrs) AS Adj_Hrs
FROM op_scored op
JOIN Employee e ON e.Employee = op.Employee
WHERE e.Status = 'Active' AND {employee_clause}
GROUP BY op.Employee, e.First_Name, e.Last_Name
ORDER BY e.Last_Name, e.First_Name
"""

DETAIL_COLUMNS = (
    'employee', 'job', 'work_center', 'operation',
    'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_qty', 'run_adj_hrs', 'run_pct_eff',
)
DETAIL_HEADERS = [
    'Employee', 'Job', 'Work Center', 'Operation',
    'Setup Act Hrs', 'Setup Est Hrs', 'Setup Adj Hrs', 'Setup % Eff',
    'Run Act Hrs', 'Run Est Hrs', 'Run Qty', 'Run Adj Hrs', 'Run % Eff',
]
# Setup and Run are always separate, parallel blocks, never summed into one
# blended "Total" -- matches Detail, and matches the real report, which
# never combines them either (Setup isn't part of any combined score).
SUMMARY_COLUMNS = (
    'employee', 'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_adj_hrs', 'run_pct_eff',
)
SUMMARY_HEADERS = [
    'Employee', 'Setup Act Hrs', 'Setup Est Hrs', 'Setup Adj Hrs', 'Setup % Eff',
    'Run Act Hrs', 'Run Est Hrs', 'Run Adj Hrs', 'Run % Eff',
]


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
        # Setup Adj Hrs = Setup Est Hrs -- see module docstring ("Setup" section)
        # for why, and its ~94%-exact caveat. No qty-sanity guard here -- Setup
        # has no quantity to sanity-check against in the first place.
        setup_adj = setup_est
        # None (not 0) means either no Run component at all (Est_Run_Per_Part
        # unset) or the qty-sanity guard flagged this operation -- blank, not
        # "0.00"/"0.0", since both mean "not scoreable", not "scored at zero".
        run_adj = r.get('Adj_Hrs')
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'job': r.get('Job') or '',
            'work_center': r.get('Work_Center') or '',
            'operation': r.get('Operation_Service') or '',
            'setup_act_hrs': f"{setup_act:.2f}",
            'setup_est_hrs': f"{setup_est:.2f}",
            'setup_adj_hrs': f"{setup_adj:.2f}",
            'setup_pct_eff': _pct_or_blank(setup_adj, setup_act),
            'run_act_hrs': f"{run_act:.2f}",
            'run_est_hrs': f"{run_est:.2f}",
            'run_qty': str(qty),
            'run_adj_hrs': f"{run_adj:.2f}" if run_adj is not None else '',
            'run_pct_eff': _pct_or_blank(run_adj, run_act) if run_adj is not None else '',
        })
    return rows


def _rows_from_summary(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        setup_act = r.get('Setup_Act_Hrs') or 0
        setup_est = r.get('Setup_Est_Hrs') or 0
        run_act = r.get('Run_Act_Hrs') or 0
        run_est = r.get('Run_Est_Hrs') or 0
        run_adj = r.get('Adj_Hrs') or 0
        # Setup Adj Hrs = Setup Est Hrs -- see _rows_from_detail/module docstring.
        setup_adj = setup_est
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'setup_act_hrs': f"{setup_act:.2f}",
            'setup_est_hrs': f"{setup_est:.2f}",
            'setup_adj_hrs': f"{setup_adj:.2f}",
            'setup_pct_eff': _pct_or_blank(setup_adj, setup_act),
            'run_act_hrs': f"{run_act:.2f}",
            'run_est_hrs': f"{run_est:.2f}",
            'run_adj_hrs': f"{run_adj:.2f}",
            'run_pct_eff': _pct_or_blank(run_adj, run_act),
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
