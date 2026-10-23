"""Job Report -- matches the shape of this shop's existing "Job Report"
(jobRpt) -- a custom report, not something JobBOSS ships built-in -- one row
per open job with PO/line/drawing/promise-date detail, not just the narrow
Date/Customer/Job/Description/Status set the other report types share.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.reporting.db_integration import connect, customer_filter_clause
from modules.reporting.reports.base import ReportDefinition

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
_JOB_REPORT_COLUMNS_SQL = (
    "Job, Customer, Customer_PO, Customer_PO_LN, Drawing, Part_Number, Rev, "
    "Description, Order_Date, Order_Quantity, Sched_End, Status, Note_Text"
)

COLUMNS = (
    'classification', 'job', 'customer', 'po', 'line', 'drawing', 'part_number',
    'revision', 'description', 'order_date', 'order_qty', 'sched_end',
    'promise_date', 'status', 'curr_wc', 'notes',
)
HEADERS = [
    'Classification', 'Job ID', 'Customer ID', 'Customer PO Number', 'Line',
    'Drawing', 'Part Number', 'Revision', 'Description', 'Order Date',
    'Order Qty', 'Scheduled End Date', 'Promise Date', 'Status',
    'Current Work Center', 'Notes',
]

# OUTER APPLY, not CROSS APPLY: unlike shop-schedule's current-operation lookup
# (every open job has at least one non-complete Job_Operation row by
# definition, since that query starts FROM Job_Operation itself), Job Report
# starts FROM Job with no Job_Operation filter at all -- a Job in 'Active'
# status isn't guaranteed to have a non-complete Job_Operation row (not yet
# routed, or operations closed out of sync with the job header). CROSS APPLY
# would silently drop such a job from the report entirely; OUTER APPLY keeps
# it with a blank Current Work Center instead. Same reasoning as the Delivery
# lookup below. When a job has multiple Delivery rows (partial shipments),
# the soonest still-open one (Remaining_Quantity > 0) is used as "the"
# promise date; if every delivery on the job has already fully shipped,
# falls back to the soonest by date so a fully-shipped-but-still-Active job
# still shows something.
#
# Current Work Center = the work center of the earliest non-complete
# operation (by Sequence) -- the exact "current operation per job" logic
# already proven live in shop-schedule/jobboss_db.py's CROSS APPLY, reused
# here verbatim (Job_Operation.Work_Center/.Sequence/.Status), just OUTER
# instead of CROSS for the reason above.
_JOB_REPORT_QUERY = (
    f"SELECT TOP 500 {_JOB_REPORT_COLUMNS_SQL}, dlv.Promised_Date, cur.Curr_WC\n"  # nosec B608
    "FROM Job j\n"
    "OUTER APPLY (\n"
    "    SELECT TOP 1 d.Promised_Date\n"
    "    FROM Delivery d\n"
    "    WHERE d.Job = j.Job\n"
    "    ORDER BY CASE WHEN d.Remaining_Quantity > 0 THEN 0 ELSE 1 END, d.Promised_Date ASC\n"
    ") dlv\n"
    "OUTER APPLY (\n"
    "    SELECT TOP 1 jo.Work_Center AS Curr_WC\n"
    "    FROM Job_Operation jo\n"
    "    WHERE jo.Job = j.Job AND jo.Status <> 'C'\n"
    "    ORDER BY jo.Sequence ASC\n"
    ") cur\n"
    "WHERE Status = 'Active' AND {customer_clause} AND {assembly_clause}\n"
    "ORDER BY Customer, Sched_End\n"
)


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
            'curr_wc': r.get('Curr_WC') or '',
            'notes': (r.get('Note_Text') or '').strip(),
        })
    return rows


def _is_past_promise(sched_end: str, promise_date: str) -> bool:
    """True if Scheduled End Date is later than Promise Date. Both are
    'YYYY-MM-DD' strings (or '' if blank) from _rows_from_job_report, so a
    plain string comparison already sorts correctly -- no need to re-parse
    into date objects. Either side blank means nothing to compare -> False.
    """
    return bool(sched_end and promise_date and sched_end > promise_date)


def _row_highlight(row: Dict[str, str]) -> Optional[str]:
    """Which column key to flag red, or None. Only the generic reader in
    modules/reporting/module.py calls this -- it has no idea what Job Report
    specifically checks, just that this report says "highlight 'sched_end'
    on this row" or "don't."
    """
    if _is_past_promise(row.get('sched_end', ''), row.get('promise_date', '')):
        return 'sched_end'
    return None


def fetch(settings: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, str]]:
    clause, customer_params = customer_filter_clause(filters.get('customers'))
    assembly_clause = "Assembly_Level = 0" if filters.get('exclude_assemblies') else "1=1"
    query = _JOB_REPORT_QUERY.format(customer_clause=clause, assembly_clause=assembly_clause)
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(query, customer_params)
            return _rows_from_job_report(cur.fetchall())


JOB_REPORT = ReportDefinition(
    name="Job Report",
    columns=COLUMNS,
    headers=HEADERS,
    fetch=fetch,
    resize_mode="interactive",
    uses_customer_filter=True,
    uses_exclude_assemblies=True,
    row_highlight=_row_highlight,
)
