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
        / SUM(Act Hrs(every employee who logged time on operation,
                       active or not, within the date range))

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
one real employee (EMP-F), summing this formula's predicted Adj Hrs across
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
Setup % Eff values like 6200% (EMP-I) and 1237% (EMP-H) in an
earlier Summary export, and the fact that in the real export, 55.2% of all
rows have a *displayed* "Quantity" of 0 yet still carry a real, nonzero Adj
E Hrs (e.g. Quantity=0, Adj E Hrs=0.78125) -- which the old Act_Run_Qty-based
formula could never produce (0 * anything = 0), proving Quantity was never
the real driver of Run's Adj Hrs at all.

**Independently confirmed exact on a second real operation, with two real
employees.** Job 27652, CNC LATHE OP6 -- queried directly off the live
database (not re-derived from the export) -- has exactly two contributors:
EMP-F (Setup Act 1.0, Run Act 2.5) and EMP-G (Setup Act 1.5, Run Act 1.5),
against a shared Setup Est of 1.25 and Run Est of 1.25. The formula predicts
EMP-F's Setup Adj as 1.25*1.0/2.5=0.5 and Run Adj as 1.25*2.5/4.0=0.78125;
EMP-G's Setup Adj as 1.25*1.5/2.5=0.75 and Run Adj as 1.25*1.5/4.0=0.46875.
All four match JobBOSS's own real exported values exactly, to full float
precision. This is the strongest confirmation of the formula in this
module -- two independent employees, both blocks, no rounding.

**A later "fix" restricting op_totals to Active employees was itself wrong
-- reverted.** Earlier, chasing a mismatch on Job 27173H, GRINDERS OP2,
this module added `AND te.Status = 'Active'` to op_totals' join on the
theory that since an inactive coworker never appears as a row in JobBOSS's
own export, their hours shouldn't count in the shared denominator either.
That theory was never actually confirmed against real numbers for 27173H
itself (see "Two operations investigated to a dead end" below -- that one
stayed unexplained under every formula tried, active-filtered or not) and
turned out to be backwards. Confirmed wrong with exact arithmetic on Job
26734, WELDING OP2 (Job_Operation 145813, Est_Run_Hrs=40): three real
contributors -- call them EMP-A (Active, 11.0 hrs), EMP-B (Inactive, 5.0
hrs), EMP-C (Inactive, 25.25 hrs). JobBOSS's real Adj Hrs for EMP-A is
10.6666666666667. `40 * 11 / (11 + 5 + 25.25)` = `40 * 11 / 41.25` =
`10.666666666666666` -- matches to full float precision only when the two
Inactive coworkers' hours ARE included. Excluding them (the since-reverted
behavior) computed EMP-A's share as `11/11 = 100%`, giving `Adj = 40.0` --
nearly 4x too high, and this wasn't a one-off: re-checking every one of
EMP-A's real operations after reverting the filter, 516 of 524 (98.5%) now
match JobBOSS's real Adj Hrs exactly (previously ~70%, matching the Run
accuracy figure below, which was measured before this bug was
introduced). The real report's "Active Employees Only" population (which
EMPLOYEES get their own row) and the proportional-share DENOMINATOR (whose
hours get pooled per operation, for employees who DO get a row) are two
independent things -- confirmed the Active-only *population* side is
still correct, separately: this schema has exactly 26 Active employees
and 215 Inactive, no ambiguous third status, and 26 is exactly the number
of employee blocks in JobBOSS's own real export.

**Some operations use a flat equal split (Est Hrs / number of employees)
instead of proportional share -- real, confirmed at scale, but with no
detectable trigger. NOT modeled here, deliberately.** On a minority of
operations JobBOSS ignores how much each person logged and gives every
contributor exactly `Est Hrs / N`. Confirmed on 3,296 distinct real
operations where `Est/N` matches JobBOSS's own exported Adj Hrs to full
float precision and the proportional-share value does not: e.g. Job 28804,
CNC HBM1 OP1.5 (Job_Operation 175276, Est_Run_Hrs=180) has three
contributors with wildly different Act Hrs -- EMP-D (70.25), EMP-E (30.0),
EMP-A (7.0, same individual as the WELDING example above) -- yet all three
get exactly **60** (`180 / 3`). Job 27173H, GRINDERS OP2 (Job_Operation
160964, Est_Run_Hrs=26.67) is the same shape: two contributors (42.0 and
6.25 hrs), both given `13.335` = `26.67 / 2` -- which is why it never fit
the proportional formula (that would have needed a denominator of 84 Act
Hrs against the 48.25 ever recorded).

**An earlier version of this docstring attributed this to jobs predating
the shop's adoption of JobBOSS's Data Collection module. That explanation
is disproved by the full data and must not be reinstated without new
evidence.** Equal-split operations occur in every year on this install,
including the most recent: 42.1% of 2026's multi-contributor operations
and 46.2% of 2025's are equal-split, against 44.3% in 2010 and 51.2% in
2012. It is not an old-data artifact and there is no job-number or date
cutoff to find.

**What the trigger is NOT** (each checked against the full 143,285-row
export, so these are closed questions, not untried ideas):
  - Not any column of `Job_Operation`. Every column was brute-forced for
    separating power; the best single predictor is `Work_Center`, which is
    plainly a proxy (26-85% equal-split depending on the work center) and
    not a rule.
  - Not the quantity, the run method, or the employee count on their own,
    though two *necessary* conditions did fall out and both hold with
    essentially no exceptions: equal split never happens when the
    operation has no reported quantity (1 equal-split vs 6,467
    proportional) and never happens when `Run_Method = 'FixedHrs'` (0 vs
    3,895). Inside the remaining cell (a per-part run method *and* a
    reported quantity) the split is 3,261 equal vs 3,422 proportional --
    a coin flip.
  - Not the time-entry pattern: overlapping work dates, entry counts,
    who closed the operation, overtime factors, `Entry_Type`,
    `Operation_Complete` and `Attended_Pct` were all cross-tabbed; none
    separates the two.
  - Not recoverable even in principle from the data this module can see:
    Job 16865 has two labelled operations, `Job_Operation` 50715
    (equal-split) and 50717 (proportional), that agree on run method
    family, `Est_Required_Qty` (11), `Run_Qty` (11), `Act_Run_Qty` (11),
    employee count and status -- the same attribute values land on both
    sides of the branch.

**Why it is left unimplemented rather than approximated.** Implemented
with the best available trigger (per-part method + reported quantity, the
two necessary conditions above), the equal-split path moves overall cell
agreement by only +0.28 percentage points: it converts ~800 wrong rows to
right while making a comparable number of currently-correct rows wrong,
because the trigger is only ~49% precise. A rule that is right half the
time is worse than a documented omission, and the whole history of this
module is a warning against fitting a formula to a pattern whose cause
isn't understood. The residual is quantified instead (see below), so a
future session with a better signal can pick this up knowing exactly what
it would buy. JobBOSS's own report source confirms the mechanism exists --
its Crystal recordset carries an explicit `EmpCount` field (see the
`LR_EmployeeEfficiency.TTX` note below) -- so the branch is real; only its
condition is missing.

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

These percentages were measured while the Active-only denominator bug
above was still in place -- almost certainly an understatement of this
formula's real accuracy, given the same bug turned a ~70% match rate into
98.5% for one full employee (516/524 operations) once reverted. Not
re-run at full scale after the fix (would need redoing this same
job-number-range comparison from scratch); treat the 90%/97-98.7% figures
as a floor, not the current number.

**Grouping bug fix (Detail only).** Detail's CTE used to group by the
*descriptive* columns (Job, Work_Center, Operation_Service) instead of the
real Job_Operation foreign key -- Summary already grouped correctly, Detail
didn't. Confirmed wrong directly from JobBOSS's own export: 303 distinct
(employee, Job, Work_Center, Operation_Service) combinations appear *more
than once* for the same employee in the real data, with genuinely different
Est/Act/Adj values each time (e.g. EMP-H's "13072/ASSEMBLY/ASSEMBLE" appears
twice, once with Run Est Hrs 0.5 and once with Run Est Hrs 10 -- two real,
distinct operations that happen to share a display label, likely a job
whose routing revisits the same work center at two different steps). Group-
ing by the descriptive triple silently merged these via MAX()/SUM(), blending
two unrelated operations' estimates into one nonsensical row. Detail now
groups by jot.Job_Operation like Summary always did, with Job/Work_Center/
Operation_Service selected alongside it (safe: Job_Operation determines them
uniquely, so adding them to GROUP BY doesn't change the grouping grain).

**Detail includes Indirect operations (Summary does not).** Confirmed
directly against JobBOSS's real export: Indirect time (vacation, training,
cleanup, etc.) appears as real line items in the real Detail report --
each Indirect category (TRAINING, CLEAN-UP, MAINTNANCE, ADMIN, etc.) is
its own Job_Operation per month, with the month itself (e.g. "2026-OCT")
standing in for Job, confirmed live (`Job_Operation.Job = '2026-OCT'` for
these). op_detail's own `jo.Job`/`jo.Work_Center`/`jo.Operation_Service`
columns already carry this through unmodified -- no special-casing needed.
Est_Setup_Hrs/Est_Run_Hrs are a real stored `0.0` for these rows (not
`NULL`), but since op_totals (the denominator) still excludes Indirect --
there's no real "proportional share" concept for non-job time -- the
`LEFT JOIN op_totals` (not a plain `JOIN`, needed so these rows survive at
all) leaves `ot.Total_*_Act_Hrs` `NULL` for them, so Setup_Adj_Hrs/
Run_Adj_Hrs still correctly come out blank, matching the real report's own
blank Adj Hrs/% Eff for these rows. Summary's op_rollup keeps the
exclusion -- it's specifically a Setup/Run job-efficiency rollup, and
including Indirect there would inflate "Act Hrs" with non-job time without
changing Adj Hrs (still NULL/ignored by SUM()), distorting the Act-vs-Adj
relationship Summary exists to show.

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
Employee Total). The proportional-share formula above explains part of
this naturally: Adj Hrs is undefined (NULL here) whenever SUM(Act Hrs
across all employees) on an operation is 0 -- the exact condition under
which the ratio is 0/0, not a guessed exclusion rule. This covers the
shared-denominator case but turned out not to be the whole rule -- see
"When JobBOSS blanks an Adj Hrs cell" immediately below for the complete,
now fully-confirmed condition.

**When JobBOSS blanks an Adj Hrs cell -- the complete rule, not just the
shared-denominator case above.** Adj Hrs is blank whenever EITHER the
shared denominator is 0 (the 0/0 case just described) OR this employee's
own Act Hrs for that block is 0 -- but Setup and Run are NOT symmetric
about the second condition. A Setup block still gets a real, printed Adj
Hrs (including a real `0`) whenever this employee logged real Setup hours,
even if `Est_Setup_Hrs = 0` -- confirmed on 1,548 real rows where Setup
Est is 0 but Setup Act is not, and JobBOSS still printed a computed value,
not a blank. Run is stricter: it ALSO blanks whenever `Est_Run_Hrs = 0`,
even when the employee logged real Run hours -- confirmed with no
exception found on 23,185 real rows. Implemented as extra guards on top
of the existing shared-denominator condition, in the outer `SELECT`'s
`CASE` expressions: `op.Setup_Act_Hrs > 0` for Setup; `op.Run_Act_Hrs > 0
AND op.Run_Est_Hrs > 0` for Run. Deliberately asymmetric -- don't "tidy"
this into one shared condition for both blocks.

**The blank-cell rule above governs individual cells; Summary's aggregate
SUM() needs the same exclusion applied to Act/Est Hrs, not just Adj Hrs --
a real, live bug, found and fixed one session after the rule above was
first confirmed.** The "Operations without Adj E Hrs are not included"
footnote already implied this (that's exactly what "145.95 more than their
own Employee Total" meant), but `op_scored`'s CASE guards originally wrapped
only `Setup_Adj_Hrs`/`Run_Adj_Hrs` -- `Setup_Act_Hrs`/`Setup_Est_Hrs`/
`Run_Act_Hrs`/`Run_Est_Hrs` were summed unconditionally from `op_rollup`,
so an unscoreable operation's real logged Act Hrs still inflated the outer
SUM() denominator even though its Adj Hrs correctly contributed nothing to
the numerator. Caught on EMP-J, a real employee with exactly one scoreable
operation in a short date range (Adj 4 / Act 2.92, matching JobBOSS's real
Detail export exactly -- 136.99%) plus several Work_Center.Type='Direct'
monthly overhead-bucket operations (ENGINEER/R&D time logged against a
non-customer "job" named after the month, e.g. "2026-AUG" -- the same
month-standing-in-for-Job convention as the Indirect buckets, just not
flagged Indirect by Work_Center.Type, so _OP_TOTALS_CTE's/op_rollup's
existing Indirect exclusion doesn't catch it either): Summary showed 0.6%
(the ~637 real-but-unscoreable overhead hours drowning out the 2.92 real
scoreable hours in the denominator) where JobBOSS's own report shows
136.99%. Fixed by wrapping all four columns in the same CASE guards as the
Adj Hrs columns in `op_scored`, confirmed to reproduce JobBOSS's 136.99%
exactly once fixed. `Job.Customer IS NULL` was investigated as a cleaner,
more general exclusion signal for this whole class of non-customer "job"
but rejected -- it also matches genuine internal/non-billed real work
(e.g. a machine-install project, a rework placeholder job), which would be
wrongly excluded too; gating on scoreability (the same condition Adj Hrs
already uses) has no such false-positive risk since it only ever excludes
operations that were already contributing nothing to the numerator.

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

Indirect time (vacation, training, cleanup, etc.) is excluded via
Work_Center.Type <> 'Indirect' from _OP_TOTALS_CTE and Summary's op_rollup
(Work_Center has a real Type column, Direct/Indirect, confirmed directly
from this shop's own Work Center setup screen -- it's the *work center*
that's marked Indirect, not the job), keeping non-production time out of
the proportional-share denominator and out of Summary's Setup/Run Act Hrs
rollup, which is specifically a job-efficiency score. **Detail's own
op_detail does NOT exclude it** -- confirmed directly against JobBOSS's
real export that Indirect time appears as real line items in the real
Detail report (e.g. "2026-OCT / INDIRECT / TRAINING"), not folded away;
see "Detail includes Indirect operations" below for the full reasoning.

**Department comes from Employee.Department -- the employee's own assigned
department -- not Work_Center.Department.** An earlier version of this
sourced Department from the work center of each operation (i.e. "where the
work happened"), which is wrong for this shop: confirmed directly by the
user that employees are assigned a department as a fixed attribute of the
employee record, not inferred from whatever work center they happened to
log time against on a given day. Confirmed live that the two are genuinely
different columns (Employee.Department has real, populated values like
"CNC DEPT"/"Assembly shop"/"Office"; Employee.Work_Center is NULL for
every active employee on this install, so there's no way to derive one
from the other). Both queries join Employee (already needed for name/
Status) and select e.Department directly -- Detail's outer SELECT isn't
grouped, so this needed no GROUP BY change there; Summary's outer SELECT
is grouped, so e.Department had to be added to its GROUP BY alongside
e.First_Name/e.Last_Name, but since Department is a 1:1 attribute of the
employee (not of the operation), this doesn't change Summary's row count
or grouping at all -- it's the exact same one-row-per-employee result as
before Department existed, just with the column attached.
"""

from __future__ import annotations

from typing import Any, Dict, List

from experimental.db_integration import connect, employee_filter_clause
from modules.reporting.reports.base import ReportDefinition

# op_totals: Act Hrs summed across EVERY employee (active or not) who
# logged time on an operation, never filtered by the Employee picker --
# see module docstring ("deliberately NOT employee-filtered"). This is the
# shared denominator both queries divide an operation's Est Hrs by.
#
# Reverted an Active-only filter here (`JOIN Employee te ... AND
# te.Status = 'Active'`) that turned out to be wrong, confirmed with exact
# arithmetic against a real JobBOSS export: Job 26734, WELDING OP2
# (Job_Operation 145813, Est_Run_Hrs=40) has three real contributors --
# call them EMP-A (Active, 11.0 hrs), EMP-B (Inactive, 5.0 hrs), EMP-C
# (Inactive, 25.25 hrs). JobBOSS's own real Adj Hrs for EMP-A is
# 10.6666666666667. 40 * 11 / (11 + 5 + 25.25) = 40 * 11 / 41.25 =
# 10.666666666666666 -- matches to full float precision only when
# Inactive coworkers' hours ARE included in the denominator. Excluding
# them (the reverted behavior) computed EMP-A's share as 11/11 = 100%,
# giving Adj = 40.0 -- nearly 4x too high. The real report's "Active
# Employees Only" population (which
# EMPLOYEES get their own row in the output) and the proportional-share
# DENOMINATOR (whose hours get pooled per operation) turned out to be two
# independent things, not the same population as originally assumed when
# the Active filter was added (chasing a different, still-unexplained
# mismatch on Job 27173H -- see "Two operations investigated to a dead
# end" below; that investigation's own numbers never actually confirmed
# the Active filter either, in hindsight).
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
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
          AND (wc.Type IS NULL OR wc.Type <> 'Indirect')
    GROUP BY jot.Job_Operation
)"""

# Per-employee "% Indirect" (vacation, training, cleanup, etc., time logged
# against a Work_Center.Type = 'Indirect' work center -- confirmed live:
# this shop has exactly one, 'INDIRECT', and real time against it is logged
# the same way as any other operation, via Act_Setup_Hrs/Act_Run_Hrs). The
# ONLY CTE here that deliberately does NOT filter out Indirect -- it needs
# both the indirect and non-indirect hours to compute a ratio between them.
# Not Active-employee-filtered like _OP_TOTALS_CTE: this is a plain
# per-employee total, not a shared denominator split between coworkers, so
# there's nothing for an inactive coworker to dilute.
_INDIRECT_TOTALS_CTE = """indirect_totals AS (
    SELECT jot.Employee,
           SUM(CASE WHEN wc.Type = 'Indirect' THEN jot.Act_Setup_Hrs + jot.Act_Run_Hrs ELSE 0 END) AS Indirect_Hrs,
           SUM(jot.Act_Setup_Hrs + jot.Act_Run_Hrs) AS Total_Hrs
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    JOIN Work_Center wc ON wc.Work_Center = jo.Work_Center
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0
    GROUP BY jot.Employee
)"""

# op_detail groups by jot.Job_Operation -- the real foreign key, matching
# Summary's op_rollup -- not the descriptive (Job, Work_Center,
# Operation_Service) triple used here before. See module docstring
# ("Grouping bug fix"): that triple isn't unique, and grouping by it
# silently merged distinct operations that happen to share a display label.
# Job/Work_Center/Operation_Service are selected alongside Job_Operation in
# the GROUP BY -- safe, since Job_Operation determines them uniquely.
#
# Unlike op_rollup (Summary) and _OP_TOTALS_CTE, this does NOT exclude
# Indirect work centers -- confirmed directly against JobBOSS's own real
# export that Indirect time (vacation, training, cleanup, etc.) appears as
# real line items in the real Detail report, not folded away. JobBOSS logs
# each Indirect category (TRAINING, CLEAN-UP, MAINTNANCE, ADMIN, etc.) as
# its own Job_Operation per month, with the month itself (e.g. "2026-OCT")
# standing in for Job -- jo.Job already carries that real value through
# unmodified, no special-casing needed. Est_Setup_Hrs/Est_Run_Hrs are a
# real stored 0.0 for these (not NULL) -- harmless, since the LEFT JOIN to
# op_totals below (which still excludes Indirect -- there's no real
# "proportional share" concept for non-job time) means ot.Total_*_Act_Hrs
# is NULL for an Indirect row regardless, so Setup_Adj_Hrs/Run_Adj_Hrs
# still correctly come out NULL (blank), matching the real report's own
# blank Adj Hrs/% Eff columns for these rows.
#
# The two extra guards in the outer SELECT's CASE expressions
# (`op.Setup_Act_Hrs > 0`, and `op.Run_Act_Hrs > 0 AND op.Run_Est_Hrs > 0`)
# are JobBOSS's own blank-cell rules, confirmed exhaustively -- see the module
# docstring's "When JobBOSS blanks an Adj Hrs cell". They are deliberately
# asymmetric: Setup has no `Est > 0` guard because the real report DOES print
# a real 0 for a Setup block with Est_Setup_Hrs = 0 and real logged setup
# hours (1,548 such rows), whereas Run with Est_Run_Hrs = 0 is always blank
# (23,185 rows). Don't "tidy" this into one shared condition.
_EMPLOYEE_EFFICIENCY_DETAIL_QUERY = """
WITH {op_totals},
{indirect_totals},
op_detail AS (
    SELECT jot.Employee, jot.Job_Operation, jo.Job, jo.Work_Center, jo.Operation_Service,
           SUM(jot.Act_Setup_Hrs) AS Setup_Act_Hrs, MAX(jo.Est_Setup_Hrs) AS Setup_Est_Hrs,
           SUM(jot.Act_Run_Hrs) AS Run_Act_Hrs, MAX(jo.Est_Run_Hrs) AS Run_Est_Hrs,
           CASE WHEN SUM(jot.Act_Run_Hrs) = 0 THEN 0 ELSE SUM(jot.Act_Run_Qty) END AS Run_Qty
    FROM Job_Operation_Time jot
    JOIN Job_Operation jo ON jo.Job_Operation = jot.Job_Operation
    WHERE jot.Work_Date BETWEEN %s AND %s AND jot.Rework_Time = 0 AND {employee_clause}
    GROUP BY jot.Employee, jot.Job_Operation, jo.Job, jo.Work_Center, jo.Operation_Service
)
SELECT op.Employee, e.First_Name, e.Last_Name, op.Job, op.Work_Center, op.Operation_Service, e.Department,
       op.Setup_Act_Hrs, op.Setup_Est_Hrs,
       CASE WHEN ot.Total_Setup_Act_Hrs > 0 AND op.Setup_Act_Hrs > 0
            THEN op.Setup_Est_Hrs * op.Setup_Act_Hrs / ot.Total_Setup_Act_Hrs END AS Setup_Adj_Hrs,
       op.Run_Act_Hrs, op.Run_Est_Hrs, op.Run_Qty,
       CASE WHEN ot.Total_Run_Act_Hrs > 0 AND op.Run_Act_Hrs > 0 AND op.Run_Est_Hrs > 0
            THEN op.Run_Est_Hrs * op.Run_Act_Hrs / ot.Total_Run_Act_Hrs END AS Run_Adj_Hrs,
       CASE WHEN it.Total_Hrs > 0 THEN it.Indirect_Hrs / it.Total_Hrs * 100 END AS Indirect_Pct
FROM op_detail op
JOIN Employee e ON e.Employee = op.Employee
LEFT JOIN op_totals ot ON ot.Job_Operation = op.Job_Operation
LEFT JOIN indirect_totals it ON it.Employee = op.Employee
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
#
# op_scored carries the same blank-cell guards as Detail (own Act Hrs > 0,
# plus Run Est Hrs > 0 for Run). Here they do real arithmetic work rather
# than just controlling display: an operation JobBOSS leaves blank is one it
# also leaves out of its own "Employee Total" row ("Operations without Adj E
# Hrs are not included"), and because SUM() ignores NULL, NULLing those
# operations here drops them from the rollup exactly the same way.
#
# Critically, the SAME guard is applied to Setup_Act_Hrs/Setup_Est_Hrs/
# Run_Act_Hrs/Run_Est_Hrs here too, not just the Adj_Hrs columns -- an
# unscoreable operation's real logged Act Hrs must NOT still flow into the
# outer SELECT's SUM(Act_Hrs) denominator just because its Adj_Hrs correctly
# came out NULL. Confirmed as a real, live bug: an employee with one real
# production operation (Adj 4 / Act 2.92, matching JobBOSS's own Detail
# export exactly -- 136.99%) plus several Work_Center.Type='Direct' monthly
# overhead buckets (ENGINEER/R&D time logged against a non-customer "job"
# named after the month, e.g. "2026-AUG" -- JobBOSS's own month-standing-in-
# for-Job convention, same idea as the Indirect buckets but not flagged
# Indirect by Work_Center.Type) showed JobBOSS's real "Employee Total" % at
# 136.99% (matching the one real operation exactly, since the overhead rows
# have Est_Run_Hrs = 0 and are excluded) while this query, before this fix,
# summed those overhead rows' real Act Hrs into the denominator anyway
# (2.92 real + ~637 overhead = ~640), producing 0.6% -- off by over 200x.
# Gating Act/Est Hrs the same way Adj_Hrs already is reproduces JobBOSS's
# 136.99% exactly, confirmed live against that same employee/date range.
_EMPLOYEE_EFFICIENCY_SUMMARY_QUERY = """
WITH {op_totals},
{indirect_totals},
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
    SELECT op.Employee,
           CASE WHEN ot.Total_Setup_Act_Hrs > 0 AND op.Setup_Act_Hrs > 0
                THEN op.Setup_Act_Hrs END AS Setup_Act_Hrs,
           CASE WHEN ot.Total_Setup_Act_Hrs > 0 AND op.Setup_Act_Hrs > 0
                THEN op.Setup_Est_Hrs END AS Setup_Est_Hrs,
           CASE WHEN ot.Total_Run_Act_Hrs > 0 AND op.Run_Act_Hrs > 0 AND op.Run_Est_Hrs > 0
                THEN op.Run_Act_Hrs END AS Run_Act_Hrs,
           CASE WHEN ot.Total_Run_Act_Hrs > 0 AND op.Run_Act_Hrs > 0 AND op.Run_Est_Hrs > 0
                THEN op.Run_Est_Hrs END AS Run_Est_Hrs,
           CASE WHEN ot.Total_Setup_Act_Hrs > 0 AND op.Setup_Act_Hrs > 0
                THEN op.Setup_Est_Hrs * op.Setup_Act_Hrs / ot.Total_Setup_Act_Hrs END AS Setup_Adj_Hrs,
           CASE WHEN ot.Total_Run_Act_Hrs > 0 AND op.Run_Act_Hrs > 0 AND op.Run_Est_Hrs > 0
                THEN op.Run_Est_Hrs * op.Run_Act_Hrs / ot.Total_Run_Act_Hrs END AS Run_Adj_Hrs
    FROM op_rollup op
    JOIN op_totals ot ON ot.Job_Operation = op.Job_Operation
)
SELECT op.Employee, e.Department, e.First_Name, e.Last_Name,
       SUM(op.Setup_Act_Hrs) AS Setup_Act_Hrs,
       SUM(op.Setup_Est_Hrs) AS Setup_Est_Hrs,
       SUM(op.Setup_Adj_Hrs) AS Setup_Adj_Hrs,
       SUM(op.Run_Act_Hrs) AS Run_Act_Hrs,
       SUM(op.Run_Est_Hrs) AS Run_Est_Hrs,
       SUM(op.Run_Adj_Hrs) AS Run_Adj_Hrs,
       CASE WHEN it.Total_Hrs > 0 THEN it.Indirect_Hrs / it.Total_Hrs * 100 END AS Indirect_Pct
FROM op_scored op
JOIN Employee e ON e.Employee = op.Employee
LEFT JOIN indirect_totals it ON it.Employee = op.Employee
WHERE e.Status = 'Active' AND {employee_clause}
GROUP BY op.Employee, e.Department, e.First_Name, e.Last_Name, it.Indirect_Hrs, it.Total_Hrs
ORDER BY e.Last_Name, e.First_Name
"""

DETAIL_COLUMNS = (
    'employee', 'job', 'work_center', 'department', 'operation',
    'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_qty', 'run_adj_hrs', 'run_pct_eff', 'pct_indirect',
)
DETAIL_HEADERS = [
    'Employee', 'Job', 'Work Center', 'Department', 'Operation',
    'Setup Act Hrs', 'Setup Est Hrs', 'Setup Adj Hrs', 'Setup % Eff',
    'Run Act Hrs', 'Run Est Hrs', 'Run Qty', 'Run Adj Hrs', 'Run % Eff', '% Indirect',
]
# Setup and Run are always separate, parallel blocks, never summed into one
# blended "Total" -- matches Detail, and matches the real report, which
# never combines them either (Setup isn't part of any combined score).
SUMMARY_COLUMNS = (
    'employee', 'department', 'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_adj_hrs', 'run_pct_eff', 'pct_indirect',
)
SUMMARY_HEADERS = [
    'Employee', 'Department', 'Setup Act Hrs', 'Setup Est Hrs', 'Setup Adj Hrs', 'Setup % Eff',
    'Run Act Hrs', 'Run Est Hrs', 'Run Adj Hrs', 'Run % Eff', '% Indirect',
]


def _pct_or_blank(numerator: float, denominator: float) -> str:
    """numerator/denominator * 100 as a 1-decimal string, or '' if
    denominator is 0/falsy (nothing actually worked yet -- not 0% efficient,
    just not comparable).
    """
    if not denominator:
        return ''
    return f"{(numerator / denominator) * 100:.1f}"


def _already_pct_or_blank(value) -> str:
    """A percentage SQL already computed (Indirect_Pct) as a 1-decimal
    string, or '' if it's None (SQL's CASE returns NULL when Total_Hrs was
    0 -- no time logged at all in range, not 0% indirect).
    """
    return f"{value:.1f}" if value is not None else ''


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
            'department': r.get('Department') or '',
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
            'pct_indirect': _already_pct_or_blank(r.get('Indirect_Pct')),
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
            'department': r.get('Department') or '',
            'setup_act_hrs': f"{setup_act:.2f}",
            'setup_est_hrs': f"{setup_est:.2f}",
            'setup_adj_hrs': f"{setup_adj:.2f}",
            'setup_pct_eff': _pct_or_blank(setup_adj, setup_act),
            'run_act_hrs': f"{run_act:.2f}",
            'run_est_hrs': f"{run_est:.2f}",
            'run_adj_hrs': f"{run_adj:.2f}",
            'run_pct_eff': _pct_or_blank(run_adj, run_act),
            'pct_indirect': _already_pct_or_blank(r.get('Indirect_Pct')),
        })
    return rows


def _fetch_detail(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    employee_clause, employee_params = employee_filter_clause(filters.get('employees'), column='jot.Employee')
    query = _EMPLOYEE_EFFICIENCY_DETAIL_QUERY.format(
        op_totals=_OP_TOTALS_CTE, indirect_totals=_INDIRECT_TOTALS_CTE, employee_clause=employee_clause)
    # op_totals' date-range placeholders come first in the formatted query
    # text, then indirect_totals', then op_detail's own -- params must be
    # supplied in that order.
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end, start, end, start, end) + employee_params)
            return _rows_from_detail(cur.fetchall())


def _fetch_summary(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    employee_clause, employee_params = employee_filter_clause(filters.get('employees'), column='op.Employee')
    query = _EMPLOYEE_EFFICIENCY_SUMMARY_QUERY.format(
        op_totals=_OP_TOTALS_CTE, indirect_totals=_INDIRECT_TOTALS_CTE, employee_clause=employee_clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (start, end, start, end, start, end) + employee_params)
            return _rows_from_summary(cur.fetchall())


# Printed at the bottom of every exported Detail/Summary file -- the same
# plain-language form as the module docstring's formula, condensed to what a
# reader of the exported file actually needs, not the full investigation.
# Each line is written to a single, unwrapped cell (_write_xlsx_report_sheet
# just does ws.append([line])) so it visually spills across however many
# columns its length needs -- kept under ~90 chars/line so that spill stays
# within column K on a normal-width Detail/Summary sheet instead of running
# off past the data columns entirely.
_FORMULA_FOOTER = [
    "Adj Hrs = Est Hrs x (own Act Hrs / total Act Hrs on that op, all employees)",
    "% Eff = Adj Hrs / own Act Hrs x 100",
    "Setup and Run are scored separately, never combined. Run = JobBOSS's official score.",
    "Blank Adj Hrs / % Eff = not scoreable (no comparable hours, or a JobBOSS exclusion).",
    "% Indirect = Indirect hours / total hours x 100, per employee (same on every row).",
]

# Everything in DETAIL_COLUMNS/SUMMARY_COLUMNS except the identifier columns
# (employee/job/work_center/department/operation) -- the only ones with a
# sensible department-average (see base.ReportDefinition.average_columns and
# module.py's _department_average_row(), which would otherwise average an
# identifier column whenever its values happen to all parse as numbers).
_DETAIL_AVERAGE_COLUMNS = (
    'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_qty', 'run_adj_hrs', 'run_pct_eff', 'pct_indirect',
)
_SUMMARY_AVERAGE_COLUMNS = (
    'setup_act_hrs', 'setup_est_hrs', 'setup_adj_hrs', 'setup_pct_eff',
    'run_act_hrs', 'run_est_hrs', 'run_adj_hrs', 'run_pct_eff', 'pct_indirect',
)

EMPLOYEE_EFFICIENCY_DETAIL = ReportDefinition(
    name="Employee Efficiency - Detail",
    columns=DETAIL_COLUMNS,
    headers=DETAIL_HEADERS,
    fetch=_fetch_detail,
    resize_mode="interactive",
    uses_dates=True,
    dates_required=True,
    uses_employee_filter=True,
    uses_department_tabs=True,
    average_columns=_DETAIL_AVERAGE_COLUMNS,
    uses_employee_total_rows=True,
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
    uses_department_tabs=True,
    average_columns=_SUMMARY_AVERAGE_COLUMNS,
    footer_lines=_FORMULA_FOOTER,
)
