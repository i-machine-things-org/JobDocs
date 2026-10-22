"""Shared shape every report type in modules/reporting/reports/ declares once.

Deliberately no PyQt imports here -- this package stays UI-framework-agnostic,
matching experimental/db_integration.py's existing boundary. resize_mode is a
plain string ("stretch"/"interactive"); modules/reporting/module.py is the one
place that translates it to a QHeaderView.ResizeMode value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ReportDefinition:
    """Everything modules/reporting/module.py needs to drive one report type
    generically, without an if/elif branch of its own for it.
    """

    name: str
    columns: Tuple[str, ...]
    headers: List[str]
    fetch: Callable[[Dict[str, Any], Dict[str, Any]], List[Dict[str, str]]]
    resize_mode: str = "stretch"
    uses_dates: bool = False
    # Only meaningful when uses_dates is True. Required (Jobs by Date Range,
    # Employee Efficiency): both dates must be picked, or generate_report()
    # refuses to run. Optional (Top Customers): either both picked (ranged)
    # or both left at "(No Filter)" (all time) -- picking just one is the
    # only rejected combination.
    dates_required: bool = False
    uses_customer_filter: bool = False
    uses_employee_filter: bool = False
    uses_exclude_assemblies: bool = False
    # Row dicts carry a 'department' key, and the UI offers a "By Department"
    # export checkbox: when checked, _export_xlsx() splits the data rows
    # into one worksheet tab per department instead of one combined sheet.
    # Export-only (like footer_lines) -- CSV/PDF have no native multi-tab
    # concept, so they always stay a single flat output regardless of this
    # checkbox; only xlsx actually splits.
    uses_department_tabs: bool = False
    # Column KEYS (subset of `columns`) eligible for the "By Department"
    # export's trailing average row -- restricts _department_average_row()
    # (modules/reporting/module.py) to genuine metric columns (hours, %,
    # qty). An identifier column (job/operation/employee) has no sensible
    # average even when every value in it happens to parse as a number.
    # Empty tuple (the default) passes no restriction down, meaning no
    # average row makes sense to compute -- only meaningful alongside
    # uses_department_tabs.
    average_columns: Tuple[str, ...] = ()
    # xlsx export only (like average_columns): insert an "<Employee> Total"
    # row plus a blank spacer row after each employee's consecutive block of
    # rows, matching JobBOSS's own native Detail report layout (one row per
    # operation, grouped into per-employee blocks each closed out by a total
    # line). Relies on `fetch`'s own SQL already ordering rows so one
    # employee's rows are contiguous -- this does not re-sort. Because the
    # inserted rows break the uniform shape an Excel Table/AutoFilter range
    # requires, a report with this on does not get wrapped in a Table.
    uses_employee_total_rows: bool = False
    # Given one formatted row dict, return the column KEY to highlight red
    # (e.g. 'sched_end'), or None. None (the default) means this report never
    # highlights anything.
    row_highlight: Optional[Callable[[Dict[str, str]], Optional[str]]] = field(default=None)
    # Shown in the exported title block's "Date Range:" line when uses_dates
    # is True but no date filter was actually applied. None means "N/A".
    date_label_when_unset: Optional[str] = None
    # Plain-text lines appended after the data rows in CSV/xlsx exports (one
    # row per line, first column only) -- e.g. Employee Efficiency's formula
    # summary. None (the default) means no footer. Export-only, not shown in
    # the on-screen report_table.
    footer_lines: Optional[List[str]] = None
