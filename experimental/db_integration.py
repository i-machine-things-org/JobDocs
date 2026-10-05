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
    "Job Statistics",
    "Jobs by Customer",
    "Jobs by Date Range",
    "Recent Jobs",
    "Top Customers",
)

# Row-per-job reports all select the same columns, matching the report_table's
# fixed Date/Customer/Job #/Description/Status layout (reporting_tab.ui).
_JOB_COLUMNS = "Job, Customer, Description, Status, Released_Date"

_RECENT_JOBS_QUERY = f"""
SELECT TOP 50 {_JOB_COLUMNS}
FROM Job
WHERE Released_Date IS NOT NULL
ORDER BY Released_Date DESC
"""

_JOBS_BY_CUSTOMER_QUERY = f"""
SELECT TOP 200 {_JOB_COLUMNS}
FROM Job
WHERE Released_Date IS NOT NULL AND Customer LIKE %s
ORDER BY Released_Date DESC
"""

_JOBS_BY_DATE_RANGE_QUERY = f"""
SELECT TOP 500 {_JOB_COLUMNS}
FROM Job
WHERE Released_Date BETWEEN %s AND %s
ORDER BY Released_Date DESC
"""

_TOP_CUSTOMERS_QUERY = """
SELECT TOP 10 Customer, COUNT(*) AS Job_Count
FROM Job
WHERE Released_Date IS NOT NULL
GROUP BY Customer
ORDER BY Job_Count DESC
"""

_JOB_COUNT_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Released_Date >= %s"
_JOB_COUNT_ALL_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Released_Date IS NOT NULL"


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
        released = r.get('Released_Date')
        rows.append({
            'date': released.strftime('%Y-%m-%d') if released else '',
            'customer': r.get('Customer') or '',
            'job': r.get('Job') or '',
            'description': r.get('Description') or '',
            'status': r.get('Status') or '',
        })
    return rows


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
            if report_type == "Recent Jobs":
                cur.execute(_RECENT_JOBS_QUERY)
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Jobs by Customer":
                customer = (filters.get('customer') or '').strip()
                like = f"%{customer}%" if customer else "%"
                cur.execute(_JOBS_BY_CUSTOMER_QUERY, (like,))
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Jobs by Date Range":
                start: date = filters['start_date']
                end: date = filters['end_date']
                cur.execute(_JOBS_BY_DATE_RANGE_QUERY, (start, end))
                return _rows_from_jobs(cur.fetchall())

            if report_type == "Top Customers":
                cur.execute(_TOP_CUSTOMERS_QUERY)
                return [
                    {'date': '', 'customer': r['Customer'] or '', 'job': '',
                     'description': 'Job Count', 'status': str(r['Job_Count'])}
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
