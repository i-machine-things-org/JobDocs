"""
JobBOSS SQL Server access for the Reporting module (experimental).

Mirrors the connection technique already proven in the sibling shop-schedule
project's jobboss_db.py: pytds (pure-Python TDS client, no ODBC driver to
install), named-instance port resolution via the SQL Browser service, and a
SELECT-only query against the Job table -- pair this with a SQL login that
has SELECT-only grants on Job, nothing broader. See README.md in this
directory for the recommended login setup.

Unlike shop-schedule (one device, one gitignored .env), JobDocs is installed
by many different users against their own JobBOSS server, so connection
settings come from the Settings dialog instead of environment variables.
Non-secret fields (host/port/database/username) live in the regular app
settings dict; the password is never written to settings.json -- it's stored
in the OS credential store via `keyring`.

Copyright (c) 2025 JobDocs Contributors
Licensed under the GNU General Public License v3.0 - see LICENSE file for details
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import keyring
import keyring.errors
import pytds

KEYRING_SERVICE = 'JobDocs'

REPORT_TYPES = (
    "Job Report",
    "Job Statistics",
    "Jobs by Customer",
    "Jobs by Date Range",
    "Recent Jobs",
    "Top Customers",
)

# Row-per-job reports all select the same columns, matching the report_table's
# fixed Date/Customer/Job #/Description/Status layout (reporting_tab.ui).
# Order_Date, not Released_Date -- found by manual testing that Released_Date
# has only been populated for roughly the last year on this schema, so any
# filter/sort built on it silently went empty for older data.
_JOB_COLUMNS = "Job, Customer, Description, Status, Order_Date"

_RECENT_JOBS_QUERY = f"""
SELECT TOP 50 {_JOB_COLUMNS}
FROM Job
WHERE Order_Date IS NOT NULL
ORDER BY Order_Date DESC
"""

_JOBS_BY_CUSTOMER_QUERY = f"""
SELECT TOP 200 {_JOB_COLUMNS}
FROM Job
WHERE Order_Date IS NOT NULL AND {{customer_clause}}
ORDER BY Order_Date DESC
"""

_JOBS_BY_DATE_RANGE_QUERY = f"""
SELECT TOP 500 {_JOB_COLUMNS}
FROM Job
WHERE Order_Date BETWEEN %s AND %s
ORDER BY Order_Date DESC
"""

_TOP_CUSTOMERS_QUERY = """
SELECT TOP 10 Customer, COUNT(*) AS Job_Count, SUM(Total_Price) AS Gross_Revenue
FROM Job
WHERE Order_Date IS NOT NULL
GROUP BY Customer
ORDER BY Gross_Revenue DESC
"""

_TOP_CUSTOMERS_QUERY_RANGED = """
SELECT TOP 10 Customer, COUNT(*) AS Job_Count, SUM(Total_Price) AS Gross_Revenue
FROM Job
WHERE Order_Date BETWEEN %s AND %s
GROUP BY Customer
ORDER BY Gross_Revenue DESC
"""

_JOB_COUNT_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Order_Date >= %s"
_JOB_COUNT_ALL_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Order_Date IS NOT NULL"

_DISTINCT_CUSTOMERS_QUERY = """
SELECT DISTINCT Customer
FROM Job
WHERE Customer IS NOT NULL AND Customer <> ''
ORDER BY Customer
"""

# Mirrors JobBOSS's own canned "Job Report" (jobRpt) export: one row per open
# job with PO/line/drawing/promise-date detail, not just the narrow
# Date/Customer/Job/Description/Status set the other report types share.
#
# Customer_PO/Customer_PO_LN (not SO_Detail.PO/Line) are the real source for
# PO Number/Line on this schema -- confirmed against production data that
# SO_Detail is entirely unused (0 rows) at this install, while Customer_PO is
# populated on ~93% of jobs. Likewise Rev (not Revision, which is always
# blank here) is the actually-populated revision field.
#
# There's no column anywhere in this schema that corresponds to the sample
# report's "Classification" field -- left blank in _rows_from_job_report
# rather than guessed.
#
# Assembly_Level=0 means a standalone/top-level job (Top_Lvl_Job == Job);
# Assembly_Level>0 is a sub-component under a parent assembly job (e.g.
# "30274A" under parent "30274", Top_Lvl_Job='30274') -- confirmed against
# production data, including that the sub-component's own Type is often
# 'Regular' (not 'Assembly'), so Type can't be used for this filter, only
# Assembly_Level/Top_Lvl_Job. Optionally excluded via filters['exclude_assemblies'].
_JOB_REPORT_COLUMNS = (
    "Job, Customer, Customer_PO, Customer_PO_LN, Drawing, Part_Number, Rev, "
    "Description, Order_Date, Order_Quantity, Sched_End, Status, Note_Text"
)

# OUTER APPLY, not CROSS APPLY: unlike shop-schedule's current-operation lookup
# (every open job has at least one non-complete Job_Operation row by
# definition), a job can have zero Delivery rows -- OUTER APPLY keeps that job
# in the report with a blank Promise Date instead of silently dropping it.
# When a job has multiple Delivery rows (partial shipments), the soonest still-
# open one (Remaining_Quantity > 0) is used as "the" promise date; if every
# delivery on the job has already fully shipped, falls back to the soonest by
# date so a fully-shipped-but-still-Active job still shows something.
_JOB_REPORT_QUERY = f"""
SELECT TOP 500 {_JOB_REPORT_COLUMNS}, dlv.Promised_Date
FROM Job j
OUTER APPLY (
    SELECT TOP 1 d.Promised_Date
    FROM Delivery d
    WHERE d.Job = j.Job
    ORDER BY CASE WHEN d.Remaining_Quantity > 0 THEN 0 ELSE 1 END, d.Promised_Date ASC
) dlv
WHERE Status = 'Active' AND {{customer_clause}} AND {{assembly_clause}}
ORDER BY Customer, Sched_End
"""


def _customer_filter_clause(customers: Optional[List[str]]) -> "tuple[str, tuple]":
    """Build a 'Customer IN (...)' clause plus its matching parameter tuple
    for however many customers are selected (0 = no filter -- every job/row,
    not zero of them; 1 or many both use the same IN-list shape).
    """
    names = [c for c in (customers or []) if c]
    if not names:
        return "1=1", ()
    placeholders = ", ".join(["%s"] * len(names))
    return f"Customer IN ({placeholders})", tuple(names)


def _keyring_key(username: str) -> str:
    return f"jobboss_db:{username}"


def set_password(username: str, password: str) -> None:
    """Store the JobBOSS DB password in the OS credential store."""
    keyring.set_password(KEYRING_SERVICE, _keyring_key(username), password)


def get_password(username: str) -> Optional[str]:
    """Look up the stored JobBOSS DB password; None if unset or the backend is unavailable."""
    if not username:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, _keyring_key(username))
    except keyring.errors.KeyringError:
        return None


def is_configured(settings: Dict[str, Any]) -> bool:
    """True if enough settings + a stored password are present to attempt a connection."""
    host = (settings.get('jobboss_db_host') or '').strip()
    name = (settings.get('jobboss_db_name') or '').strip()
    user = (settings.get('jobboss_db_user') or '').strip()
    return bool(host and name and user and get_password(user))


def _connect_kwargs(settings: Dict[str, Any]):
    """Build the (dsn, connect_kwargs) pair for pytds.connect(), matching
    jobboss_db.py's named-instance resolution: a bare host/named-instance
    string lets pytds resolve the real port via the SQL Browser service;
    only split off an explicit port if one was actually configured.
    """
    host = (settings.get('jobboss_db_host') or '').strip()
    name = (settings.get('jobboss_db_name') or '').strip()
    user = (settings.get('jobboss_db_user') or '').strip()
    port_raw = str(settings.get('jobboss_db_port') or '').strip()

    dsn = host
    connect_kwargs: Dict[str, Any] = {
        'database': name, 'user': user, 'password': get_password(user),
        'timeout': 15, 'as_dict': True,
    }
    if port_raw:
        dsn = host.split('\\', 1)[0]
        connect_kwargs['port'] = int(port_raw)
    return dsn, connect_kwargs


def test_connection(settings: Dict[str, Any]) -> tuple[bool, str]:
    """Open and immediately close a connection to confirm the configured
    settings actually reach the JobBOSS SQL Server.
    """
    if not is_configured(settings):
        return False, "Not configured -- set the JobBOSS DB connection in Settings > Advanced Settings."
    dsn, connect_kwargs = _connect_kwargs(settings)
    try:
        with pytds.connect(dsn, **connect_kwargs):
            pass
    except Exception as exc:
        # Only the exception type, never str(exc) -- the TDS driver's error text
        # can echo back connection parameters.
        return False, f"Connection failed ({type(exc).__name__})"
    return True, "Connected"


def _rows_from_jobs(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        order_date = r.get('Order_Date')
        rows.append({
            'date': order_date.strftime('%Y-%m-%d') if order_date else '',
            'customer': r.get('Customer') or '',
            'job': r.get('Job') or '',
            'description': r.get('Description') or '',
            'status': r.get('Status') or '',
        })
    return rows


def _rows_from_job_report(raw_rows: List[dict]) -> List[Dict[str, str]]:
    rows = []
    for r in raw_rows:
        order_date = r.get('Order_Date')
        sched_end = r.get('Sched_End')
        promised = r.get('Promised_Date')
        rows.append({
            # No column in this schema corresponds to the sample report's
            # "Classification" field -- see _JOB_REPORT_QUERY.
            'classification': '',
            'job': r.get('Job') or '',
            'customer': r.get('Customer') or '',
            'po': r.get('Customer_PO') or '',
            'line': r.get('Customer_PO_LN') or '',
            'drawing': r.get('Drawing') or '',
            'part_number': r.get('Part_Number') or '',
            'revision': r.get('Rev') or '',
            'description': r.get('Description') or '',
            'order_date': order_date.strftime('%Y-%m-%d') if order_date else '',
            'order_qty': str(r['Order_Quantity']) if r.get('Order_Quantity') is not None else '',
            'sched_end': sched_end.strftime('%Y-%m-%d') if sched_end else '',
            'promise_date': promised.strftime('%Y-%m-%d') if promised else '',
            'status': r.get('Status') or '',
            'notes': (r.get('Note_Text') or '').strip(),
        })
    return rows


def fetch_customers(settings: Dict[str, Any]) -> List[str]:
    """Distinct customer names from Job, for populating the Customer filter combo."""
    if not is_configured(settings):
        raise RuntimeError("JobBOSS DB is not configured")
    dsn, connect_kwargs = _connect_kwargs(settings)
    with pytds.connect(dsn, **connect_kwargs) as conn:
        with conn.cursor() as cur:
            cur.execute(_DISTINCT_CUSTOMERS_QUERY)
            return [r['Customer'] for r in cur.fetchall() if r.get('Customer')]


def fetch_report(settings: Dict[str, Any], report_type: str,
                  filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Run the query for `report_type` and return rows shaped for report_table
    (date, customer, job, description, status keys), regardless of whether the
    underlying query is row-per-job or an aggregate.
    """
    if not is_configured(settings):
        raise RuntimeError("JobBOSS DB is not configured")
    filters = filters or {}
    dsn, connect_kwargs = _connect_kwargs(settings)

    with pytds.connect(dsn, **connect_kwargs) as conn:
        with conn.cursor() as cur:
            if report_type == "Job Report":
                customer_clause, customer_params = _customer_filter_clause(filters.get('customers'))
                assembly_clause = "Assembly_Level = 0" if filters.get('exclude_assemblies') else "1=1"
                query = _JOB_REPORT_QUERY.format(customer_clause=customer_clause, assembly_clause=assembly_clause)
                cur.execute(query, customer_params)
                return _rows_from_job_report(cur.fetchall())

            if report_type == "Recent Jobs":
                cur.execute(_RECENT_JOBS_QUERY)
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Jobs by Customer":
                customer_clause, customer_params = _customer_filter_clause(filters.get('customers'))
                query = _JOBS_BY_CUSTOMER_QUERY.format(customer_clause=customer_clause)
                cur.execute(query, customer_params)
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Jobs by Date Range":
                start: date = filters['start_date']
                end: date = filters['end_date']
                cur.execute(_JOBS_BY_DATE_RANGE_QUERY, (start, end))
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Top Customers":
                start = filters.get('start_date')
                end = filters.get('end_date')
                if start and end:
                    cur.execute(_TOP_CUSTOMERS_QUERY_RANGED, (start, end))
                else:
                    cur.execute(_TOP_CUSTOMERS_QUERY)
                return [
                    {'date': '', 'customer': r['Customer'] or '',
                     'job': str(r['Job_Count']), 'description': '',
                     'status': f"${r['Gross_Revenue']:,.2f}" if r['Gross_Revenue'] is not None else '$0.00'}
                    for r in cur.fetchall()
                ]

            if report_type == "Job Statistics":
                today = datetime.now().date()
                month_start = today.replace(day=1)
                week_start = today - timedelta(days=today.weekday())

                cur.execute(_JOB_COUNT_ALL_QUERY)
                total = cur.fetchone()['Job_Count']
                cur.execute(_JOB_COUNT_QUERY, (month_start,))
                this_month = cur.fetchone()['Job_Count']
                cur.execute(_JOB_COUNT_QUERY, (week_start,))
                this_week = cur.fetchone()['Job_Count']

                return [
                    {'date': '', 'customer': '', 'job': '', 'description': 'Total Jobs', 'status': str(total)},
                    {'date': '', 'customer': '', 'job': '', 'description': 'Jobs This Month', 'status': str(this_month)},
                    {'date': '', 'customer': '', 'job': '', 'description': 'Jobs This Week', 'status': str(this_week)},
                ]

            raise ValueError(f"Unknown report type: {report_type!r}")
