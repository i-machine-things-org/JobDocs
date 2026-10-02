"""Tests for the Search tab's "Related Files" Folder Contents enrichment.

modules/search/module.py._add_related_files_node() adds a synthetic
"Related Files" node to the Folder Contents panel when a selected job
result's drawing/part numbers match files in the separately-configured
Related Files directory -- those files live outside the job folder
entirely, so the normal directory listing never surfaces them.
"""

import os
import sqlite3
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidget

from modules.search.module import SearchModule

# QTreeWidget requires a live QApplication instance. Held at module scope so
# it isn't garbage-collected between test calls.
_QAPP = QApplication.instance() or QApplication([])


def _make_module(app_context) -> SearchModule:
    module = SearchModule()
    module._app_context = app_context
    module._widget = None
    module.folder_tree = QTreeWidget()
    return module


def _job_result(customer='Acme', drawings=None):
    return {
        'customer': customer,
        'job_number': '12345',
        'description': 'Bracket',
        'drawings': drawings if drawings is not None else ['10-0315-G'],
        'po_number': '',
        'path': 'C:/Customers/Acme/12345_Bracket',
    }


def _tree_top_level_texts(tree: QTreeWidget):
    root = tree.invisibleRootItem()
    return [root.child(i).text(0) for i in range(root.childCount())]


class TestFindRelatedFiles:
    """_find_related_files() queries the SQLite index only -- deliberately no
    live filesystem-walk fallback, since this runs inline on the GUI thread
    from a row-selection signal and a live os.walk() risks the exact UI
    freeze the QThread-based search workers exist to avoid.
    """

    def test_no_index_returns_empty(self):
        module = _make_module(MagicMock())
        module._index = None

        assert module._find_related_files('Acme', ['10-0315-G'], 'RF') == []

    def test_returns_joined_paths_from_index_rows(self):
        module = _make_module(MagicMock())
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = [
            {'dir_path': 'C:/RelatedFiles/Acme', 'filename': '10-0315-G r9.pdf'},
        ]

        result = module._find_related_files('Acme', ['10-0315-G'], 'RF')

        assert result == [os.path.join('C:/RelatedFiles/Acme', '10-0315-G r9.pdf')]
        module._index.find_files_for_drawings.assert_called_once_with(
            'Acme', ['10-0315-G'], ('RF',)
        )

    def test_query_failure_returns_empty_instead_of_raising(self):
        module = _make_module(MagicMock())
        module._index = MagicMock()
        module._index.find_files_for_drawings.side_effect = sqlite3.OperationalError("locked")

        assert module._find_related_files('Acme', ['10-0315-G'], 'RF') == []


class TestAddRelatedFilesNode:
    def test_non_job_result_with_no_drawings_is_a_noop(self):
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=False)))
        module._index = MagicMock()

        module._add_related_files_node(_job_result(drawings=[]))

        module._index.find_files_for_drawings.assert_not_called()
        assert _tree_top_level_texts(module.folder_tree) == []

    def test_matching_job_adds_related_files_node(self):
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=False)))
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = [
            {'dir_path': 'C:/RelatedFiles/Acme', 'filename': '10-0315-G r9.pdf'},
        ]
        module._is_within_permitted_roots = MagicMock(return_value=True)

        module._add_related_files_node(_job_result())

        assert _tree_top_level_texts(module.folder_tree) == ['Related Files']
        group = module.folder_tree.invisibleRootItem().child(0)
        assert group.childCount() == 1
        child = group.child(0)
        assert child.text(0) == '10-0315-G r9.pdf'
        assert child.data(0, Qt.ItemDataRole.UserRole).endswith('10-0315-G r9.pdf')

    def test_no_matches_adds_no_node(self):
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=False)))
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = []

        module._add_related_files_node(_job_result())

        assert _tree_top_level_texts(module.folder_tree) == []

    def test_itar_customer_queries_itar_rf_prefix(self):
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=False)))
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = []

        module._add_related_files_node(_job_result(customer='[ITAR] Defense Co'))

        module._index.find_files_for_drawings.assert_called_once_with(
            'Defense Co', ['10-0315-G'], ('ITAR-RF',)
        )

    def test_readonly_filters_matches_outside_permitted_roots(self):
        """Defense-in-depth mirroring _populate_tree_level()/_open_item_
        externally(): a match whose canonical path resolves outside the
        currently-permitted (non-ITAR) roots must not be shown, even if it
        somehow made it into the index (e.g. a stale entry from before this
        machine was reconfigured to Read-Only)."""
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=True)))
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = [
            {'dir_path': 'C:/RelatedFiles/Acme', 'filename': 'allowed.pdf'},
            {'dir_path': 'C:/ITAR_RelatedFiles/Acme', 'filename': 'blocked.pdf'},
        ]
        module._is_within_permitted_roots = MagicMock(
            side_effect=lambda p: 'ITAR_RelatedFiles' not in p
        )

        module._add_related_files_node(_job_result())

        group = module.folder_tree.invisibleRootItem().child(0)
        names = [group.child(i).text(0) for i in range(group.childCount())]
        assert names == ['allowed.pdf']

    def test_customer_prefix_stripping_covers_rf_and_itar_rf_labels(self):
        # A result whose own customer label already carries an [RF]/[ITAR-RF]
        # prefix (a Related Files search result row itself, not a job) must
        # still resolve to the bare customer name, not query for a customer
        # literally named "[RF] Acme".
        module = _make_module(MagicMock(is_readonly=MagicMock(return_value=False)))
        module._index = MagicMock()
        module._index.find_files_for_drawings.return_value = []

        module._add_related_files_node(_job_result(customer='[RF] Acme'))

        module._index.find_files_for_drawings.assert_called_once_with(
            'Acme', ['10-0315-G'], ('RF',)
        )
