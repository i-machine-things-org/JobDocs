"""Tests for _neutralize_formula_cell(), the CSV/XLSX export formula-injection
guard in modules/reporting/module.py.

Pure function -- no DB/QApplication needed. See CodeRabbit finding on PR #341:
a JobBOSS note starting with "=" becomes a live formula when the exported
file is opened (openpyxl auto-detects data_type='f' for any string value
starting with "="; Excel's own CSV importer sniffs "+"/"-"/"@"/tab/CR too).

Also covers _export_title_block() specifically -- CodeRabbit's original PR
#341 finding was against that exact method (the "Customers:" summary line),
not just the per-row cell data, and it was still unfixed there when checked
again (this file's own per-cell tests existed, but nothing covered the
title block). _export_title_block() needs no QApplication either: it only
reads self._last_filters/_last_report_type/_available_employees/
_last_generated_at, all plain attributes, never touching a real widget.
"""

from modules.reporting.module import ReportingModule, _neutralize_formula_cell


def test_prefixes_equals_sign():
    assert _neutralize_formula_cell('=HYPERLINK("evil")') == '\'=HYPERLINK("evil")'


def test_prefixes_each_trigger_character():
    for char in ('=', '+', '-', '@', '\t', '\r'):
        value = f"{char}something"
        assert _neutralize_formula_cell(value) == f"'{value}"


def test_leaves_ordinary_text_untouched():
    assert _neutralize_formula_cell('STBD END PLATE') == 'STBD END PLATE'
    assert _neutralize_formula_cell('BRADKEN') == 'BRADKEN'
    assert _neutralize_formula_cell('2026-06-01') == '2026-06-01'


def test_leaves_blank_untouched():
    assert _neutralize_formula_cell('') == ''


def test_dash_in_the_middle_is_not_prefixed():
    # Only a LEADING trigger char matters -- "see dwg - rev 2" is ordinary text.
    assert _neutralize_formula_cell('see dwg - rev 2') == 'see dwg - rev 2'


def test_title_block_neutralizes_customers_line():
    mod = ReportingModule()
    mod._last_report_type = "Job Report"
    mod._last_filters = {'customers': ['=HYPERLINK("evil")', 'BRADKEN']}
    rows = mod._export_title_block()
    customers_row = next(r for r in rows if r and r[0] == "Customers:")
    assert customers_row[1] == '\'=HYPERLINK("evil"), BRADKEN'


def test_title_block_neutralizes_employees_line():
    mod = ReportingModule()
    mod._last_report_type = "Employee Efficiency - Detail"
    mod._last_filters = {'employees': ['E1']}
    mod._available_employees = [{'code': 'E1', 'name': '=cmd|/c calc'}]
    rows = mod._export_title_block()
    employees_row = next(r for r in rows if r and r[0] == "Employees:")
    assert employees_row[1] == "'=cmd|/c calc"


def test_title_block_leaves_ordinary_customers_untouched():
    mod = ReportingModule()
    mod._last_report_type = "Job Report"
    mod._last_filters = {'customers': ['BRADKEN', 'ACME']}
    rows = mod._export_title_block()
    customers_row = next(r for r in rows if r and r[0] == "Customers:")
    assert customers_row[1] == "BRADKEN, ACME"
