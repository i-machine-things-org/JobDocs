"""Structural checks on modules/reporting/reports' registry -- pure Python,
no DB/QApplication needed. Doesn't check any one report's query/formatting
logic (see tests/test_report_*.py for that); just that every ReportDefinition
is internally consistent enough for modules/reporting/module.py's generic
glue to use it safely.
"""

from modules.reporting.reports import REPORT_TYPES, REPORTS


def test_report_types_matches_registry_keys():
    assert REPORT_TYPES == tuple(REPORTS)


def test_every_report_has_matching_columns_and_headers_length():
    for name, report in REPORTS.items():
        assert len(report.columns) == len(report.headers), (
            f"{name}: {len(report.columns)} columns but {len(report.headers)} headers"
        )


def test_every_report_name_is_unique():
    names = [r.name for r in REPORTS.values()]
    assert len(names) == len(set(names))


def test_every_report_fetch_is_callable():
    for name, report in REPORTS.items():
        assert callable(report.fetch), f"{name}: fetch is not callable"


def test_dates_required_only_set_alongside_uses_dates():
    for name, report in REPORTS.items():
        if report.dates_required:
            assert report.uses_dates, f"{name}: dates_required=True but uses_dates=False"


def test_row_highlight_when_set_is_callable():
    for name, report in REPORTS.items():
        if report.row_highlight is not None:
            assert callable(report.row_highlight), f"{name}: row_highlight is not callable"


def test_footer_lines_when_set_is_a_nonempty_list_of_strings():
    for name, report in REPORTS.items():
        if report.footer_lines is not None:
            assert report.footer_lines, f"{name}: footer_lines is set but empty"
            assert all(isinstance(line, str) and line for line in report.footer_lines), (
                f"{name}: footer_lines must be non-empty strings"
            )


def test_average_columns_is_a_subset_of_columns():
    for name, report in REPORTS.items():
        unknown = set(report.average_columns) - set(report.columns)
        assert not unknown, f"{name}: average_columns {unknown} not in columns"


def test_average_columns_only_set_alongside_uses_department_tabs():
    for name, report in REPORTS.items():
        if report.average_columns:
            assert report.uses_department_tabs, (
                f"{name}: average_columns is set but uses_department_tabs=False -- "
                "it's never read by _export_xlsx() in that case"
            )
