"""Tests for SearchModule's readonly_mode enforcement.

modules/search/module.py._blueprints_path_action() is the one write-capable
action reachable from a read-only (search-only) install's Search tab — it
hard-links a file into the blueprints folder and can persist a settings
change. These tests exercise that guard directly: with readonly_mode=True
the write must not happen; with readonly_mode=False it must still work.

Note: SearchModule.initialize() (not used here) opens a SQLite index file
under the real per-OS config directory as a side effect — tests construct
the module directly and set `_app_context` to avoid touching that path.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from core.app_context import AppContext
from modules.search.module import SearchModule


# QApplication.clipboard() requires a live QApplication instance. Constructed
# once at module import time and held in a module-level variable so it isn't
# garbage-collected between test calls (a local variable whose return value
# is discarded gets GC'd immediately, leaving QApplication.clipboard() None).
_QAPP = QApplication.instance() or QApplication([])


def _qapp() -> QApplication:
    return _QAPP


class _FakeTable:
    """Stand-in for the real QTableWidget — only currentRow() is used."""

    def __init__(self, row: int = 0):
        self._row = row

    def currentRow(self):
        return self._row


def _make_module(app_context: AppContext, source_path: Path, customer: str = 'Acme') -> SearchModule:
    module = SearchModule()
    # Bypass SearchModule.initialize()/BaseModule.initialize() — the former
    # opens a SQLite index under the real user config dir as a side effect,
    # which we don't want triggered by a unit test.
    module._app_context = app_context
    module._widget = None
    module.search_table = _FakeTable(0)
    module.search_status_label = MagicMock()
    module.search_results = [{
        'date': None,
        'customer': customer,
        'job_number': '10001',
        'description': 'Test Job',
        'drawings': [],
        'path': str(source_path.parent),
    }]
    return module


def _make_app_context(
    tmp_path: Path, bp_dir: Path, *, readonly_mode: bool, suppress_notification: bool = True
) -> tuple[AppContext, MagicMock, MagicMock]:
    show_error = MagicMock()
    save_settings = MagicMock()
    settings = {
        'blueprints_dir': str(bp_dir),
        'suppress_bp_link_notification': suppress_notification,
    }
    app_context = AppContext(
        settings=settings,
        history={},
        config_dir=tmp_path,
        save_settings_callback=save_settings,
        save_history_callback=MagicMock(),
        log_message_callback=MagicMock(),
        show_error_callback=show_error,
        show_info_callback=MagicMock(),
        get_customer_list_callback=MagicMock(return_value=[]),
        add_to_history_callback=MagicMock(),
        readonly_mode=readonly_mode,
    )
    return app_context, show_error, save_settings


class TestBlueprintsPathActionReadonlyGuard:
    """_blueprints_path_action() must not write anything when readonly_mode is True."""

    def test_readonly_mode_blocks_hardlink_and_setting_write(self, tmp_path):
        _qapp()
        source = tmp_path / 'source' / 'drawing.pdf'
        source.parent.mkdir(parents=True)
        source.write_text('drawing contents')
        bp_dir = tmp_path / 'blueprints'
        bp_dir.mkdir()

        app_context, show_error, save_settings = _make_app_context(
            tmp_path, bp_dir, readonly_mode=True,
        )
        module = _make_module(app_context, source)

        module._blueprints_path_action(str(source))

        dest_dir = bp_dir / 'Acme'
        assert not dest_dir.exists(), "readonly install must not create the blueprints subfolder"
        assert not (dest_dir / 'drawing.pdf').exists(), "readonly install must not hard-link the file"
        show_error.assert_called_once()
        save_settings.assert_not_called()

    def test_non_readonly_mode_still_links_file(self, tmp_path):
        _qapp()
        source = tmp_path / 'source' / 'drawing.pdf'
        source.parent.mkdir(parents=True)
        source.write_text('drawing contents')
        bp_dir = tmp_path / 'blueprints'
        bp_dir.mkdir()

        # suppress_bp_link_notification=True avoids the modal QMessageBox
        # confirmation on a successful link, keeping this test headless-safe.
        app_context, show_error, save_settings = _make_app_context(
            tmp_path, bp_dir, readonly_mode=False, suppress_notification=True,
        )
        module = _make_module(app_context, source)

        module._blueprints_path_action(str(source))

        dest = bp_dir / 'Acme' / 'drawing.pdf'
        assert dest.exists(), "non-readonly install must hard-link the file into blueprints"
        assert os.path.samefile(source, dest), "destination must be a hard link to the source, not a copy"
        show_error.assert_not_called()

    def test_readonly_mode_blocked_even_when_menu_item_bypassed(self, tmp_path):
        """Defense-in-depth: the handler itself refuses the write even if
        called directly (e.g. a stale signal), not just via the hidden menu
        item — mirrors how show_search_context_menu() omits "Blueprints Path"
        entirely when app_context.readonly_mode is True."""
        _qapp()
        source = tmp_path / 'source' / 'drawing.pdf'
        source.parent.mkdir(parents=True)
        source.write_text('drawing contents')
        bp_dir = tmp_path / 'blueprints'
        bp_dir.mkdir()

        app_context, _, _ = _make_app_context(tmp_path, bp_dir, readonly_mode=True)
        assert app_context.readonly_mode is True
        assert app_context.is_readonly() is True

        module = _make_module(app_context, source)
        module._blueprints_path_action(str(source))

        assert list(bp_dir.iterdir()) == [], "no files should exist under blueprints_dir at all"
