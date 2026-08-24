"""Tests for SearchModule._search_from_index()'s failure bookkeeping.

A failed index query and a confirmed zero-result search both make
_search_from_index() return False. perform_search() distinguishes them via
self._index_query_failed before trusting self._index.is_fully_covered() —
otherwise a failed query could be reported as "Found 0 result(s)", or (after
the index is disabled following repeated failures) crash on None.is_fully_covered().
"""

from datetime import datetime
from unittest.mock import MagicMock

from modules.search.module import SearchModule


def _make_module() -> SearchModule:
    module = SearchModule()
    module._widget = None
    module.search_table = MagicMock()
    module.search_status_label = MagicMock()
    module._app_context = MagicMock(is_readonly=MagicMock(return_value=False))
    return module


def test_query_failure_sets_failed_flag_and_returns_false():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.side_effect = RuntimeError("boom")

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is False
    assert module._index_query_failed is True
    assert module._index_failures == 1
    assert module._index is not None  # not yet disabled before the 3rd failure


def test_third_consecutive_failure_disables_index():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.side_effect = RuntimeError("boom")

    for _ in range(3):
        result = module._search_from_index('term', True, True, True, True, False)
        assert result is False

    assert module._index_failures == 3
    assert module._index is None
    assert module._index_query_failed is True


def test_successful_query_clears_failed_flag():
    module = _make_module()
    module._index = MagicMock()
    module._index_query_failed = True
    module._index_failures = 2
    module._index.search_jobs.return_value = [{
        'date': datetime(2026, 1, 1), 'customer': 'Acme', 'job_number': '1',
        'po_number': '', 'description': 'Test', 'drawings': [],
    }]
    module._index.search_quotes.return_value = []

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is True
    assert module._index_query_failed is False
    assert module._index_failures == 0


def test_zero_results_leaves_failed_flag_false():
    module = _make_module()
    module._index = MagicMock()
    module._index.search_jobs.return_value = []
    module._index.search_quotes.return_value = []

    result = module._search_from_index('term', True, True, True, True, False)

    assert result is False
    assert module._index_query_failed is False
