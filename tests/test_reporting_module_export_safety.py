"""Tests for _neutralize_formula_cell(), the CSV/XLSX export formula-injection
guard in modules/reporting/module.py.

Pure function -- no DB/QApplication needed. See CodeRabbit finding on PR #341:
a JobBOSS note starting with "=" becomes a live formula when the exported
file is opened (openpyxl auto-detects data_type='f' for any string value
starting with "="; Excel's own CSV importer sniffs "+"/"-"/"@"/tab/CR too).
"""

from modules.reporting.module import _neutralize_formula_cell


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
