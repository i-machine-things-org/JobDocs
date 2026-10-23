"""Recent Jobs -- the 50 most recently ordered jobs, no filters."""

from __future__ import annotations

from typing import Any, Dict, List

from modules.reporting.db_integration import connect
from modules.reporting.reports._common import JOB_COLUMNS_SQL, SIMPLE_COLUMNS, SIMPLE_HEADERS, rows_from_jobs
from modules.reporting.reports.base import ReportDefinition

# Built as implicit-concatenated string literals, one f-string line (just
# JOB_COLUMNS_SQL, a hardcoded module constant) followed by plain-string
# continuation lines -- bandit's B608 check flags any f-string that looks
# like a formatted SQL statement, with no data-flow analysis to see what was
# interpolated; this shape puts the one f-string line under a suppression
# comment scoped to just that line, while the plain-string lines (no
# f-prefix, nothing formatted into them) don't trigger the check at all.
_RECENT_JOBS_QUERY = (
    f"SELECT TOP 50 {JOB_COLUMNS_SQL}\n"  # nosec B608
    "FROM Job\n"
    "WHERE Order_Date IS NOT NULL\n"
    "ORDER BY Order_Date DESC\n"
)


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_RECENT_JOBS_QUERY)
            return rows_from_jobs(cur.fetchall())


RECENT_JOBS = ReportDefinition(
    name="Recent Jobs",
    columns=SIMPLE_COLUMNS,
    headers=SIMPLE_HEADERS,
    fetch=fetch,
)
