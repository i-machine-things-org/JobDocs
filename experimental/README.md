# Experimental Features

This directory contains experimental and work-in-progress features that are **not yet ready for production use**.

## Current Experimental Features

### Database Integration (`db_integration.py`)

**Status**: Working against a live JobBOSS SQL Server, scoped to the `Job` table only. Still experimental: gated behind the "Enable experimental features (Reporting)" setting, and the exact `Job` table column names (particularly `Status`) should be confirmed against your own JobBOSS schema the first time you connect -- see "Known gap" below.

**Purpose**: Lets the Reporting tab pull live job data straight out of JobBOSS over SQL Server (via [`python-tds`](https://pypi.org/project/python-tds/), the same pure-Python TDS client used by the sibling `shop-schedule` project), instead of showing placeholder sample data.

**Connection setup**:

1. Create a read-only SQL login, following the same model as `shop-schedule`:

   ```sql
   CREATE LOGIN jobdocs_reporting_ro WITH PASSWORD = 'choose-a-strong-password';
   USE <your_jobboss_database>;
   CREATE USER jobdocs_reporting_ro FOR LOGIN jobdocs_reporting_ro;
   GRANT SELECT ON dbo.Job TO jobdocs_reporting_ro;
   ```

2. In JobDocs, open **Settings > Advanced Settings**, check **Enable experimental features (Reporting)**, then fill in the JobBOSS DB Host / Port / Database / Username / Password fields. Use the exact `Server` value from your SQL Server ODBC DSN for Host -- for a named instance (e.g. `SMI-APP02\JBSQL`), leave Port blank and it resolves automatically via the SQL Browser service, the same way the ODBC driver does for Excel/Power Query.
3. The password is **not** written to `settings.json`. It's stored in your OS credential store (Windows Credential Manager, macOS Keychain, or Linux Secret Service) via the `keyring` package, under service name `JobDocs`.
4. On the Reporting tab, click **Connect to Database**, then pick a report type and **Generate Report**.

**Known gap**: the `Status` column assumed by every report (`Job.Status`, same single-char convention as `Job_Operation.Status`) hasn't been verified against a real schema from this codebase alone -- confirm it matches your JobBOSS version the first time you connect. Report results currently only cover the `Job` table (no join to operations/work centers, no pricing/cost fields).

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
