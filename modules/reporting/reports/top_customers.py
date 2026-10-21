"""Top Customers -- top 10 by gross revenue, optionally ranged by Order_Date.

Unlike Jobs by Date Range, the date range here is optional: no dates picked
means "all time," not an error.
"""

from __future__ import annotations

from typing import Any, Dict, List

from experimental.db_integration import connect
from modules.reporting.reports._common import SIMPLE_COLUMNS
from modules.reporting.reports.base import ReportDefinition

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

# Repurposes the shared 5-column shape: 'job' holds the job count, 'status'
# holds the formatted revenue -- hence the blank header labels for the
# columns ('customer'/'description') this report doesn't use.
HEADERS = ['', 'Customer', 'Job Count', '', 'Gross Revenue']


def _rows_from_top_customers(raw_rows: List[dict]) -> List[Dict[str, str]]:
    return [
        {'date': '', 'customer': r['Customer'] or '',
         'job': str(r['Job_Count']), 'description': '',
         'status': f"${r['Gross_Revenue']:,.2f}" if r['Gross_Revenue'] is not None else '$0.00'}
        for r in raw_rows
    ]


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    start = filters.get('start_date')
    end = filters.get('end_date')
    with connect(settings) as conn:
        with conn.cursor() as cur:
            if start and end:
                cur.execute(_TOP_CUSTOMERS_QUERY_RANGED, (start, end))
            else:
                cur.execute(_TOP_CUSTOMERS_QUERY)
            return _rows_from_top_customers(cur.fetchall())


TOP_CUSTOMERS = ReportDefinition(
    name="Top Customers",
    columns=SIMPLE_COLUMNS,
    headers=HEADERS,
    fetch=fetch,
    uses_dates=True,
    dates_required=False,
    date_label_when_unset="All Time",
)
