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
    # Given one formatted row dict, return the column KEY to highlight red
    # (e.g. 'sched_end'), or None. None (the default) means this report never
    # highlights anything.
    row_highlight: Optional[Callable[[Dict[str, str]], Optional[str]]] = field(default=None)
    # Shown in the exported title block's "Date Range:" line when uses_dates
    # is True but no date filter was actually applied. None means "N/A".
    date_label_when_unset: Optional[str] = None
