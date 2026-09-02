"""Tests for FolderNamingReportDialog's double-click-to-reveal behavior.

Double-clicking a row should reveal that folder in the OS file browser,
highlighted in its containing directory -- but per CODING_NOTES.md's
"kiosk/read-only UI must block every path to Explorer, not just the obvious
menu item... audit double-click handlers too" note, it must be a no-op
entirely on a read-only (search-only) install, matching every other
Explorer-launching action in this module (_open_item_externally(),
open_selected_search_job()).
"""

import os

import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from modules.search.module import FolderNamingReportDialog  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_results(path):
    return [("Acme", path, "unrecognized folder")]


def test_double_click_reveals_path_when_not_readonly(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    with patch("modules.search.module.reveal_in_file_manager") as mock_reveal:
        mock_reveal.return_value = (True, None)
        dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)
        index = dialog.table.model().index(0, 1)
        dialog._on_row_double_clicked(index)

    mock_reveal.assert_called_once_with(str(target))


def test_double_click_does_nothing_when_readonly(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=True))

    with patch("modules.search.module.reveal_in_file_manager") as mock_reveal:
        dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)
        # Not connected at all on a read-only install -- emitting the signal
        # must reach no slot, so reveal_in_file_manager is never called even
        # though a row exists.
        dialog.table.doubleClicked.emit(dialog.table.model().index(0, 1))

    mock_reveal.assert_not_called()


def test_double_click_warns_on_missing_path(qapp, tmp_path):
    missing = str(tmp_path / "gone")
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    with patch("modules.search.module.reveal_in_file_manager") as mock_reveal, \
            patch("modules.search.module.QMessageBox") as mock_box:
        mock_reveal.return_value = (False, f"Not found: {missing}")
        dialog = FolderNamingReportDialog(None, _make_results(missing), app_context)
        index = dialog.table.model().index(0, 1)
        dialog._on_row_double_clicked(index)

    mock_box.warning.assert_called_once()
