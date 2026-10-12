# Experimental Features

This directory contains experimental and work-in-progress features that are **not yet ready for production use**.

## Current Experimental Features

### Database Integration

**Status**: Working against a live JobBOSS SQL Server, scoped to the `Job`, `Delivery`, `Job_Operation`, `Job_Operation_Time`, and `Employee` tables. Still experimental: gated behind the "Enable experimental features (Reporting)" setting, and the exact column names (particularly `Job.Status`/`Employee.Status`) should be confirmed against your own JobBOSS schema the first time you connect -- see "Known gap" below.

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
   ```

   `Delivery`/`Job_Operation` are only needed for Job Report (Promise Date and Current Work Center respectively). `Job_Operation_Time`/`Employee` are only needed for the two Employee Efficiency report types. Every other report type reads `Job` alone.

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

Source tables, confirmed against a full live schema dump (no `Labor_Ticket` table exists on this install, despite that being a more commonly-expected JobBOSS table name): `Job_Operation_Time` (one row per employee per job-operation per `Work_Date` -- the actual hours/qty an employee logged) joined to `Job_Operation` (the operation's own estimate hours: `Est_Setup_Hrs`, `Est_Run_Hrs`) and `Employee` (name/status). Both queries group by `(Employee, Job_Operation)` first before aggregating further, since an employee who worked the same operation across several days has multiple `Job_Operation_Time` rows for it -- grouping first avoids multiply-counting that operation's fixed estimate hours.

**Still not shown: "Adj E Hrs"**, the column feeding the real JobBOSS report's "% Eff" (`Adj E Hrs / Act Hrs * 100`, per that report's own PDF footnote). Neither `Job_Operation` nor `Job_Operation_Time` has any column literally named `Adj_E_Hrs` -- confirmed against the schema dump; it's a Crystal-Reports-computed value there, not a stored one here. The best inferred formula (Setup Adj Hrs == `Est_Setup_Hrs`, Run Adj Hrs == `Act_Run_Qty * Est_Run_Per_Part`) is still just an inference. `employee_efficiency.py`'s `_compute_adj_hrs_and_efficiency()` is a documented stub marking where that calculation plugs back in once validated.

**`Est/Act %` is the one %Eff-shaped column shown**: `(Setup Est Hrs + Run Est Hrs) / (Setup Act Hrs + Run Act Hrs) * 100` -- zero new inference, just a ratio of the Hours columns already shown. Won't match the real report wherever actual quantity run differs from the job's original estimated quantity (that's exactly the gap "Adjusted" closes and this doesn't). `Job_Operation.Efficiency_Pct` was also tried (briefly shown as "JobBOSS Eff%") and dropped again -- live-tested against the real server, it came back exactly `100.0` for every employee regardless of how far off their real Est/Act ratio actually ran (0.2% to 140.9% in one real export), the signature of a static scheduling-input default, not a computed value. Confirmed garbage, not just unverified -- don't reintroduce it without new evidence it means something else on a different install.

**Indirect jobs are excluded** (overhead/non-production time -- vacation, training, cleanup, etc. -- charged to a special non-customer job number): both queries join `Job` and filter `Type <> 'Indirect'`, always on, not a checkbox (indirect time counting toward an employee's efficiency is a correctness bug, not an optional view). `'Indirect'` is JobBOSS's standard value for `Job.Type`, not independently confirmed against row data on this install -- if your install uses a different value/convention here, this filter silently does nothing.

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
