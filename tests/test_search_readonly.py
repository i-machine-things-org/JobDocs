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

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem

from core.app_context import AppContext
from modules.search.module import SearchModule, SearchWorker


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


class TestIsWithinPermittedRootsEdgeCases:
    """Direct coverage for _is_within_permitted_roots()'s os.path.commonpath()
    -based containment check, which replaced an earlier string-prefix
    comparison CodeRabbit flagged as Windows-unsafe: case-insensitivity,
    drive-letter mismatches, and trailing separators (PR #315).

    CI's "Tests" job runs on ubuntu-latest, so os.path is posixpath there —
    it has no concept of drive letters or backslash separators, and
    normcase() is a no-op. Tests for those specifically-Windows behaviors
    are skipped off Windows rather than faked with literal "C:\\..." strings,
    which posixpath would treat as a single opaque filename with no
    separators at all (that's what broke this class in CI the first time:
    two tests asserted Windows-only semantics using literal path strings and
    silently exercised meaningless posixpath behavior instead). Tests for
    the platform-independent parts of the fix (rejecting a same-prefix
    sibling, honoring a trailing separator on the configured root) use real
    tmp_path directories so they mean the same thing on either OS.
    """

    def _module(self, customer_dirs=(), blueprint_dirs=()):
        module = _make_bare_module(MagicMock())
        module._get_customer_files_dirs = MagicMock(return_value=list(customer_dirs))
        module._get_blueprint_dirs = MagicMock(return_value=list(blueprint_dirs))
        return module

    @pytest.mark.skipif(os.name != 'nt', reason="case-insensitive paths are a Windows-only concept")
    def test_matches_regardless_of_case(self):
        module = self._module(customer_dirs=[('', r'C:\Customers')])
        assert module._is_within_permitted_roots(r'c:\CUSTOMERS\Acme\job.pdf') is True

    @pytest.mark.skipif(os.name != 'nt', reason="drive letters are a Windows-only concept")
    def test_different_drive_is_not_a_match(self):
        """A configured root on C: must not "contain" a path on D: — must
        not raise, either (os.path.commonpath() raises ValueError for
        cross-drive inputs; that means no match, not a crash)."""
        module = self._module(customer_dirs=[('', r'C:\Customers')])
        assert module._is_within_permitted_roots(r'D:\Customers\Acme\job.pdf') is False

    def test_trailing_separator_on_configured_root_still_matches(self, tmp_path):
        customer_dir = tmp_path / 'Customers'
        customer_dir.mkdir()
        module = self._module(customer_dirs=[('', str(customer_dir) + os.sep)])
        allowed_path = str(customer_dir / 'Acme' / 'job.pdf')
        assert module._is_within_permitted_roots(allowed_path) is True

    def test_sibling_directory_with_shared_prefix_is_not_a_match(self, tmp_path):
        """"Customers2" must not read as "inside" "Customers" just because
        the strings share a prefix — the bug a naive str.startswith() check
        had before this fix (CodeRabbit, PR #315)."""
        customer_dir = tmp_path / 'Customers'
        customer_dir.mkdir()
        sibling_dir = tmp_path / 'Customers2'
        sibling_dir.mkdir()
        module = self._module(customer_dirs=[('', str(customer_dir))])
        outside_path = str(sibling_dir / 'Acme' / 'job.pdf')
        assert module._is_within_permitted_roots(outside_path) is False

    def test_no_configured_roots_matches_nothing(self, tmp_path):
        module = self._module()
        assert module._is_within_permitted_roots(str(tmp_path / 'Customers' / 'Acme' / 'job.pdf')) is False


class TestPopulateTreeLevelReparsePointFilter:
    """_populate_tree_level() must exclude reparse points (symlinks,
    junctions) outright on a read-only install, not follow them — a link
    under a permitted folder could target the excluded ITAR directory
    (CodeRabbit, PR #315).

    Mocks is_reparse_point() directly rather than creating a real
    symlink/junction, since that requires Developer Mode or elevation on
    Windows and would otherwise skip on many CI runners — see
    TestReparsePointExclusionOnReadonly below for a real-symlink test that
    skips gracefully where unsupported.
    """

    def _context(self, tmp_path: Path, *, readonly_mode: bool, settings: dict | None = None) -> AppContext:
        return AppContext(
            settings=settings or {},
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

    def test_reparse_point_excluded_when_readonly(self, tmp_path):
        real_dir = tmp_path / 'real_job'
        real_dir.mkdir()
        linked_dir = tmp_path / 'linked_job'
        linked_dir.mkdir()  # stand-in path; is_reparse_point is mocked below

        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(tmp_path)}
        )
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        def fake_is_reparse_point(full_path):
            return os.path.basename(full_path) == 'linked_job'

        with _patched_search_module_global(
            'is_reparse_point', side_effect=fake_is_reparse_point
        ):
            module._populate_tree_level(tree.invisibleRootItem(), str(tmp_path))

        root = tree.invisibleRootItem()
        names = [root.child(i).text(0) for i in range(root.childCount())]
        assert 'real_job' in names
        assert 'linked_job' not in names

    def test_reparse_point_root_itself_is_rejected_before_listing(self, tmp_path):
        """The *root* call (from _on_result_selected(), passing a search
        result's path straight through) must validate dir_path itself, not
        just its children — recursive calls via _on_tree_item_expanded()
        only ever reach an already-filtered child, but nothing filtered the
        very first call before this fix (CodeRabbit, PR #315)."""
        customer_dir = tmp_path / 'Z_Customer_Files'
        customer_dir.mkdir()
        linked_root = tmp_path / 'linked_job'
        linked_root.mkdir()
        (linked_root / 'classified.pdf').write_text('secret')

        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(customer_dir)},
        )
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        with _patched_search_module_global('is_reparse_point', return_value=True):
            module._populate_tree_level(tree.invisibleRootItem(), str(linked_root))

        assert tree.invisibleRootItem().childCount() == 0, \
            "a reparse-point root must not be listed at all"

    def test_root_outside_permitted_roots_is_rejected_before_listing(self, tmp_path):
        """Same as above but for a root that isn't a reparse point, just
        outside every configured (non-ITAR) root entirely — e.g. a stale
        index entry pointing at a since-reconfigured or ITAR path
        (CodeRabbit, PR #315)."""
        customer_dir = tmp_path / 'Z_Customer_Files'
        customer_dir.mkdir()
        outside_root = tmp_path / 'itar_customers' / 'secret_job'
        outside_root.mkdir(parents=True)
        (outside_root / 'classified.pdf').write_text('secret')

        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(customer_dir)},
        )
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        module._populate_tree_level(tree.invisibleRootItem(), str(outside_root))

        assert tree.invisibleRootItem().childCount() == 0

    def test_reparse_point_included_when_not_readonly(self, tmp_path):
        real_dir = tmp_path / 'real_job'
        real_dir.mkdir()
        linked_dir = tmp_path / 'linked_job'
        linked_dir.mkdir()

        app_context = self._context(tmp_path, readonly_mode=False)
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        def fake_is_reparse_point(full_path):
            return os.path.basename(full_path) == 'linked_job'

        with _patched_search_module_global(
            'is_reparse_point', side_effect=fake_is_reparse_point
        ):
            module._populate_tree_level(tree.invisibleRootItem(), str(tmp_path))

        root = tree.invisibleRootItem()
        names = [root.child(i).text(0) for i in range(root.childCount())]
        assert 'real_job' in names
        assert 'linked_job' in names, "the exclusion is a read-only restriction, not general"


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

    def _context(self, tmp_path: Path, *, readonly_mode: bool, settings: dict | None = None) -> AppContext:
        return AppContext(
            settings=settings or {},
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
        a_dir = tmp_path / 'subfolder'
        a_dir.mkdir()
        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(tmp_path)}
        )
        module = _make_bare_module(app_context)
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_dir))

        with _patched_qdesktopservices() as qds:
            module._open_item_externally(item)

        qds.openUrl.assert_not_called()

    def test_open_item_externally_opens_a_temp_copy_when_readonly(self, tmp_path):
        """The external viewer must never see the real customer-directory
        path — its own "Save As" / "Recent Files" would hand it straight
        back to the user, undoing every other kiosk restriction."""
        source_dir = tmp_path / 'Z_Customer_Files' / 'Acme' / 'job documents'
        source_dir.mkdir(parents=True)
        a_file = source_dir / 'drawing.pdf'
        a_file.write_text('contents')
        app_context = self._context(
            tmp_path, readonly_mode=True,
            settings={'customer_files_dir': str(tmp_path / 'Z_Customer_Files')},
        )
        module = _make_bare_module(app_context)
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
        a_file = tmp_path / 'drawing.pdf'
        a_file.write_text('contents')
        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(tmp_path)}
        )
        module = _make_bare_module(app_context)
        module.show_error = MagicMock()
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(a_file))

        with _patched_qdesktopservices() as qds, \
                _patched_search_module_global('shutil', copy2=MagicMock(side_effect=OSError("disk full"))):
            module._open_item_externally(item)

        qds.openUrl.assert_not_called()
        module.show_error.assert_called_once()

    def test_open_item_externally_refuses_path_outside_permitted_roots(self, tmp_path):
        """A path whose canonical location isn't under any currently
        configured (non-ITAR) customer/blueprint root must be refused, even
        if it somehow reached this call — the primary guard is the
        reparse-point filter in _populate_tree_level(), this is
        defense-in-depth (CodeRabbit, PR #315)."""
        customer_dir = tmp_path / 'Z_Customer_Files'
        customer_dir.mkdir()
        outside_file = tmp_path / 'itar_customers' / 'secret.pdf'
        outside_file.parent.mkdir()
        outside_file.write_text('classified')
        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(customer_dir)},
        )
        module = _make_bare_module(app_context)
        item = QTreeWidgetItem()
        item.setData(0, Qt.ItemDataRole.UserRole, str(outside_file))

        with _patched_qdesktopservices() as qds:
            module._open_item_externally(item)

        qds.openUrl.assert_not_called()

    def test_print_selected_folder_files_skips_path_outside_permitted_roots(self, tmp_path):
        """Printing reads file content just like opening does, so it needs
        the same permitted-roots check (CodeRabbit, PR #315)."""
        customer_dir = tmp_path / 'Z_Customer_Files'
        customer_dir.mkdir()
        allowed_file = customer_dir / 'drawing.pdf'
        allowed_file.write_text('ok')
        outside_file = tmp_path / 'itar_customers' / 'secret.pdf'
        outside_file.parent.mkdir()
        outside_file.write_text('classified')

        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(customer_dir)},
        )
        module = _make_bare_module(app_context)
        allowed_item = QTreeWidgetItem()
        allowed_item.setData(0, Qt.ItemDataRole.UserRole, str(allowed_file))
        outside_item = QTreeWidgetItem()
        outside_item.setData(0, Qt.ItemDataRole.UserRole, str(outside_file))
        module.folder_tree = MagicMock(selectedItems=MagicMock(
            return_value=[allowed_item, outside_item]
        ))

        with _patched_search_module_global('print_files_with_dialog') as print_dialog:
            module._print_selected_folder_files()

        print_dialog.assert_called_once()
        printed_paths = print_dialog.call_args[0][0]
        assert printed_paths == [str(allowed_file)]

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


class TestReparsePointExclusionOnReadonly:
    """A junction/symlink planted under a permitted customer/blueprint
    folder can target an arbitrary path, including the excluded ITAR
    directory. On a read-only (search-only) install, the folder tree must
    exclude it outright rather than follow it (CodeRabbit, PR #315)."""

    def _context(self, tmp_path: Path, *, readonly_mode: bool, settings: dict | None = None) -> AppContext:
        return AppContext(
            settings=settings or {},
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

    def _make_symlinked_layout(self, tmp_path: Path):
        """Real (non-ITAR) folder with an ordinary subfolder plus a symlink
        pointing at a separate "secret" folder standing in for ITAR data.
        Skips the test if this environment won't allow creating a symlink
        (e.g. no Developer Mode / elevation on this Windows runner)."""
        customer_dir = tmp_path / 'Z_Customer_Files' / 'Acme'
        customer_dir.mkdir(parents=True)
        real_subdir = customer_dir / 'real_job'
        real_subdir.mkdir()
        (real_subdir / 'drawing.pdf').write_text('ok')

        secret_target = tmp_path / 'itar_customers' / 'secret_job'
        secret_target.mkdir(parents=True)
        (secret_target / 'classified.pdf').write_text('secret')

        link_path = customer_dir / 'linked_job'
        try:
            os.symlink(secret_target, link_path, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlink creation not permitted in this environment")
        return customer_dir, real_subdir, link_path

    def test_symlinked_subdirectory_excluded_from_readonly_tree(self, tmp_path):
        customer_dir, real_subdir, link_path = self._make_symlinked_layout(tmp_path)
        app_context = self._context(
            tmp_path, readonly_mode=True,
            settings={'customer_files_dir': str(customer_dir.parent)},
        )
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        module._populate_tree_level(tree.invisibleRootItem(), str(customer_dir))

        root = tree.invisibleRootItem()
        names = [root.child(i).text(0) for i in range(root.childCount())]
        assert 'real_job' in names, "an ordinary subfolder must still show up"
        assert 'linked_job' not in names, "a symlinked subfolder must be excluded, not followed"

    def test_symlinked_subdirectory_included_when_not_readonly(self, tmp_path):
        """The exclusion is a read-only (kiosk) restriction, not a general
        one — the full app has no ITAR-exclusion concern to defend here."""
        customer_dir, real_subdir, link_path = self._make_symlinked_layout(tmp_path)
        app_context = self._context(
            tmp_path, readonly_mode=False,
            settings={'customer_files_dir': str(customer_dir.parent)},
        )
        module = _make_bare_module(app_context)
        tree = QTreeWidget()

        module._populate_tree_level(tree.invisibleRootItem(), str(customer_dir))

        root = tree.invisibleRootItem()
        names = [root.child(i).text(0) for i in range(root.childCount())]
        assert 'linked_job' in names


class TestStrictSearchExcludesReparsePointCustomers:
    """SearchWorker._strict_search()'s own customer-listing loop must also
    exclude reparse points on a read-only install. find_job_folders()'s own
    entry-point guard only protects a "customer" path once it's already
    been constructed and passed in — this is the earlier listing that
    builds that path in the first place, and os.walk()'s followlinks=False
    default doesn't help here since a customer-level link would be the
    walk's own starting point, not something encountered mid-walk
    (CodeRabbit, PR #315)."""

    def _context(self, tmp_path: Path, *, readonly_mode: bool, settings: dict) -> AppContext:
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

    def _run_strict_search(self, base_dir: str, app_context: AppContext) -> list:
        worker = SearchWorker(
            dirs_to_search=[('', base_dir)],
            search_term='', strict_mode=True,
            search_customer=True, search_job=False, search_desc=False, search_drawing=False,
            app_context=app_context,
        )
        results = []
        worker.result_found.connect(results.append)
        with _patched_search_module_global(
            'is_reparse_point', side_effect=lambda p: os.path.basename(p) == 'LinkedCustomer'
        ):
            worker._strict_search()
        return results

    def test_reparse_point_customer_excluded_when_readonly(self, tmp_path):
        base_dir = tmp_path / 'Z_Customer_Files'
        (base_dir / 'Acme' / '10001_Widget').mkdir(parents=True)
        (base_dir / 'LinkedCustomer' / '99999_Secret').mkdir(parents=True)

        app_context = self._context(
            tmp_path, readonly_mode=True, settings={'customer_files_dir': str(base_dir)},
        )
        results = self._run_strict_search(str(base_dir), app_context)

        customers = {r['customer'] for r in results}
        assert 'Acme' in customers
        assert 'LinkedCustomer' not in customers

    def test_reparse_point_customer_included_when_not_readonly(self, tmp_path):
        base_dir = tmp_path / 'Z_Customer_Files'
        (base_dir / 'LinkedCustomer' / '99999_Secret').mkdir(parents=True)

        app_context = self._context(
            tmp_path, readonly_mode=False, settings={'customer_files_dir': str(base_dir)},
        )
        results = self._run_strict_search(str(base_dir), app_context)

        customers = {r['customer'] for r in results}
        assert 'LinkedCustomer' in customers
