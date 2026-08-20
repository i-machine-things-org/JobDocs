"""Tests for SearchModule's readonly_mode enforcement.

modules/search/module.py._blueprints_path_action() is the one write-capable
action reachable from a read-only (search-only) install's Search tab — it
hard-links a file into the blueprints folder and can persist a settings
change. These tests exercise that guard directly: with readonly_mode=True
the write must not happen; with readonly_mode=False it must still work.

Also covers two other read-only (search-only) kiosk restrictions:
- ITAR customer/blueprint directories are excluded from search/indexing
  entirely (_get_customer_files_dirs/_get_blueprint_dirs), not merely
  labeled — a shared/shop-floor kiosk must not surface export-controlled
  job data at all.
- No action may launch Explorer or offer a pasteable path
  (open_selected_search_job/open_selected_blueprints/copy_search_path/
  _open_item_externally on a directory) — only printing and opening
  individual files in their own viewer remain available.

Note: SearchModule.initialize() (not used here) opens a SQLite index file
under the real per-OS config directory as a side effect — tests construct
the module directly and set `_app_context` to avoid touching that path.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidgetItem

from core.app_context import AppContext
from modules.search.module import SearchModule


# QApplication.clipboard() requires a live QApplication instance. Constructed
# once at module import time and held in a module-level variable so it isn't
# garbage-collected between test calls (a local variable whose return value
# is discarded gets GC'd immediately, leaving QApplication.clipboard() None).
_QAPP = QApplication.instance() or QApplication([])


def _qapp() -> QApplication:
    return _QAPP


@contextmanager
def _patched_search_module_global(name: str, **mock_kwargs):
    """patch.dict on a name in modules.search.module's own globals (read via
    a known method's __globals__), not patch('modules.search.module.<name>').

    The latter resolves sys.modules['modules.search.module'] by string at
    patch time. core.module_loader can register a second, distinct module
    object under that same dotted name (dev-mode dynamic loading uses the
    same name as the standard package import), and depending on what else
    has run earlier in the test session, sys.modules may already hold that
    second copy — silently patching a dict SearchModule's methods don't
    actually read from. Patching the function's own __globals__ dict is
    correct regardless of which module object sys.modules currently holds.
    """
    mock = MagicMock(**mock_kwargs)
    with patch.dict(SearchModule._open_item_externally.__globals__, {name: mock}):
        yield mock


def _patched_qdesktopservices():
    return _patched_search_module_global('QDesktopServices')


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
        app_context, show_error, _save_settings = _make_app_context(
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


def _make_bare_module(app_context: AppContext) -> SearchModule:
    """A SearchModule with just app_context wired — for helpers that don't
    touch search_table/search_results (dir-discovery, Explorer guards)."""
    module = SearchModule()
    module._app_context = app_context
    module._widget = None
    return module


class TestItarExclusionFromSearchDirs:
    """A read-only (search-only) install must never search, index, or
    otherwise surface the ITAR customer/blueprint directories — it's meant
    for shared/shop-floor kiosk machines (README) that must not expose
    export-controlled job data."""

    def _settings(self, tmp_path: Path) -> dict:
        cf_dir = tmp_path / 'customers'
        itar_cf_dir = tmp_path / 'itar_customers'
        bp_dir = tmp_path / 'blueprints'
        itar_bp_dir = tmp_path / 'itar_blueprints'
        for d in (cf_dir, itar_cf_dir, bp_dir, itar_bp_dir):
            d.mkdir()
        return {
            'customer_files_dir': str(cf_dir),
            'itar_customer_files_dir': str(itar_cf_dir),
            'blueprints_dir': str(bp_dir),
            'itar_blueprints_dir': str(itar_bp_dir),
        }

    def _context(self, tmp_path: Path, settings: dict, *, readonly_mode: bool) -> AppContext:
        return AppContext(
            settings=settings,
            history={},
            config_dir=tmp_path,
            save_settings_callback=MagicMock(),
            save_history_callback=MagicMock(),
            log_message_callback=MagicMock(),
            show_error_callback=MagicMock(),
            show_info_callback=MagicMock(),
            get_customer_list_callback=MagicMock(return_value=[]),
            add_to_history_callback=MagicMock(),
            readonly_mode=readonly_mode,
        )

    def test_readonly_excludes_itar_customer_dir(self, tmp_path):
        settings = self._settings(tmp_path)
        app_context = self._context(tmp_path, settings, readonly_mode=True)
        module = _make_bare_module(app_context)

        dirs = module._get_customer_files_dirs()

        prefixes = [p for p, _ in dirs]
        assert prefixes == ['']
        assert settings['itar_customer_files_dir'] not in [d for _, d in dirs]

    def test_non_readonly_includes_itar_customer_dir(self, tmp_path):
        settings = self._settings(tmp_path)
        app_context = self._context(tmp_path, settings, readonly_mode=False)
        module = _make_bare_module(app_context)

        dirs = module._get_customer_files_dirs()

        assert sorted(p for p, _ in dirs) == ['', 'ITAR']

    def test_readonly_excludes_itar_blueprint_dir(self, tmp_path):
        settings = self._settings(tmp_path)
        app_context = self._context(tmp_path, settings, readonly_mode=True)
        module = _make_bare_module(app_context)

        dirs = module._get_blueprint_dirs()

        prefixes = [p for p, _ in dirs]
        assert prefixes == ['BP']

    def test_non_readonly_includes_itar_blueprint_dir(self, tmp_path):
        settings = self._settings(tmp_path)
        app_context = self._context(tmp_path, settings, readonly_mode=False)
        module = _make_bare_module(app_context)

        dirs = module._get_blueprint_dirs()

        assert sorted(p for p, _ in dirs) == ['BP', 'ITAR-BP']

    def test_readonly_search_from_index_drops_stale_itar_results(self, tmp_path):
        """Defense in depth: even if the local index still has ITAR rows
        (e.g. this machine was reconfigured from Full to Read-Only and
        hasn't re-indexed yet), query results must not include them."""
        settings = self._settings(tmp_path)
        app_context = self._context(tmp_path, settings, readonly_mode=True)
        module = _make_bare_module(app_context)
        module._index = MagicMock()
        module._index.search_jobs.return_value = [
            {'customer': 'Acme', 'job_number': '1'},
            {'customer': '[ITAR] Defense Co', 'job_number': '2'},
        ]
        module._index.search_quotes.return_value = [
            {'customer': '[ITAR Quote] Defense Co', 'job_number': 'Q1'},
        ]
        module._index_failures = 0
        module._index_query_failed = False
        module.search_status_label = MagicMock()
        module.search_results = []
        module._apply_sort = MagicMock()

        found = module._search_from_index('acme', True, True, True, True, include_blueprints=False)

        assert found is True
        assert [r['customer'] for r in module.search_results] == ['Acme']


class TestNoFilesystemEscapeOnReadonly:
    """A read-only (search-only) install must never launch Explorer or hand
    the user a pasteable filesystem path — only printing and opening
    individual files in their own viewer are available."""

    def _context(self, tmp_path: Path, *, readonly_mode: bool) -> AppContext:
        return AppContext(
            settings={},
            history={},
            config_dir=tmp_path,
            save_settings_callback=MagicMock(),
            save_history_callback=MagicMock(),
            log_message_callback=MagicMock(),
            show_error_callback=MagicMock(),
            show_info_callback=MagicMock(),
            get_customer_list_callback=MagicMock(return_value=[]),
            add_to_history_callback=MagicMock(),
            readonly_mode=readonly_mode,
        )

    def test_open_selected_search_job_noop_when_readonly(self, tmp_path):
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        module.search_table = _FakeTable(0)
        module.search_results = [{'customer': 'Acme', 'path': str(tmp_path)}]

        with _patched_search_module_global('open_folder') as open_folder:
            module.open_selected_search_job()

        open_folder.assert_not_called()

    def test_open_selected_blueprints_noop_when_readonly(self, tmp_path):
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        module.search_table = _FakeTable(0)
        module.search_results = [{'customer': 'Acme', 'path': str(tmp_path)}]

        with _patched_search_module_global('open_folder') as open_folder:
            module.open_selected_blueprints()

        open_folder.assert_not_called()

    def test_copy_search_path_noop_when_readonly(self, tmp_path):
        _qapp()
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        module.search_table = _FakeTable(0)
        module.search_results = [{'customer': 'Acme', 'path': str(tmp_path)}]
        module.search_status_label = MagicMock()

        module.copy_search_path()

        module.search_status_label.setText.assert_not_called()

    def test_open_item_externally_refuses_directory_when_readonly(self, tmp_path):
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        a_dir = tmp_path / 'subfolder'
        a_dir.mkdir()
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_dir))

        with _patched_qdesktopservices() as qds:
            module._open_item_externally(item)

        qds.openUrl.assert_not_called()

    def test_open_item_externally_opens_a_temp_copy_when_readonly(self, tmp_path):
        """The external viewer must never see the real customer-directory
        path — its own "Save As" / "Recent Files" would hand it straight
        back to the user, undoing every other kiosk restriction."""
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        source_dir = tmp_path / 'Z_Customer_Files' / 'Acme' / 'job documents'
        source_dir.mkdir(parents=True)
        a_file = source_dir / 'drawing.pdf'
        a_file.write_text('contents')
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_file))

        with _patched_qdesktopservices() as qds:
            module._open_item_externally(item)

        qds.openUrl.assert_called_once()
        opened_path = Path(qds.openUrl.call_args[0][0].toLocalFile())
        assert opened_path != a_file, "must open a copy, not the real path"
        assert str(source_dir) not in str(opened_path), \
            "temp copy must not reveal the real customer directory path"
        assert opened_path.name == 'drawing.pdf', "filename should still look sane in the viewer"
        assert opened_path.read_text() == 'contents'

    def test_open_item_externally_fails_closed_on_temp_copy_error(self, tmp_path):
        """If the temp copy can't be made, never fall back to opening the
        real path — that would silently defeat the whole guard."""
        app_context = self._context(tmp_path, readonly_mode=True)
        module = _make_bare_module(app_context)
        module.show_error = MagicMock()
        a_file = tmp_path / 'drawing.pdf'
        a_file.write_text('contents')
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_file))

        with _patched_qdesktopservices() as qds, \
                _patched_search_module_global('shutil', copy2=MagicMock(side_effect=OSError("disk full"))):
            module._open_item_externally(item)

        qds.openUrl.assert_not_called()
        module.show_error.assert_called_once()

    def test_open_item_externally_opens_directory_when_not_readonly(self, tmp_path):
        app_context = self._context(tmp_path, readonly_mode=False)
        module = _make_bare_module(app_context)
        a_dir = tmp_path / 'subfolder'
        a_dir.mkdir()
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_dir))

        with _patched_qdesktopservices() as qds:
            module._open_item_externally(item)

        qds.openUrl.assert_called_once()
