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

from PyQt6.QtCore import Qt, QPoint  # noqa: E402
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


def test_context_menu_connected_when_not_readonly(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)

    assert dialog.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_context_menu_not_connected_when_readonly(qapp, tmp_path):
    """Mirrors show_search_context_menu()'s readonly gate: a kiosk install
    never gets a path to Explorer, so the menu is never wired up at all."""
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=True))

    dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)

    assert dialog.table.contextMenuPolicy() != Qt.ContextMenuPolicy.CustomContextMenu


def _row0_pos(dialog):
    return QPoint(5, dialog.table.rowViewportPosition(0) + 5)


def test_context_menu_open_action_reveals_path(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    with patch("modules.search.module.reveal_in_file_manager") as mock_reveal, \
            patch("modules.search.module.QMenu") as mock_menu_cls:
        mock_reveal.return_value = (True, None)
        mock_menu = mock_menu_cls.return_value
        open_action, copy_action = MagicMock(), MagicMock()
        mock_menu.addAction.side_effect = [open_action, copy_action]

        dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)
        dialog._show_context_menu(_row0_pos(dialog))

        mock_menu.exec.assert_called_once()
        # Invoke the callback that was wired to "Open"'s triggered signal --
        # menu.exec() is mocked out (it would otherwise block on a real
        # click) so the click itself is simulated here instead.
        open_action.triggered.connect.call_args[0][0]()

    mock_reveal.assert_called_once_with(str(target))


def test_context_menu_copy_action_copies_path(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    with patch("modules.search.module.QMenu") as mock_menu_cls:
        mock_menu = mock_menu_cls.return_value
        open_action, copy_action = MagicMock(), MagicMock()
        mock_menu.addAction.side_effect = [open_action, copy_action]

        dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)
        dialog._show_context_menu(_row0_pos(dialog))

        copy_action.triggered.connect.call_args[0][0]()

    assert qapp.clipboard().text() == str(target)


def test_context_menu_does_nothing_off_row(qapp, tmp_path):
    target = tmp_path / "New folder"
    target.mkdir()
    app_context = MagicMock(is_readonly=MagicMock(return_value=False))

    with patch("modules.search.module.QMenu") as mock_menu_cls:
        dialog = FolderNamingReportDialog(None, _make_results(str(target)), app_context)
        # Far below the single populated row -- rowAt() returns -1 there.
        dialog._show_context_menu(QPoint(5, 5000))

    mock_menu_cls.assert_not_called()
