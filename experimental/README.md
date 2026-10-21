# Experimental Features

This directory contains experimental and work-in-progress features that are **not yet ready for production use**.

## Current Experimental Features

### Database Integration

**Status**: Working against a live JobBOSS SQL Server, scoped to the `Job`, `Delivery`, `Job_Operation`, `Job_Operation_Time`, `Employee`, and `Work_Center` tables. Still experimental: gated behind the "Enable experimental features (Reporting)" setting, and the exact column names (particularly `Job.Status`/`Employee.Status`) should be confirmed against your own JobBOSS schema the first time you connect -- see "Known gap" below.

**Purpose**: Lets the Reporting tab pull live job/labor data straight out of JobBOSS over SQL Server (via [`python-tds`](https://pypi.org/project/python-tds/), the same pure-Python TDS client used by the sibling `shop-schedule` project), instead of showing placeholder sample data.

**Architecture**: `db_integration.py` is shared infrastructure only -- credentials, connection setup, and the two filter-input lookups (`fetch_customers()`, `fetch_employees()`) reused by more than one report type. Every report type's query, row-formatter, and display columns/headers live in `modules/reporting/reports/` instead, one file per report type (see that package's `__init__.py` for the registry). Adding a new report type means adding a file there, not editing `db_integration.py` or `modules/reporting/module.py`.

**Connection setup**:

1. Create a read-only SQL login, following the same model as `shop-schedule`:

   ```sql
   CREATE LOGIN jobdocs_reporting_ro WITH PASSWORD = 'choose-a-strong-password';
   USE <your_jobboss_database>;
   CREATE USER jobdocs_reporting_ro FOR LOGIN jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Job TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Delivery TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Job_Operation TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Job_Operation_Time TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Employee TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Work_Center TO jobdocs_reporting_ro;
   ```

   `Delivery`/`Job_Operation` are only needed for Job Report (Promise Date and Current Work Center respectively). `Job_Operation_Time`/`Employee`/`Work_Center` are only needed for the two Employee Efficiency report types. Every other report type reads `Job` alone.

2. In JobDocs, open **Settings > Advanced Settings**, check **Enable experimental features (Reporting)**, then fill in the JobBOSS DB Host / Port / Database / Username / Password fields. Use the exact `Server` value from your SQL Server ODBC DSN for Host -- for a named instance (e.g. `SMI-APP02\JBSQL`), leave Port blank and it resolves automatically via the SQL Browser service, the same way the ODBC driver does for Excel/Power Query.
3. The password is **not** written to `settings.json`. It's stored in your OS credential store (Windows Credential Manager, macOS Keychain, or Linux Secret Service) via the `keyring` package, under service name `JobDocs`.
4. The Reporting tab connects to the database automatically as soon as it's opened -- a small status indicator in the corner shows green once connected (click it to retry if it's gray/red). Pick a report type and **Generate Report**.

**Exported files are real Excel Tables**: the `.xlsx` export wraps the header + data rows in an Excel Table with its AutoFilter, so every column is sortable/filterable as soon as the file opens in Excel -- not a plain value dump.

**Known gap**: the `Status` columns assumed by most reports (`Job.Status`, `Employee.Status`, same single-char-or-word convention as `Job_Operation.Status`), and `Total_Price` (summed per customer for Top Customers' "Gross Revenue") have not been verified against a real schema from this codebase alone -- confirm these match your JobBOSS version the first time you connect.

**Known limitation -- unencrypted transport by default**: like `shop-schedule`, `pytds` doesn't encrypt the connection unless given a CA certificate, which isn't wired up here yet. This matches the same trust model as existing ODBC/Excel access to the same server; not a new exposure, but worth closing later if someone wants to add `JOBBOSS_DB_CAFILE`-style TLS support (see `shop-schedule/README.md` for the pattern).

**Not Recommended For**:
- A different ERP/database (only JobBOSS/MSSQL via `pytds` is implemented)
- Any write-back to JobBOSS (every query is SELECT-only, matching the login's grants)

#### Job Report (`modules/reporting/reports/job_report.py`)

Matches the shape of this shop's existing "Job Report" (jobRpt) -- a custom report, not something JobBOSS ships built-in (one row per open job: PO, line, drawing, revision, promise date). Confirmed against a real schema that `Job.Customer_PO`/`Customer_PO_LN` (not `SO_Detail.PO`/`Line` -- `SO_Detail` was entirely unused, 0 rows, on the schema this was built against) are the real PO/Line source, and `Job.Rev` (not `Job.Revision`, always blank there) is the populated revision field -- if your install actually uses JobBOSS's Sales Order module, you may want `SO_Detail` instead. There is no column anywhere in that schema corresponding to the sample report's "Classification" field; it's left blank rather than guessed.

**Current Work Center**: the work center of each job's earliest non-complete operation (by `Job_Operation.Sequence`) -- the exact "current operation" logic already proven live in the sibling `shop-schedule` project's `jobboss_db.py`, reused here. Unlike that project's `CROSS APPLY` (safe there only because its query starts `FROM Job_Operation` itself, so a matching row is guaranteed), Job Report starts `FROM Job` with no such guarantee -- an `Active` job isn't certain to have a non-complete operation row (not yet routed, or operations closed out of sync with the job header). Uses `OUTER APPLY` instead, so such a job still appears in the report with a blank Current Work Center rather than being silently dropped.

**Late-job highlight**: the Scheduled End Date cell turns red (on screen and in the `.xlsx` export) whenever it's later than that job's Promise Date -- same comparison Report Fixer's Fix & Export used to flag the same condition, reapplied here since Job Report is a fresh SQL pull rather than that tool's output. A blank Scheduled End Date or Promise Date is never flagged (nothing to compare).

**Filters**: Customer picker (checklist, zero = All) and "Exclude assembly sub-jobs" (filters on `Assembly_Level = 0`, i.e. `Top_Lvl_Job == Job`, to drop component jobs like "30274A" under a parent "30274").

#### Jobs by Customer, Jobs by Date Range, Recent Jobs (`jobs_by_customer.py`, `jobs_by_date_range.py`, `recent_jobs.py`)

Three plain job lists (Date/Customer/Job #/Description/Status), sharing one row-formatter (`_common.py`'s `rows_from_jobs`) and column/header set -- just a different filter/query each: a Customer picker, a mandatory date range, or no filter (most recent 50) respectively. All three filter/sort on `Job.Order_Date`, not `Released_Date` -- found by manual testing that `Released_Date` is only populated for roughly the last year on this schema, which made every date-based report silently come back empty for anything older.

#### Top Customers (`top_customers.py`)

Top 10 customers by gross revenue (`SUM(Total_Price)`), with an optional date range -- no dates picked means all time, not an error (unlike Jobs by Date Range, where both dates are mandatory). The read-only login's `GRANT SELECT ON dbo.Job` already covers `Total_Price` (SQL Server grants apply to the whole table), but if your DBA prefers column-level grants instead, include it explicitly. This is the one report that exposes dollar figures; the rest only show job/customer/schedule/labor-hours metadata.

#### Job Statistics (`job_statistics.py`)

Three quick counts (Total Jobs, Jobs This Month, Jobs This Week) from `Job.Order_Date`. No filters.

#### Employee Efficiency - Detail / Summary (`employee_efficiency.py`)

Replaces Report Fixer's "JobBOSS Custom Reports" Employee Efficiency hack (run JobBOSS's own canned export, then hide rows behind an Excel AutoFilter -- no real querying) with a direct SQL pull. **Detail** is one row per employee per job operation; **Summary** rolls that up to one row per employee. Both require a date range (filtered on `Job_Operation_Time.Work_Date`, the real "Time Entry Date Range" field) and support an optional Employee picker (checklist, zero = all active employees).

**Department comes from `Employee.Department` -- the employee's own assigned department -- not `Work_Center.Department`.** An earlier version sourced it from the work center of each operation ("where the work happened"); confirmed wrong directly by the user (employees are assigned a department as a fixed attribute of their own record) and confirmed live (`Employee.Work_Center` is `NULL` for every active employee on this install, so there's no deriving one from the other -- they're genuinely different columns with real, different values, e.g. `Employee.Department` = "CNC DEPT"/"Assembly shop"/"Office"). Both queries join `Employee` (already needed for name/`Status`) and select `e.Department` directly.

**"By Department" checkbox is an export-split option, not a filter.** Every department's rows are always fetched; checking the box only changes what `_export_xlsx()` does with them -- it splits the data into one worksheet tab per department (each with its own trailing "Department Average" row, the arithmetic mean of every numeric column for that department) instead of one combined sheet. CSV and PDF exports, and the on-screen table, are unaffected -- they have no native multi-tab concept, so Department just shows as a normal column there. An earlier version of this tried a multi-select Department *filter* (an IN-clause restricting which rows came back, mirroring the Customer/Employee pickers) -- scrapped because it solved a problem nobody had: the user wanted to see every department's numbers, split out for comparison, not to narrow the report down to one department at a time.

Because Department is a 1:1 attribute of the employee rather than of the operation, it doesn't change **Summary's grain** -- SQL Server requires it in the `GROUP BY` since it's selected without aggregation, but that's grouping by something already fixed per employee, so Summary stays one row per employee, same as before Department existed.

**"% Indirect"** is each employee's total Indirect hours (vacation, training, cleanup, etc. -- logged against the shop's one `Work_Center` of `Type = 'Indirect'`) divided by their total hours of every kind, within the picked date range, x 100. A separate `indirect_totals` CTE computes this -- the only CTE in this file that deliberately does *not* exclude Indirect work centers, since it needs both the indirect and non-indirect hours to compute a ratio between them. Like Department, this is a per-employee total: the same value repeats on every one of an employee's rows in Detail, and appears once per employee in Summary.

Source tables, confirmed against a full live schema dump (no `Labor_Ticket` table exists on this install, despite that being a more commonly-expected JobBOSS table name): `Job_Operation_Time` (one row per employee per job-operation per `Work_Date` -- the actual hours/qty an employee logged) joined to `Job_Operation` (the operation's own estimate hours: `Est_Setup_Hrs`, `Est_Run_Hrs`) and `Employee` (name/status). Both queries group by the real `Job_Operation` foreign key, not a descriptive label -- see the grouping-bug note below.

**Both Setup and Run get `Adj Hrs` / `% Eff`, via one formula, reverse-engineered from real exported data** (not a guess, and not the ECI knowledge-base article's formula -- see why below):

```
Adj Hrs = Est Hrs(operation) * Act Hrs(employee, operation) / SUM(Act Hrs, every ACTIVE employee on that operation, within the date range)
% Eff   = Adj Hrs / Act Hrs(employee, operation) * 100
```

An operation's estimated hours get divided among everyone who actually worked it, in proportion to how much real time each person logged -- not based on parts/quantity, and identically for Setup and Run. Found by parsing two real xlsx exports cell-by-cell for the same date range and employees -- JobBOSS's own canned Detail export (39,772 rows, 26 employees) and this module's own Detail export -- and solving for what relationship actually holds between JobBOSS's own Est/Act/Adj columns. Verified on real data, not just plausible-looking: on every row where the operation's identity was unambiguous, **Setup matched exactly on 95.8%** (7,094/7,407), **Run on 70.2% exact + 11.0% within 0.5 hrs** (the rest is explained by the grouping-bug cases below, not left as unexplained noise). Cross-checked again at the aggregate level against one real employee's own "Employee Total" row, independent of the row-level check: predicted totals landed within 1% for both Setup (1247.74 vs 1239.50 actual) and Run (3458.30 vs 3346.62 actual).

**Why this replaces the earlier approach.** The ECI knowledge-base article's formula (`Run Adj Hrs = Act_Run_Qty * Est_Run_Per_Part`) and "Setup Adj Hrs = Setup Est Hrs" were each shipped once and found wrong against real data: Setup % Eff hit 6200% (KYLE ***REDACTED***) and 1237% (DAVID ***REDACTED***) in a real Summary export, and separately, 55.2% of all rows in the real Detail export show a displayed Quantity of 0 alongside a real, nonzero Adj E Hrs (e.g. Quantity=0, Adj E Hrs=0.78125) -- which `Act_Run_Qty * anything` can never produce, proving Quantity was never the real driver of Run's Adj Hrs. `Job_Operation.Est_Run_Per_Part` itself also doesn't reliably match the real per-part rate even read directly -- one real operation implied a rate 20x smaller than what Adj Hrs/Quantity actually required.

**Grouping bug fix (Detail only).** Detail used to group by the descriptive `(Job, Work_Center, Operation_Service)` triple instead of the real `Job_Operation` key -- Summary already grouped correctly. Confirmed wrong directly from the real export: 303 distinct (employee, Job, Work_Center, Operation_Service) combinations appear more than once for the same employee, each time with genuinely different Est/Act/Adj values (e.g. one employee's "13072/ASSEMBLY/ASSEMBLE" appears twice, once with Run Est Hrs 0.5 and once with 10 -- two real, distinct operations sharing a display label, likely a job whose routing revisits the same work center twice). Grouping by the triple silently merged these via `MAX()`/`SUM()`. Detail now groups by `jot.Job_Operation`, same as Summary.

**Independently confirmed exact, two real employees, queried live.** Job 27652, CNC LATHE OP6: ***REDACTED*** (Setup Act 1.0, Run Act 2.5) and ***REDACTED*** (Setup Act 1.5, Run Act 1.5) against a shared Setup/Run Est of 1.25 each. The formula predicts ***REDACTED*** at Setup Adj 0.5 / Run Adj 0.78125 and ***REDACTED*** at Setup Adj 0.75 / Run Adj 0.46875 -- all four match JobBOSS's own real exported values exactly, to full float precision. Two independent employees, both blocks, no rounding -- the strongest confirmation yet.

**The proportional-share denominator is not employee-filtered, but IS Active-employee-filtered.** It sums Act Hrs across every *active* employee who logged time on an operation within the date range, regardless of which employees the Employee picker selected -- otherwise each employee's share would depend circularly on their own filtered-out view of the data. Scoped to the same date range as the rest of the report. The Active-only filter was added after a confirmed real bug: querying Job 27173H live turned up a second contributor, ***REDACTED***, with real Act_Run_Hrs on that operation -- but ***REDACTED*** isn't in JobBOSS's own Employee Efficiency export at all, because ***REDACTED*** isn't an Active employee, and the real report's population (same as this module's Employee picker) is Active-employees-only throughout. Without this filter, an inactive coworker's historical hours were diluting an active employee's share of an operation the real report never counted them against.

**Two operations investigated to a dead end, deliberately left unmodeled.** Job 27173H, GRINDERS OP2 (`Job_Operation` 160964) -- confirmed a single operation, not a hidden duplicate: `Est_Run_Hrs=26.67`, `Est_Required_Qty=80`, `Act_Run_Qty=2` for ***REDACTED***. Real `Adj Hrs = 13.335` (exactly Est/2), which rules out every formula tried: the proportional-share model would need a total of 84 Act Hrs across contributors to produce that, but the database has only 48.25 Act Hrs *ever recorded* against this operation across all of history (***REDACTED*** 42 + ***REDACTED*** 6.25) -- 84 exceeds the maximum possible, not an approximation gap. The qty-based KB formula, computed properly (`2 * 26.67/80 = 0.667`), misses by 20x. Job 27173A, ASSEMBLY/ASSEMBLE (`Job_Operation` 154332) -- confirmed four real contributors (***REDACTED*** 3.5, ***REDACTED*** 13.5, ***REDACTED*** 4.5, ***REDACTED*** 10.25 Act Run Hrs, two of them active), yet JobBOSS's export shows the whole Run block blank for ***REDACTED***, not a computed value. Both are most likely further instances of the "Operations without Adj E Hrs are not included" footnote (above) -- real, confirmed-material, exact trigger condition still unrecovered. Chasing either further would mean guessing a new formula to fit two known outliers, the exact mistake this module's history already warns against; both are left as documented exceptions rather than forced to fit.

**Accuracy climbs sharply on newer data -- the remaining gap is mostly historical noise, not formula error.** Comparing this module's own Detail export against a real one, restricted by job-number range (chronological in this shop) and counting only rows where both sides computed a real value (excluding the still-unmodeled "blank" cases above): pre-2026 jobs matched ~90% exactly; jobs on the newer time clock system (job >= 29000, per the user) matched 97-99%. Two further non-formula gap sources were identified from real data and are deliberately not modeled: (1) an operator can mark an operation complete before it's actually finished, then add a brand-new `Job_Operation` to keep logging hours against the schedule -- JobBOSS's own Adj Hrs still credits the *original* operation's estimate (confirmed live: Job 30055/CNC VTL/OP1 has two `Job_Operation` ids, one with the real `Est_Run_Hrs=60` matching JobBOSS's `Adj Hrs` exactly, and an all-zero replacement created after the original was closed prematurely); (2) `Operation_Service` is free text with no integrity constraint -- a mistyped label can misfile a real entry with nothing to catch it. This module's own SQL is unaffected (always groups/joins by the real `Job_Operation` id -- see **"Job_Operation is the real identifier, never the descriptive text"** below), but any text-based comparison against a real export is exposed to it, including the ones that produced the percentages above.

**Job_Operation is the real identifier for an operation -- never `(Job, Work_Center, Operation_Service)`.** Confirmed directly by the user: a job's routing can legitimately revisit the same work center under the same operation label more than once (each visit gets its own `Job_Operation` id, by design), operators can add administrative replacement operations under an existing label (see above), and `Operation_Service` itself is free text with no constraint preventing a typo. All three mean the descriptive triple is never safe to group or join on. Every query in this module already follows this (grouping/joining is always by `jot.Job_Operation`); this is the rule that drove the Detail grouping-bug fix above and should be followed by any future JobBOSS report in this repo.

**Qty-sanity guard, removed.** The old `_QTY_SANITY_MULTIPLIER` guard (one real operation: `Est_Required_Qty = 1`, `Act_Run_Qty = 5,629`, a historical data-entry error) existed only because the old formula multiplied by `Act_Run_Qty`. The new formula doesn't use it at all, so that failure mode can't recur here; `Run_Qty` is now purely an informational display column.

**Two rules confirmed directly from JobBOSS's own report source** (`LR_EmployeeEfficiency_Rpt.htm`, the VBScript that builds this report's real SQL query -- found on the JobBOSS server's Reporting share and read from a local copy, not live on the server), not inferred like everything above:
- `Job_Operation_Time.Rework_Time = 0` is filtered on every query.
- If an employee's summed Run Act Hrs for an operation is 0, JobBOSS forces the reported quantity to 0 too, regardless of what `Act_Run_Qty` itself summed to (`IIF(ARHSum=0, 0, ARQSum)` in the source) -- applied here as part of computing Detail's informational Run Qty column.

The actual Adj E Hrs / % Eff Crystal Reports formula definition itself was never recovered from the `.rpt` file -- its formula definitions are compiled to a proprietary bytecode, not stored as readable text (confirmed by extracting its OLE streams directly: near-uniform byte-value distribution, no plain text, no standard compression). The formula above was recovered by reverse-engineering real exported output instead, which is why it's stated as empirically confirmed rather than read from JobBOSS's own source.

**Indirect time is excluded** (vacation, training, cleanup, etc.): both queries join `Work_Center` and filter `Type <> 'Indirect'`, always on, not a checkbox (indirect time counting toward an employee's efficiency is a correctness bug, not an optional view). It's the *work center* that carries this distinction (confirmed directly from this shop's Work Center setup screen -- `Work_Center.Type` is `Direct`/`Indirect`), not the job -- an earlier version of this filter wrongly checked `Job.Type` instead, which has no such value.

**Active Employees Only / grouped quantities**: both always-on for v1, not separate checkboxes -- the Employee picker only ever lists `Employee.Status = 'Active'` rows (itself an unverified assumption, same caveat as `Job.Status` above), and Detail is inherently grouped per (employee, operation) by the query itself. Work Center / Supervisor / Job filters from the real report are not included in v1.

## Contributing

If you'd like to work on experimental features:

1. These features are incomplete and may change significantly
2. Feel free to contribute improvements
3. Open an issue before major changes
4. Consider the feature experimental until moved to main modules/

## Moving to Production

When an experimental feature is ready:

1. Complete implementation with tests
2. Add proper error handling
3. Document usage thoroughly
4. Move to appropriate location in main codebase
5. Update CHANGELOG.md
