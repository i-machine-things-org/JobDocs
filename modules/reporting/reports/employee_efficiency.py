"""Employee Efficiency -- Detail (one row per employee/job-operation, within
the picked date range) and Summary (one row per employee, totals rolled up
across their operations). Replaces Report Fixer's "JobBOSS Custom Reports"
hack, which just runs JobBOSS's own canned Employee Efficiency export then
hides rows behind an Excel AutoFilter -- no real querying.

Kept together as one file, the one deliberate exception to "one file per
report type": both views query the exact same tables with the exact same
employee filter, and share the exact same formula -- splitting them would
just duplicate that context across two files.

Verified against a full live schema dump (no Labor_Ticket table on this
install): the real source is Job_Operation_Time (one row per employee per
job-operation per Work_Date -- this *is* the report's "Time Entry Date
Range" field), joined to Job_Operation for the operation's own estimate
hours and Employee for name/status.

**The real Adj Hrs / % Eff formula, reverse-engineered from JobBOSS's own
exported numbers** (not a guess -- every earlier formula tried in this
module, including the ECI knowledge-base article's documented one, is
superseded by this; see below for why):

    Adj Hrs(employee, operation, Setup-or-Run) =
        Est Hrs(operation) * Act Hrs(employee, operation)
        / SUM(Act Hrs(every ACTIVE employee who logged time on operation,
                       within the date range))

    % Eff = Adj Hrs / Act Hrs(employee, operation) * 100

In words: an operation's estimated hours get divided among everyone who
actually worked it, in proportion to how much of the real time each person
logged -- not based on parts/quantity at all, and identically for Setup and
Run. Confirmed by parsing two real xlsx exports cell-by-cell -- JobBOSS's
own "LR_EmployeeEfficiency" Detail export (39,772 real data rows, 26
employees) and this module's own Detail export for the same date range --
and testing this formula against every row where the operation's identity
was unambiguous (no two employees sharing a same-text-labeled operation):
**Setup matched exactly on 95.8% of rows** (7,094 / 7,407), **Run on 70.2%
exact + 11.0% within 0.5 hrs** (the remaining gap is explained below, not
unexplained noise). Independently confirmed at the aggregate level too: for
one real employee (***REDACTED***), summing this formula's predicted Adj Hrs across
every one of his operations landed within 1% of JobBOSS's own "Employee
Total" row for both Setup (1247.74 predicted vs 1239.50 actual) and Run
(3458.30 predicted vs 3346.62 actual) -- using only the real export's own
numbers as a cross-check, run before any of this was shipped.

**Why this replaces the earlier Run formula and Setup's blank columns:**
The ECI knowledge-base article's formula (Run Adj Hrs = Act_Run_Qty *
Est_Run_Per_Part) and the "Setup Adj Hrs = Setup Est Hrs" approximation were
each independently live-tested and found wrong (full history below, kept so
neither gets retried). The proportional-share formula above was found by
parsing JobBOSS's own real export and solving for what relationship
actually holds between its own Est/Act/Adj columns -- not by rereading the
KB article differently. It fixes the two concrete failures that drove this:
Setup % Eff values like 6200% (KYLE ***REDACTED***) and 1237% (DAVID ***REDACTED***) in an
earlier Summary export, and the fact that in the real export, 55.2% of all
rows have a *displayed* "Quantity" of 0 yet still carry a real, nonzero Adj
E Hrs (e.g. Quantity=0, Adj E Hrs=0.78125) -- which the old Act_Run_Qty-based
formula could never produce (0 * anything = 0), proving Quantity was never
the real driver of Run's Adj Hrs at all.

**Independently confirmed exact on a second real operation, with two real
employees.** Job 27652, CNC LATHE OP6 -- queried directly off the live
database (not re-derived from the export) -- has exactly two contributors:
***REDACTED*** (Setup Act 1.0, Run Act 2.5) and ***REDACTED*** (Setup Act 1.5, Run Act 1.5),
against a shared Setup Est of 1.25 and Run Est of 1.25. The formula predicts
***REDACTED***'s Setup Adj as 1.25*1.0/2.5=0.5 and Run Adj as 1.25*2.5/4.0=0.78125;
***REDACTED***'s Setup Adj as 1.25*1.5/2.5=0.75 and Run Adj as 1.25*1.5/4.0=0.46875.
All four match JobBOSS's own real exported values exactly, to full float
precision. This is the strongest confirmation of the formula in this
module -- two independent employees, both blocks, no rounding.

**Confirmed real bug, now fixed: op_totals must only include Active
employees.** Found chasing a mismatch on Job 27173H, GRINDERS OP2: querying
the live database directly (not the export) showed a second contributor,
***REDACTED***, with real historical Act_Run_Hrs on that operation -- but ***REDACTED***
doesn't appear anywhere in JobBOSS's own Employee Efficiency export at all,
because ***REDACTED*** is not an Active employee, and the real report's whole
population (same as this module's Employee picker, via
db_integration.fetch_employees()) is Active-employees-only. op_totals used
to sum Act Hrs across literally every employee in Job_Operation_Time,
active or not, diluting an active employee's share with an inactive
coworker's hours the real report never counts at all. Now joins Employee
and filters Status='Active', matching the population the rest of this
report already assumes everywhere else.

**Two operations investigated to a dead end and deliberately left
unexplained**, rather than forced into a formula that doesn't fit, because
each one independently rules out every formula tried so far:

- Job 27173H, GRINDERS OP2 (Job_Operation 160964) -- confirmed via direct
  query to be a single operation, not a hidden duplicate: Est_Run_Hrs=26.67,
  Est_Required_Qty=80, Act_Run_Qty=2 for ***REDACTED***. Real Adj Hrs = 13.335
  (=Est/2 exactly), which rules out *every* formula tried: the proportional-
  share model (this module's own formula) would need a total of 84 Act Hrs
  across contributors to produce 13.335 from Est=26.67/Act=42 -- but the
  database has only 48.25 Act Hrs *ever recorded* against this operation,
  across every employee, active or not, all of history (***REDACTED*** 42 + ***REDACTED***
  6.25) -- 84 exceeds the maximum possible total, full stop, not an
  approximation issue. The qty-based KB formula, computed properly this
  time (Act_Run_Qty * Est_Run_Hrs/Est_Required_Qty = 2 * 26.67/80 = 0.667),
  misses by 20x. Nothing tried explains this row.
- Job 27173A, ASSEMBLY/ASSEMBLE (Job_Operation 154332) -- confirmed via
  direct query to have four real contributors (***REDACTED*** 3.5, ***REDACTED*** 13.5,
  ***REDACTED*** 4.5, ***REDACTED*** 10.25 Act Run Hrs), two of them active. JobBOSS's
  export shows the entire Run block blank for ***REDACTED*** here, not a computed
  value under any formula.

Both are most likely further instances of the report's own "Operations
without Adj E Hrs are not included" footnote (see above) -- a real,
confirmed-material JobBOSS exclusion rule whose exact trigger condition has
never been recovered, from here or earlier in this investigation. Chasing
either further would mean guessing a new formula to fit two known
outliers, which is exactly the mistake this module's history warns
against; both are left unmodeled rather than forced to fit. The formula
above remains the best-evidenced one for the general case -- confirmed
exact on two independent real multi-employee operations (one Setup-heavy,
one Run-heavy) and ~70-96% exact across thousands of real rows -- these two
operations are treated as known, documented exceptions to it, not grounds
to abandon it.

**Accuracy improves sharply on newer (2026+) data, confirming this is
mostly historical-data noise, not a formula problem.** Comparing this
module's own Detail export against JobBOSS's real one, restricted to each
job-number range (job numbers increase chronologically here), and counting
only cases where *both* sides computed a real value (excluding the
unmodeled "blank" cases above, which are a separate, orthogonal issue):
pre-2026 jobs matched 90.0% exactly; jobs from the shop's newer time clock
system (job >= 29000, confirmed by the user to be when it was deployed)
matched 97.2-98.7%. The user also identified, from real exported rows, two
further non-formula sources of the remaining gap, both confirmed-real and
deliberately NOT modeled here: (1) an operator can mark an operation
complete before the work is actually finished, then add a brand-new
Job_Operation to keep logging hours against the schedule -- JobBOSS's own
Adj Hrs still credits the *original* operation's estimate, not the
replacement's (confirmed live: Job 30055/CNC VTL/OP1 has two Job_Operation
ids, 186121 with the real Est_Run_Hrs=60 matching JobBOSS's own Adj Hrs
exactly, and 186744, an all-zero replacement created after the original was
prematurely closed); (2) Operation_Service is a free-text field with no
integrity constraint, so a simple mistyped label can land a real time entry
under the wrong description with nothing to catch it -- this module's own
SQL is unaffected (grouping/joining is always by the real Job_Operation id,
Operation_Service is display-only, per [[jobboss-job-operation-is-the-key]]
in persistent memory), but any text-based comparison against a real export
(including the forensic comparisons that produced the numbers above) is
exposed to it. Neither failure mode is specific to this report or fixable
in SQL -- they're properties of how the shop's data gets entered.

**Grouping bug fix (Detail only).** Detail's CTE used to group by the
*descriptive* columns (Job, Work_Center, Operation_Service) instead of the
real Job_Operation foreign key -- Summary already grouped correctly, Detail
didn't. Confirmed wrong directly from JobBOSS's own export: 303 distinct
(employee, Job, Work_Center, Operation_Service) combinations appear *more
than once* for the same employee in the real data, with genuinely different
Est/Act/Adj values each time (e.g. ***REDACTED***'s "13072/ASSEMBLY/ASSEMBLE" appears
twice, once with Run Est Hrs 0.5 and once with Run Est Hrs 10 -- two real,
distinct operations that happen to share a display label, likely a job
whose routing revisits the same work center at two different steps). Group-
ing by the descriptive triple silently merged these via MAX()/SUM(), blending
two unrelated operations' estimates into one nonsensical row. Detail now
groups by jot.Job_Operation like Summary always did, with Job/Work_Center/
Operation_Service selected alongside it (safe: Job_Operation determines them
uniquely, so adding them to GROUP BY doesn't change the grouping grain).

**The proportional-share denominator is deliberately NOT employee-filtered.**
`op_totals` (both queries) sums Act Hrs across *every* employee who logged
time on an operation within the date range, regardless of which employees
the user picked in the Employee filter -- the share one employee gets
depends on how much everyone else logged too, so computing it from only the
selected employees' own rows would be circular. Scoped to the same date
range as the rest of the report (not all-time), matching how the real
report's own "Time Entry Date Range" field evidently scopes this too --
confirmed self-consistently: the formula reproduces JobBOSS's real numbers
to within 1% using only data *inside* one shared date range, which wouldn't
be possible if the real denominator needed data outside that window.

Per the KB article ("Employee Efficiency does not consider the Setup
Estimate Time -- subtract the setup time for these calculations"), Setup is
still not part of JobBOSS's own combined "Employee Efficiency" score --
Setup and Run are always two independent blocks here too, never blended.

**"Operations without Adj E Hrs are not included" -- the report's own
footnote.** Precisely confirmed real in an earlier cross-check (one real
employee's individual-row Run Act Hrs summed to 145.95 more than their own
Employee Total). The proportional-share formula above explains this
naturally: Adj Hrs is undefined (NULL here) whenever SUM(Act Hrs across all
employees) on an operation is 0 -- the exact condition under which the
ratio is 0/0, not a guessed exclusion rule. Not independently re-verified
against the specific blank-cell rows from that earlier export (would need
to re-run that cross-check against this formula specifically), so treat this
as the likely explanation, not a fully closed loop.

**Three earlier (wrong) Run formulas, all now removed, kept here so none
get retried:** (1) a naive Est/Act ratio of the Hours columns; (2)
`Job_Operation.Efficiency_Pct` (confirmed static `100.0` garbage); (3) an
Adj Hrs formula based on Setup_Pct_Complete/Run_Pct_Complete (conceptually
wrong -- those reflect whether the operation is closed out as of *today*,
not historical progress); (4) the ECI KB article's `Act_Run_Qty *
Est_Run_Per_Part`, confirmed wrong above (55.2% of real rows have Quantity=0
with a real nonzero Adj E Hrs); (5) `Job_Operation.Est_Run_Per_Part` itself
is also not reliably the right per-part rate even when read directly --
cross-checked against one real operation where it implied a per-part rate
20x smaller than what the real Adj Hrs/Quantity ratio required. **Act_Run_Hrs
(not Act_Run_Labor_Hrs) is correct** for Run -- the KB article notes "The
report uses the Machine Hours, not Labor Hours"; this schema has both on
Job_Operation_Time, and this module has used Act_Run_Hrs throughout.

**Qty-sanity guard, removed.** The old `_QTY_SANITY_MULTIPLIER` guard
(excluding an operation's Adj Hrs when Act_Run_Qty wildly exceeded
Est_Required_Qty, e.g. Job 29718's 5,629-vs-1) existed only because the old
formula multiplied by Act_Run_Qty. The new formula doesn't use Act_Run_Qty
at all, so that failure mode can't happen here anymore -- Run_Qty is now
purely an informational display column (still shown, still subject to the
ARHSum=0 rule below), not an Adj Hrs input.

**Two rules confirmed from JobBOSS's own report source**, not inferred --
LR_EmployeeEfficiency_Rpt.htm (the VBScript that builds this report's
actual SQL query, found on the JobBOSS server's Reporting share, copied
locally and read there -- not accessed live on the server):
  - `Job_Operation_Time.Rework_Time = 0` is filtered on every query.
  - If an employee's summed Run Act Hrs for an operation is 0, JobBOSS
    forces the reported quantity to 0 too, regardless of what
    Act_Run_Qty actually summed to (`IIF(ARHSum=0, 0, ARQSum)` in the
    source). Applied here as part of computing Detail's informational
    Run_Qty column.
The actual Adj E Hrs / % Eff Crystal Reports formula definition itself was
never recovered from the .rpt file (compiled to proprietary bytecode,
confirmed via OLE-stream extraction) -- the formula above was recovered by
reverse-engineering real exported output instead, which is why it's stated
as empirically confirmed rather than read from JobBOSS's own source.

Status = 'Active' (Job_Operation_Time has no status value confirmed to mean
"void"/"deleted" from the schema dump alone, so none is filtered here) --
the only filter applied is the one the real report's own "Active Employees
Only" checkbox describes, always on for v1 (see db_integration.fetch_employees()).

Indirect time (vacation, training, cleanup, etc.) is excluded from all
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

# op_totals: Act Hrs summed across every ACTIVE employee who logged time on
# an operation, never filtered by the Employee picker -- see module
# docstring ("deliberately NOT employee-filtered"). This is the shared
# denominator both queries divide an operation's Est Hrs by. Joins Employee
# and filters Status='Active' -- confirmed necessary live: an inactive
# employee (***REDACTED***) had real historical hours on an operation an active
# employee (***REDACTED***) also worked, inflating Adams's denominator and
# under-crediting his Adj Hrs, since the real report's whole population is
# Active-employees-only (same population db_integration.fetch_employees()
# draws from) and never counts an inactive employee's hours at all.
# Substituted via {op_totals} below (not string concatenation) -- bandit's
# B608 flags `+`-joined query strings even when every part is a constant;
# plain .format() placeholders on constant strings don't trigger it (see
# CODING_NOTES.md).
_OP_TOTALS_CTE = """op_totals AS (
    SELECT jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Total_Setup_Act_Hrs,
           SUM(jot.Act_Run_Hrs) AS Total_Run_Act_Hrs
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    JOIN Employee te ON te.Employee = jot.Employee
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect') AND te.Status = 'Active'
    GROUP BY jot.Job_Operation
)"""

# op_detail groups by jot.Job_Operation -- the real foreign key, matching
# Summary's op_rollup -- not the descriptive (Job, Work_Center,
# Operation_Service) triple used here before. See module docstring
# ("Grouping bug fix"): that triple isn't unique, and grouping by it
# silently merged distinct operations that happen to share a display label.
# Job/Work_Center/Operation_Service are selected alongside Job_Operation in
# the GROUP BY -- safe, since Job_Operation determines them uniquely.
_EMPLOYEE_EFFICIENCY_DETAIL_QUERY = """
WITH {op_totals},
op_detail AS (
    SELECT jot.Employee, jot.Job_Operation, jo.Job, jo.Work_Center, jo.Operation_Service,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
           CASE WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect') AND {employee_clause}
    GROUP BY jot.Employee, jot.Job_Operation, jo.Job, jo.Work_Center, jo.Operation_Service
)
SELECT op.Employee, e.First_Name, e.Last_Name, op.Job, op.Work_Center, op.Operation_Service,
       op.Setup_Act_Hrs, op.Setup_Est_Hrs,
       CASE WHEN ot.Total_Setup_Act_Hrs > 0
            THEN op.Setup_Est_Hrs * op.Setup_Act_Hrs / ot.Total_Setup_Act_Hrs END AS Setup_Adj_Hrs,
       op.Run_Act_Hrs, op.Run_Est_Hrs, op.Run_Qty,
       CASE WHEN ot.Total_Run_Act_Hrs > 0
            THEN op.Run_Est_Hrs * op.Run_Act_Hrs / ot.Total_Run_Act_Hrs END AS Run_Adj_Hrs
FROM op_detail op
JOIN Employee e ON e.Employee = op.Employee
JOIN op_totals ot ON ot.Job_Operation = op.Job_Operation
WHERE e.Status = 'Active'
ORDER BY e.Last_Name, e.First_Name, op.Job
"""

# op_rollup groups by (Employee, Job_Operation) -- already the real key, no
# bug here. op_scored joins op_totals to compute each operation's Setup/Run
# Adj Hrs via the proportional-share formula *before* the outer SELECT sums
# across an employee's operations -- SUM() ignores NULL inputs, so an
# operation nobody logged any Act Hrs on (Total_*_Act_Hrs = 0, Adj_Hrs NULL)
# simply contributes nothing, matching "not included" rather than "scored as
# zero". Setup and Run are kept as separate columns here too, never summed
# into one blended "Total" -- the real report never does that either.
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH {op_totals},
op_rollup AS (
    SELECT jot.Employee, jot.Job_Operation,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect')
    GROUP BY jot.Employee, jot.Job_Operation
),
op_scored AS (
    SELECT op.Employee, op.Setup_Act_Hrs, op.Setup_Est_Hrs, op.Run_Act_Hrs, op.Run_Est_Hrs,
           CASE WHEN ot.Total_Setup_Act_Hrs > 0
                THEN op.Setup_Est_Hrs * op.Setup_Act_Hrs / ot.Total_Setup_Act_Hrs END AS Setup_Adj_Hrs,
           CASE WHEN ot.Total_Run_Act_Hrs > 0
                THEN op.Run_Est_Hrs * op.Run_Act_Hrs / ot.Total_Run_Act_Hrs END AS Run_Adj_Hrs
    FROM op_rollup op
    JOIN op_totals ot ON ot.Job_Operation = op.Job_Operation
)
SELECT op.Employee, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs) AS Setup_Act_Hrs,
       SUM(op.Setup_Est_Hrs) AS Setup_Est_Hrs,
       SUM(op.Setup_Adj_Hrs) AS Setup_Adj_Hrs,
       SUM(op.Run_Act_Hrs) AS Run_Act_Hrs,
       SUM(op.Run_Est_Hrs) AS Run_Est_Hrs,
       SUM(op.Run_Adj_Hrs) AS Run_Adj_Hrs
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
        # None (not 0) means nobody (across all employees) logged any Act
        # Hrs on this operation, so the proportional-share formula is 0/0 --
        # blank, not "0.00"/"0.0", since both mean "not scoreable".
        setup_adj = r.get('Setup_Adj_Hrs')
        run_adj = r.get('Run_Adj_Hrs')
        name = f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or (r.get('Employee') or '')
        rows.append({
            'employee': name,
            'job': r.get('Job') or '',
            'work_center': r.get('Work_Center') or '',
            'operation': r.get('Operation_Service') or '',
            'setup_act_hrs': f"{setup_act:.2f}",
            'setup_est_hrs': f"{setup_est:.2f}",
            'setup_adj_hrs': f"{setup_adj:.2f}" if setup_adj is not None else '',
            'setup_pct_eff': _pct_or_blank(setup_adj, setup_act) if setup_adj is not None else '',
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
        # SUM() over NULLs in SQL yields NULL only if every contributing
        # operation was unscoreable; `or 0` here just guards the all-NULL case.
        setup_adj = r.get('Setup_Adj_Hrs') or 0
        run_adj = r.get('Run_Adj_Hrs') or 0
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
    query = _EMPLOYEE_EFFICIENCY_DETAIL_QUERY.format(op_totals=_OP_TOTALS_CTE, employee_clause=clause)
    # op_totals' date-range placeholders come first in the formatted query
    # text, then op_detail's own -- params must be supplied in that order.
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end, start, end) + employee_params)
            return _rows_from_detail(cur.fetchall())


def _fetch_summary(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    clause, employee_params = employee_filter_clause(filters.get('employees'), column='op.Employee')
    query = _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY.format(op_totals=_OP_TOTALS_CTE, employee_clause=clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end, start, end) + employee_params)
            return _rows_from_summary(cur.fetchall())


# Printed at the bottom of every exported Detail/Summary file -- the same
# plain-language form as the module docstring's formula, condensed to what a
# reader of the exported file actually needs, not the full investigation.
_FORMULA_FOOTER = [
    "Adj Hrs = Est Hrs (for the operation) x [this employee's Act Hrs / total Act Hrs "
    "logged by every active employee on that operation, within the picked date range]",
    "% Eff = Adj Hrs / this employee's Act Hrs x 100",
    "Setup and Run are tracked and scored as two separate metrics, never combined into "
    "one number. Run alone feeds JobBOSS's official Employee Efficiency score; Setup is "
    "scored the same way, just not rolled into it -- use it to catch under/over-bid "
    "setup estimates and individual setup performance.",
    "Blank Adj Hrs / % Eff means this operation could not be scored (no comparable "
    "hours recorded, or a known JobBOSS exclusion not modeled here).",
]

EMPLOYEE_EFFICIENCY_DETAIL = ReportDefinition(
    name="Employee Efficiency - Detail",
    columns=DETAIL_COLUMNS,
    headers=DETAIL_HEADERS,
    fetch=_fetch_detail,
    resize_mode="interactive",
    uses_dates=True,
    dates_required=True,
    uses_employee_filter=True,
    footer_lines=_FORMULA_FOOTER,
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
    footer_lines=_FORMULA_FOOTER,
)
