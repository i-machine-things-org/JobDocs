"""Job Statistics -- three quick counts: total, this month, this week."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from experimental.db_integration import connect
from modules.reporting.reports._common import SIMPLE_COLUMNS
from modules.reporting.reports.base import ReportDefinition

_JOB_COUNT_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Order_Date >= %s"
_JOB_COUNT_ALL_QUERY = "SELECT COUNT(*) AS Job_Count FROM Job WHERE Order_Date IS NOT NULL"

# Repurposes the shared 5-column shape: 'description'/'status' hold the
# metric name/value, hence the blank header labels for the unused columns.
HEADERS = ['', '', '', 'Metric', 'Value']


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    today = datetime.now().date()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=today.weekday())

    with connect(settings) as conn:
        with conn.cursor() as cur:
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


JOB_STATISTICS = ReportDefinition(
    name="Job Statistics",
    columns=SIMPLE_COLUMNS,
    headers=HEADERS,
    fetch=fetch,
)
