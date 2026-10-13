"""Shared pieces for the three plain job-list reports (Recent Jobs, Jobs by
Customer, Jobs by Date Range): same row shape, same formatter, just a
different query/filter each. Leading underscore -- this isn't a report
itself, just what the others import.
"""

from __future__ import annotations

from typing import Any, Dict, List

SIMPLE_COLUMNS = ('date', 'customer', 'job', 'description', 'status')
SIMPLE_HEADERS = ['Date', 'Customer', 'Job #', 'Description', 'Status']

# Order_Date, not Released_Date -- found by manual testing that Released_Date
# has only been populated for roughly the last year on this schema, so any
# filter/sort built on it silently went empty for older data.
JOB_COLUMNS_SQL = "Job, Customer, Description, Status, Order_Date"


def rows_from_jobs(raw_rows: List[dict]) -> List[Dict[str, Any]]:
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
