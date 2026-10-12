"""Tests for test_connection()'s port-parsing guard in experimental/db_integration.py.

CodeRabbit finding on PR #341: a non-numeric Port value (a stray space,
"auto" typed literally, "1433,1434") made int(port_raw) raise ValueError
*outside* test_connection()'s own try block. _ConnectWorker.run() has no
try of its own -- it trusts test_connection() to always return a (bool, str)
tuple -- so the exception escaped the worker thread entirely, leaving
finished_ok never emitted and the Reporting tab stuck on "Connecting..."
with no error shown.

No DB connection is reached in these tests -- a bad port is rejected before
_connect_kwargs() ever gets to pytds.connect().
"""

from unittest.mock import patch

# Aliased on import -- pytest's default collection treats any top-level
# callable named test_* in a test module's namespace as a test case, imported
# or not, which would otherwise try to collect db_integration's own
# test_connection() itself and fail resolving its `settings` arg as a fixture.
from experimental.db_integration import test_connection as jobboss_test_connection


def _configured_settings(port):
    return {
        'jobboss_db_host': 'SERVER\\INSTANCE',
        'jobboss_db_name': 'JobBossDB',
        'jobboss_db_user': 'jobdocs_reporting_ro',
        'jobboss_db_port': port,
    }


@patch('experimental.db_integration.get_password', return_value='fake-password')
def test_non_numeric_port_returns_clean_error_not_raise(mock_get_password):
    ok, message = jobboss_test_connection(_configured_settings('not-a-number'))
    assert ok is False
    assert 'port' in message.lower()


@patch('experimental.db_integration.get_password', return_value='fake-password')
def test_port_with_internal_space_returns_clean_error(mock_get_password):
    # A trailing/leading space alone wouldn't reproduce this (_connect_kwargs
    # already .strip()s port_raw before int()) -- an internal space survives
    # strip() and still fails int(), which is the real failure mode.
    ok, message = jobboss_test_connection(_configured_settings('14 33'))
    assert ok is False
    assert 'port' in message.lower()


@patch('experimental.db_integration.get_password', return_value='fake-password')
def test_comma_separated_port_returns_clean_error(mock_get_password):
    ok, message = jobboss_test_connection(_configured_settings('1433,1434'))
    assert ok is False
    assert 'port' in message.lower()
