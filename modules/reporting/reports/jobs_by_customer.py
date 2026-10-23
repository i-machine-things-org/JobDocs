"""Jobs by Customer -- up to 200 jobs for the selected customer(s)."""

from __future__ import annotations

from typing import Any, Dict, List

from modules.reporting.db_integration import connect, customer_filter_clause
from modules.reporting.reports._common import JOB_COLUMNS_SQL, SIMPLE_COLUMNS, SIMPLE_HEADERS, rows_from_jobs
from modules.reporting.reports.base import ReportDefinition

# See recent_jobs.py's comment on this implicit-concatenation shape -- same
# reason: only the f-string line (JOB_COLUMNS_SQL) needs the nosec; the
# plain-string {customer_clause} placeholder below is filled in later via
# .format(), never an f-string itself, so bandit doesn't flag it.
_JOBS_BY_CUSTOMER_QUERY = (
    f"SELECT TOP 200 {JOB_COLUMNS_SQL}\n"  # nosec B608
    "FROM Job\n"
    "WHERE Order_Date IS NOT NULL AND {customer_clause}\n"
    "ORDER BY Order_Date DESC\n"
)


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    customer_clause, customer_params = customer_filter_clause(filters.get('customers'))
    query = _JOBS_BY_CUSTOMER_QUERY.format(customer_clause=customer_clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, customer_params)
            return rows_from_jobs(cur.fetchall())


JOBS_BY_CUSTOMER = ReportDefinition(
    name="Jobs by Customer",
    columns=SIMPLE_COLUMNS,
    headers=SIMPLE_HEADERS,
    fetch=fetch,
    uses_customer_filter=True,
)
