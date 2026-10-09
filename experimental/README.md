# Experimental Features

This directory contains experimental and work-in-progress features that are **not yet ready for production use**.

## Current Experimental Features

### Database Integration (`db_integration.py`)

**Status**: Working against a live JobBOSS SQL Server, scoped to the `Job` and `Delivery` tables. Still experimental: gated behind the "Enable experimental features (Reporting)" setting, and the exact column names (particularly `Job.Status`) should be confirmed against your own JobBOSS schema the first time you connect -- see "Known gap" below.

**Purpose**: Lets the Reporting tab pull live job data straight out of JobBOSS over SQL Server (via [`python-tds`](https://pypi.org/project/python-tds/), the same pure-Python TDS client used by the sibling `shop-schedule` project), instead of showing placeholder sample data.

**Connection setup**:

1. Create a read-only SQL login, following the same model as `shop-schedule`:

   ```sql
   CREATE LOGIN jobdocs_reporting_ro WITH PASSWORD = 'choose-a-strong-password';
   USE <your_jobboss_database>;
   CREATE USER jobdocs_reporting_ro FOR LOGIN jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Job TO jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Delivery TO jobdocs_reporting_ro;
   ```

   The `Delivery` grant is only needed for the **Job Report** report type (it
   looks up each job's Promise Date there); every other report type reads
   `Job` alone.

2. In JobDocs, open **Settings > Advanced Settings**, check **Enable experimental features (Reporting)**, then fill in the JobBOSS DB Host / Port / Database / Username / Password fields. Use the exact `Server` value from your SQL Server ODBC DSN for Host -- for a named instance (e.g. `SMI-APP02\JBSQL`), leave Port blank and it resolves automatically via the SQL Browser service, the same way the ODBC driver does for Excel/Power Query.
3. The password is **not** written to `settings.json`. It's stored in your OS credential store (Windows Credential Manager, macOS Keychain, or Linux Secret Service) via the `keyring` package, under service name `JobDocs`.
4. On the Reporting tab, click **Connect to Database**, then pick a report type and **Generate Report**.

**Customer filter**: for "Jobs by Customer" and "Job Report", the Customer button opens a checklist picker -- pick zero (All Customers), one, or several at once. "Job Report" also has an "Exclude assembly sub-jobs" checkbox (filters on `Assembly_Level = 0`, i.e. `Top_Lvl_Job == Job`) to drop component jobs like "30274A" under a parent "30274" from the results.

**Exported files are real Excel Tables**: the `.xlsx` export wraps the header + data rows in an Excel Table with its AutoFilter, so every column is sortable/filterable as soon as the file opens in Excel -- not a plain value dump.

**Date field**: every report filters/sorts on `Job.Order_Date`, not `Released_Date` -- found by manual testing that `Released_Date` is only populated for roughly the last year on this schema, which made every date-based report silently come back empty for anything older. If your schema's history lives on yet another field, swap `_JOB_COLUMNS` and the query constants in `db_integration.py` (all in one place).

**Known gap**: the `Status` column assumed by every report (`Job.Status`, same single-char convention as `Job_Operation.Status`), and `Total_Price` (summed per customer for Top Customers' "Gross Revenue") have not been verified against a real schema from this codebase alone -- confirm both match your JobBOSS version the first time you connect. Everything except Job Report covers the `Job` table alone (no join to operations/work centers).

**Job Report field mapping**: mirrors JobBOSS's own canned "Job Report" export (one row per open job: PO, line, drawing, revision, promise date). Confirmed against a real schema that `Job.Customer_PO`/`Customer_PO_LN` (not `SO_Detail.PO`/`Line` -- `SO_Detail` was entirely unused, 0 rows, on the schema this was built against) are the real PO/Line source, and `Job.Rev` (not `Job.Revision`, always blank there) is the populated revision field -- if your install actually uses JobBOSS's Sales Order module, you may want `SO_Detail` instead. There is no column anywhere in that schema corresponding to the sample report's "Classification" field; it's left blank rather than guessed -- fill it in from wherever that lives on your install, if anywhere.

**Gross Revenue grants**: Top Customers sums `Total_Price`, so the read-only login above also needs to be able to read that column -- `GRANT SELECT ON dbo.Job` already covers it (SQL Server grants apply to the whole table), but if your DBA prefers column-level grants instead, include `Total_Price` explicitly. This is the one report that exposes dollar figures; the rest only show job/customer/schedule metadata.

**Known limitation -- unencrypted transport by default**: like `shop-schedule`, `pytds` doesn't encrypt the connection unless given a CA certificate, which isn't wired up here yet. This matches the same trust model as existing ODBC/Excel access to the same server; not a new exposure, but worth closing later if someone wants to add `JOBBOSS_DB_CAFILE`-style TLS support (see `shop-schedule/README.md` for the pattern).

**Not Recommended For**:
- A different ERP/database (only JobBOSS/MSSQL via `pytds` is implemented)
- Any write-back to JobBOSS (every query is SELECT-only, matching the login's grants)

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
