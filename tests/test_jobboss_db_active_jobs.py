"""Tests for fetch_active_job_numbers() in shared/jobboss_db.py.

Backs the Search tab's "Active Jobs Only" filter (modules/search/module.py).
Same Job.Status='Active' convention as job_report.py's own 'Active' filter --
see modules/reporting/README.md's "Known gap" for the caveat that the exact
column isn't verified against every JobBOSS schema.
"""

from unittest.mock import MagicMock, patch

import pytest

from shared import jobboss_db


def _configured_settings():
    return {
        'jobboss_db_host': 'SERVER\\INSTANCE',
        'jobboss_db_name': 'JobBossDB',
        'jobboss_db_user': 'jobdocs_reporting_ro',
        'jobboss_db_port': '',
    }


def test_not_configured_raises_without_connecting():
    with pytest.raises(RuntimeError):
        jobboss_db.fetch_active_job_numbers({})


@patch('shared.jobboss_db.is_configured', return_value=True)
@patch('shared.jobboss_db.connect')
def test_job_numbers_are_stripped_and_uppercased(mock_connect, mock_is_configured):
    # Mixed case/whitespace, plus a blank/None row that must be dropped --
    # real JobBOSS Job numbers can carry a sub-job letter suffix (e.g.
    # '27173h'), and the Search tab's own folder-derived job numbers are
    # compared uppercase (see _passes_active_filter() in
    # modules/search/module.py), so this function must normalize the same way.
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        {'Job': '27173h'}, {'Job': ' 1001 '}, {'Job': None}, {'Job': ''},
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value.__enter__.return_value = mock_conn

    result = jobboss_db.fetch_active_job_numbers(_configured_settings())

    assert result == {'27173H', '1001'}
