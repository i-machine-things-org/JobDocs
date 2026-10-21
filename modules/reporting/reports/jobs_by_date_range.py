"""Jobs by Date Range -- up to 500 jobs ordered within the picked range (mandatory)."""

from __future__ import annotations

from typing import Any, Dict, List

from experimental.db_integration import connect
from modules.reporting.reports._common import JOB_COLUMNS_SQL, SIMPLE_COLUMNS, SIMPLE_HEADERS, rows_from_jobs
from modules.reporting.reports.base import ReportDefinition

_JOBS_BY_DATE_RANGE_QUERY = (
    f"SELECT TOP 500 {JOB_COLUMNS_SQL}\n"  # nosec B608
    "FROM Job\n"
    "WHERE Order_Date BETWEEN %s AND %s\n"
    "ORDER BY Order_Date DESC\n"
)


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters['start_date']
    end = filters['end_date']
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_JOBS_BY_DATE_RANGE_QUERY, (start, end))
            return rows_from_jobs(cur.fetchall())


JOBS_BY_DATE_RANGE = ReportDefinition(
    name="Jobs by Date Range",
    columns=SIMPLE_COLUMNS,
    headers=SIMPLE_HEADERS,
    fetch=fetch,
    uses_dates=True,
    dates_required=True,
)
