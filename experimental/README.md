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
4. On the Reporting tab, click **Connect to Database**, then pick a report type and **Generate Report**.

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

Source tables, confirmed against a full live schema dump (no `Labor_Ticket` table exists on this install, despite that being a more commonly-expected JobBOSS table name): `Job_Operation_Time` (one row per employee per job-operation per `Work_Date` -- the actual hours/qty an employee logged) joined to `Job_Operation` (the operation's own estimate hours: `Est_Setup_Hrs`, `Est_Run_Hrs`, `Est_Run_Per_Part`) and `Employee` (name/status). Both queries group by `(Employee, Job_Operation)` first before aggregating further, since an employee who worked the same operation across several days has multiple `Job_Operation_Time` rows for it -- grouping first avoids multiply-counting that operation's fixed estimate values.

**`Adj Hrs` / `% Eff` use the real, documented JobBOSS formula** -- confirmed via ECI's own knowledge base article ("JobBOSS - Employee Efficiency Report", #000012591), not a guess: `Adj Hrs = Act_Run_Qty * Est_Run_Per_Part`, `% Eff = Adj Hrs / Act_Run_Hrs * 100`. **Setup is excluded from the ratio entirely** (per the article: "Employee Efficiency does not consider the Setup Estimate Time") -- Setup Act/Est Hrs are still shown for reference, they just don't feed `% Eff`. `Act_Run_Hrs`, not the schema's separate `Act_Run_Labor_Hrs`, is correct here (the article: "uses the Machine Hours, not Labor Hours"). Verified against the article's own worked example (Make Qty 100 @ 30 parts/hr, a 2-hour entry with 25 parts run -> Adj Hrs 0.83, %Eff 41.5%) in `tests/test_report_employee_efficiency.py`.

Three earlier formulas were tried and dropped before finding this -- logged here so they aren't retried: (1) a naive Est/Act ratio of the Hours columns, which swings wildly whenever actual run quantity differs from the original estimate; (2) `Job_Operation.Efficiency_Pct`, live-tested as a flat `100.0` for every employee regardless of real performance -- a static scheduling default; (3) `Est Hrs * Setup_Pct_Complete/Run_Pct_Complete / 100`, which looked promising offline but collapsed to near-zero live a day later, since those fields reflect whether the *operation* is closed out as of today, not historical progress.

**Bad-data guard**: one real operation was found live with `Est_Required_Qty = 1` (the job needed one part) but `Act_Run_Qty = 5,629` (parts logged as run) -- a historical data-entry error, not a formula bug, that blew one employee's `% Eff` up to 796%. `_QTY_SANITY_MULTIPLIER` in `employee_efficiency.py` is a pragmatic stand-in, not a confirmed JobBOSS rule: an operation's Run Act Hrs and Adj Hrs are both excluded from `% Eff` (not from the informational Hours columns) when `Act_Run_Qty` exceeds `Est_Required_Qty` by more than that multiplier. Chosen to favor robustness over precision given this was found in the first employee checked closely.

**Two rules confirmed directly from JobBOSS's own report source** (`LR_EmployeeEfficiency_Rpt.htm`, the VBScript that builds this report's real SQL query -- found on the JobBOSS server's Reporting share and read from a local copy, not live on the server), not inferred like everything above:
- `Job_Operation_Time.Rework_Time = 0` is filtered on every query. Rework time entries didn't count toward Act Hours or Adj Hrs here before this was found -- a real gap, now fixed.
- If an employee's summed Run Act Hrs for an operation is 0, JobBOSS forces the reported quantity to 0 too, regardless of what `Act_Run_Qty` itself summed to (`IIF(ARHSum=0, 0, ARQSum)` in the source) -- applied here as part of computing Run Qty, before the bad-data guard above and before Adj Hrs.

The actual Adj E Hrs / % Eff Crystal Reports formula itself is still not recovered. The `.rpt`'s formula definitions are compiled to a proprietary bytecode, not stored as readable text (confirmed by extracting its OLE streams directly: near-uniform byte-value distribution, no plain text, no standard compression) -- reading that back out needs Crystal Reports itself. Capturing JobBOSS's own live query was also not possible (the available SQL login lacks every permission Profiler/Extended Events/Query Store/the plan cache need). The formula above is the ECI-documented one, cross-checked against real data, not read from JobBOSS's source.

**Indirect time is excluded** (vacation, training, cleanup, etc.): both queries join `Work_Center` and filter `Type <> 'Indirect'`, always on, not a checkbox (indirect time counting toward an employee's efficiency is a correctness bug, not an optional view). It's the *work center* that carries this distinction (confirmed directly from this shop's Work Center setup screen -- `Work_Center.Type` is `Direct`/`Indirect`), not the job -- an earlier version of this filter wrongly checked `Job.Type` instead, which has no such value.

**Active Employees Only / grouped quantities**: both always-on for v1, not separate checkboxes -- the Employee picker only ever lists `Employee.Status = 'Active'` rows (itself an unverified assumption, same caveat as `Job.Status` above), and Detail is inherently grouped per (employee, operation) by the query itself. Work Center / Department / Supervisor / Job filters from the real report are not included in v1.

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
