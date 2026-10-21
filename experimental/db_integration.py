"""
JobBOSS SQL Server access for the Reporting module (experimental).

Mirrors the connection technique already proven in the sibling shop-schedule
project's jobboss_db.py: pytds (pure-Python TDS client, no ODBC driver to
install), named-instance port resolution via the SQL Browser service, and
SELECT-only queries -- pair this with a SQL login that has SELECT-only
grants, nothing broader. See README.md in this directory for the
recommended login setup.

Unlike shop-schedule (one device, one gitignored .env), JobDocs is installed
by many different users against their own JobBOSS server, so connection
settings come from the Settings dialog instead of environment variables.
Non-secret fields (host/port/database/username) live in the regular app
settings dict; the password is never written to settings.json -- it's stored
in the OS credential store via `keyring`.

This module is shared infrastructure only (credentials, connection, and
filter-input lookups reused by more than one report type) -- every
report-specific query, row-formatter, and display column/header set lives
in modules/reporting/reports/ instead, one file per report type. See that
package's __init__.py for the registry.

Copyright (c) 2025 JobDocs Contributors
Licensed under the GNU General Public License v3.0 - see LICENSE file for details
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import keyring
import keyring.errors
import pytds

KEYRING_SERVICE = 'JobDocs'

_DISTINCT_CUSTOMERS_QUERY = """
SELECT DISTINCT Customer
FROM Job
WHERE Customer IS NOT NULL AND Customer <> ''
ORDER BY Customer
"""

_ACTIVE_EMPLOYEES_QUERY = """
SELECT Employee, First_Name, Last_Name
FROM Employee
WHERE Status = 'Active'
ORDER BY Last_Name, First_Name
"""


def customer_filter_clause(customers: Optional[List[str]]) -> "tuple[str, tuple]":
    """Build a 'Customer IN (...)' clause plus its matching parameter tuple
    for however many customers are selected (0 = no filter -- every job/row,
    not zero of them; 1 or many both use the same IN-list shape).
    """
    names = [c for c in (customers or []) if c]
    if not names:
        return "1=1", ()
    placeholders = ", ".join(["%s"] * len(names))
    return f"Customer IN ({placeholders})", tuple(names)


def employee_filter_clause(employees: Optional[List[str]], column: str) -> "tuple[str, tuple]":
    """Build a '<column> IN (...)' clause plus its matching parameter tuple
    for however many employees are selected (0 = no filter -- every active
    employee). Unlike customer_filter_clause's single-table (Job) queries,
    the Employee Efficiency queries join multiple tables that could all
    plausibly carry an Employee column, so the caller passes the exact
    aliased column to disambiguate (e.g. 'jot.Employee').
    """
    codes = [e for e in (employees or []) if e]
    if not codes:
        return "1=1", ()
    placeholders = ", ".join(["%s"] * len(codes))
    return f"{column} IN ({placeholders})", tuple(codes)


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


@contextmanager
def connect(settings: Dict[str, Any]):
    """Open a pytds connection from the configured settings. Thin wrapper
    around pytds.connect(*_connect_kwargs(...)) so every report file in
    modules/reporting/reports/ shares one place for connection setup instead
    of repeating it.
    """
    dsn, connect_kwargs = _connect_kwargs(settings)
    with pytds.connect(dsn, **connect_kwargs) as conn:
        yield conn


def test_connection(settings: Dict[str, Any]) -> tuple[bool, str]:
    """Open and immediately close a connection to confirm the configured
    settings actually reach the JobBOSS SQL Server.
    """
    if not is_configured(settings):
        return False, "Not configured -- set the JobBOSS DB connection in Settings > Advanced Settings."
    try:
        dsn, connect_kwargs = _connect_kwargs(settings)
    except ValueError:
        # int(port_raw) in _connect_kwargs raises on a non-numeric Port (e.g. a
        # stray space, "auto" typed literally, "1433,1434"). _ConnectWorker.run()
        # has no try of its own -- it trusts this function to always return a
        # (bool, str) tuple rather than raise, so an uncaught exception here
        # would leave finished_ok never emitted and the tab's db_status_
        # indicator stuck showing "Connecting..." forever instead of
        # showing a clear error.
        return False, "Invalid port -- enter a number or leave Port blank."
    try:
        with pytds.connect(dsn, **connect_kwargs):
            pass
    except Exception as exc:
        # Only the exception type, never str(exc) -- the TDS driver's error text
        # can echo back connection parameters.
        return False, f"Connection failed ({type(exc).__name__})"
    return True, "Connected"


def fetch_customers(settings: Dict[str, Any]) -> List[str]:
    """Distinct customer names from Job, for populating the Customer filter combo."""
    if not is_configured(settings):
        raise RuntimeError("JobBOSS DB is not configured")
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_DISTINCT_CUSTOMERS_QUERY)
            return [r['Customer'] for r in cur.fetchall() if r.get('Customer')]


def fetch_employees(settings: Dict[str, Any]) -> List[Dict[str, str]]:
    """Active employees (code + display name), for populating the Employee
    filter picker on the two Employee Efficiency report types.

    Status = 'Active' confirmed live (not just by convention) against the
    real JobBOSS Employee Efficiency export: this schema has exactly 26
    'Active' employees and 215 'Inactive', no ambiguous third status, and
    26 is exactly the number of employee blocks in JobBOSS's own real
    export. A different schema could still use something else here, in
    which case the picker comes back empty -- an obviously-broken,
    easy-to-report state rather than a silently-wrong one.
    """
    if not is_configured(settings):
        raise RuntimeError("JobBOSS DB is not configured")
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_ACTIVE_EMPLOYEES_QUERY)
            return [
                {
                    'code': r['Employee'],
                    'name': f"{r.get('First_Name') or ''} {r.get('Last_Name') or ''}".strip() or r['Employee'],
                }
                for r in cur.fetchall()
            ]
