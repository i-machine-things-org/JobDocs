"""Tests for ModuleLoader.load_module()'s external-plugin relative-import
support.

Regression coverage for a real-world failure: an installed JobDocs plugin
using a relative import for a sibling file (`from . import helpers`) raised
`ModuleNotFoundError: No module named 'plugins'` when launched from an
embedded install, even though the identical plugin loaded fine via
`python main.py` from the dev repo root. The dev-repo case only "worked" by
accident -- the repo root has a real `plugins/` subdirectory, which Python
discovers as an implicit namespace package (PEP 420) purely because it's
sitting under the current working directory, incidentally satisfying the
"plugins" segment of the relative import's dotted name. An embedded install
launched with its cwd set to `app/` (a sibling of `plugins/`, not a parent)
has no such directory to accidentally discover, so the exact same code
genuinely fails there. `ModuleLoader.load_module()` must register the bare
`plugins` package explicitly, not rely on this happening implicitly.
"""

import sys
from pathlib import Path
from textwrap import dedent

from core.module_loader import ModuleLoader


def _write_plugin_with_relative_import(plugin_root: Path, plugin_name: str) -> None:
    """Build a minimal external plugin whose module.py imports a sibling
    file via a relative import, exactly like jobboss_reports.py does in the
    real jobdocs-reports plugin."""
    plugin_dir = plugin_root / plugin_name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / '__init__.py').write_text('')
    (plugin_dir / 'helpers.py').write_text('VALUE = "loaded via relative import"\n')
    (plugin_dir / 'module.py').write_text(dedent('''\
        from core.base_module import BaseModule

        try:
            from . import helpers
        except ImportError:
            import helpers

        class FakePluginModule(BaseModule):
            def get_name(self):
                return "Fake Plugin"

            def get_widget(self):
                return None

            def initialize(self, app_context):
                super().initialize(app_context)

            HELPERS_VALUE = helpers.VALUE
    '''))


def _reset_plugin_sys_modules(plugin_name: str):
    """Remove any sys.modules entries a previous test run (or the accidental
    namespace-package discovery this test guards against) may have left
    behind, so each test starts from a clean slate regardless of pytest's
    own cwd."""
    for key in list(sys.modules):
        if key == 'plugins' or key.startswith(f'plugins.{plugin_name}'):
            del sys.modules[key]


class TestLoadModuleRegistersBarePluginsPackage:
    def test_relative_import_succeeds_without_a_real_plugins_directory_on_cwd(self, tmp_path, monkeypatch):
        # The actual regression: run from a cwd with no "plugins" subfolder
        # of its own, so nothing can accidentally satisfy the relative
        # import's top-level "plugins" segment except the loader's own
        # explicit registration.
        cwd_without_plugins = tmp_path / 'cwd_without_plugins'
        cwd_without_plugins.mkdir()
        monkeypatch.chdir(cwd_without_plugins)

        # Also strip this repo's own root from sys.path for the duration of
        # the call below: it's on sys.path already (needed just to import
        # ModuleLoader for this test), and this repo root has a real
        # plugins/ directory Python would otherwise discover as an implicit
        # namespace package -- accidentally satisfying the relative import
        # even on the old, buggy loader and masking the exact regression
        # this test exists to catch (confirmed: without this, this test
        # keeps passing even with the fix reverted).
        repo_root = str(Path(__file__).resolve().parent.parent)
        monkeypatch.setattr(sys, 'path', [p for p in sys.path if p != repo_root])

        plugin_root = tmp_path / 'plugins'
        _write_plugin_with_relative_import(plugin_root, 'fake-plugin')
        _reset_plugin_sys_modules('fake-plugin')

        loader = ModuleLoader(Path('modules'), plugins_dir=plugin_root)
        loader.discover_modules()
        cls = loader.load_module('fake-plugin')

        assert cls.__name__ == 'FakePluginModule'
        assert cls.HELPERS_VALUE == 'loaded via relative import'

    def test_bare_plugins_package_is_explicitly_registered(self, tmp_path, monkeypatch):
        # Distinguishes "the loader explicitly created it" from "Python
        # happened to discover a real plugins/ directory on its own" --
        # only the loader's own registration has an empty __path__.
        cwd_without_plugins = tmp_path / 'cwd_without_plugins'
        cwd_without_plugins.mkdir()
        monkeypatch.chdir(cwd_without_plugins)

        plugin_root = tmp_path / 'plugins'
        _write_plugin_with_relative_import(plugin_root, 'fake-plugin-2')
        _reset_plugin_sys_modules('fake-plugin-2')

        loader = ModuleLoader(Path('modules'), plugins_dir=plugin_root)
        loader.discover_modules()
        loader.load_module('fake-plugin-2')

        assert 'plugins' in sys.modules
        assert list(sys.modules['plugins'].__path__) == []

    def test_does_not_clobber_an_already_registered_plugins_module(self, tmp_path, monkeypatch):
        # If something else already registered "plugins" first, the loader
        # must not stomp on it -- only fill it in when genuinely absent.
        cwd_without_plugins = tmp_path / 'cwd_without_plugins'
        cwd_without_plugins.mkdir()
        monkeypatch.chdir(cwd_without_plugins)

        plugin_root = tmp_path / 'plugins'
        _write_plugin_with_relative_import(plugin_root, 'fake-plugin-3')
        _reset_plugin_sys_modules('fake-plugin-3')

        import types
        sentinel = types.ModuleType('plugins')
        sentinel.__path__ = ['/some/preexisting/path']
        sys.modules['plugins'] = sentinel

        try:
            loader = ModuleLoader(Path('modules'), plugins_dir=plugin_root)
            loader.discover_modules()
            loader.load_module('fake-plugin-3')

            assert sys.modules['plugins'] is sentinel
        finally:
            del sys.modules['plugins']
