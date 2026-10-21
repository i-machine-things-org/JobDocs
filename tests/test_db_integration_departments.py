"""Tests for the Department filter added to experimental/db_integration.py --
department_filter_clause() (pure) and the _DISTINCT_DEPARTMENTS_QUERY
constant that backs fetch_departments().

No DB connection needed for either: department_filter_clause() is a pure
IN-clause builder (same shape as employee_filter_clause()), and
_DISTINCT_DEPARTMENTS_QUERY is checked as a plain string, the same way
test_report_employee_efficiency.py checks the Employee Efficiency queries'
own Indirect-work-center exclusion.
"""

from experimental.db_integration import _DISTINCT_DEPARTMENTS_QUERY, department_filter_clause


def test_no_departments_selected_means_no_filter():
    clause, params = department_filter_clause(None, column='wc.Department')
    assert clause == "1=1"
    assert params == ()
    clause, params = department_filter_clause([], column='wc.Department')
    assert clause == "1=1"
    assert params == ()


def test_one_department_selected():
    clause, params = department_filter_clause(['MACHINING'], column='wc.Department')
    assert clause == "wc.Department IN (%s)"
    assert params == ('MACHINING',)


def test_several_departments_selected():
    clause, params = department_filter_clause(['MACHINING', 'ASSEMBLY'], column='wc.Department')
    assert clause == "wc.Department IN (%s, %s)"
    assert params == ('MACHINING', 'ASSEMBLY')


def test_blank_entries_are_dropped():
    # Mirrors employee_filter_clause/customer_filter_clause's own blank-entry
    # handling -- a stray '' in the selected list (shouldn't happen via the
    # picker UI, but costs nothing to guard) must not become a literal empty
    # IN-list entry.
    clause, params = department_filter_clause(['MACHINING', '', None], column='wc.Department')
    assert clause == "wc.Department IN (%s)"
    assert params == ('MACHINING',)


def test_distinct_departments_query_excludes_indirect_work_centers():
    # Regression guard: an "Indirect" department would be a filter option
    # that can never match any row Employee Efficiency actually shows, since
    # that report already drops Indirect work centers unconditionally (see
    # modules/reporting/reports/employee_efficiency.py).
    assert "FROM Work_Center" in _DISTINCT_DEPARTMENTS_QUERY
    assert "Type <> 'Indirect'" in _DISTINCT_DEPARTMENTS_QUERY
