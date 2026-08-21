"""Tests for main._is_readonly_install() — read-only (search-only) install detection.

The actual detection lives in shared.utils.is_kiosk_install()
(main._is_readonly_install() just delegates to it — see its docstring), so
the simulated install layout is anchored on shared.utils's own __file__, not
main's. shared/utils.py sits one level deeper than main.py (app/shared/
vs. app/), hence app_dir / 'shared' / 'utils.py' below. main.__file__ is
patched too, for _apply_kiosk_dirs_override() (defined in main.py itself,
so it resolves kiosk_dirs.json relative to main's own __file__).

kiosk_build.marker is baked into the Kiosk installer's payload at build time
(build_scripts/JobDocs.iss's [Files] section), not written post-install like
the old readonly.marker was — so simulating "a Kiosk install" here means
creating that file in the fake app/shared/ dir, not the install root.
"""

import platform

import main
import shared.utils


def _set_layout(monkeypatch, tmp_path, *, runtime=False, kiosk=False, flatpak=False):
    monkeypatch.setattr(platform, 'system', lambda: 'Windows')
    app_dir = tmp_path / 'app'
    (app_dir / 'shared').mkdir(parents=True)
    monkeypatch.setattr(shared.utils, '__file__', str(app_dir / 'shared' / 'utils.py'))
    monkeypatch.setattr(main, '__file__', str(app_dir / 'main.py'))
    if runtime:
        (tmp_path / 'runtime').mkdir()
    if kiosk:
        (app_dir / 'shared' / 'kiosk_build.marker').write_text('kiosk')
    monkeypatch.delenv('FLATPAK_ID', raising=False)
    if flatpak:
        monkeypatch.setenv('FLATPAK_ID', 'io.github.i_machine_things.JobDocs')


class TestIsReadonlyInstall:
    def test_dev_checkout_is_never_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=False, kiosk=False)
        assert main._is_readonly_install() is False

    def test_embedded_full_install_is_not_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=False)
        assert main._is_readonly_install() is False

    def test_embedded_kiosk_install_is_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        assert main._is_readonly_install() is True

    def test_flatpak_is_never_readonly_even_when_kiosk(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True, flatpak=True)
        assert main._is_readonly_install() is False

    def test_deleting_legacy_readonly_marker_does_not_disable_kiosk(self, monkeypatch, tmp_path):
        """kiosk_build.marker (baked in at build time) is the only signal that
        matters now — a stray install-root readonly.marker left over from an
        older installer (or one a user creates by hand) must not affect the
        answer (CodeRabbit, PR #315)."""
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        (tmp_path / 'readonly.marker').write_text('search-only')
        assert main._is_readonly_install() is True

    def test_legacy_readonly_marker_alone_does_not_make_a_full_install_readonly(
        self, monkeypatch, tmp_path
    ):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=False)
        (tmp_path / 'readonly.marker').write_text('search-only')
        assert main._is_readonly_install() is False


class TestGetConfigDirKioskIsolation:
    """Kiosk and the regular install are separate products meant to coexist
    on one machine (see build_scripts/JobDocs.iss) — get_config_dir() must
    give them different directories, or uninstalling either one would wipe
    the other's settings/history/search index (CodeRabbit, PR #315)."""

    def test_kiosk_install_gets_a_suffixed_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs Kiosk'

    def test_full_install_gets_the_plain_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=False)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs'

    def test_dev_checkout_gets_the_plain_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=False, kiosk=False)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs'


class _FakeMainWindow:
    """Stand-in exposing just what _apply_kiosk_dirs_override() reads."""
    _KIOSK_DIR_SETTING_KEYS = main.JobDocsMainWindow._KIOSK_DIR_SETTING_KEYS

    def __init__(self, readonly_mode):
        self.readonly_mode = readonly_mode


class TestApplyKioskDirsOverride:
    """JobDocs Kiosk has no Settings UI and doesn't ship the OOBE wizard —
    its directories are configured once at install time
    (build_scripts/JobDocs.iss's custom wizard pages write kiosk_dirs.json)
    and must win over whatever's in settings.json on every launch."""

    def test_kiosk_dirs_json_overrides_settings_when_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        (tmp_path / 'kiosk_dirs.json').write_text(
            '{"customer_files_dir": "Z:\\\\Customers", '
            '"itar_customer_files_dir": "", '
            '"blueprints_dir": "Z:\\\\Blueprints", '
            '"itar_blueprints_dir": ""}'
        )
        settings = {'customer_files_dir': 'C:\\stale', 'blueprints_dir': 'C:\\also_stale'}

        result = main.JobDocsMainWindow._apply_kiosk_dirs_override(_FakeMainWindow(True), settings)

        assert result['customer_files_dir'] == 'Z:\\Customers'
        assert result['blueprints_dir'] == 'Z:\\Blueprints'
        assert result['itar_customer_files_dir'] == ''

    def test_no_override_when_not_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=False)
        (tmp_path / 'kiosk_dirs.json').write_text('{"customer_files_dir": "Z:\\\\Customers"}')
        settings = {'customer_files_dir': 'C:\\real_setting'}

        result = main.JobDocsMainWindow._apply_kiosk_dirs_override(_FakeMainWindow(False), settings)

        assert result['customer_files_dir'] == 'C:\\real_setting'

    def test_no_kiosk_dirs_file_leaves_settings_unchanged(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        settings = {'customer_files_dir': 'C:\\unchanged'}

        result = main.JobDocsMainWindow._apply_kiosk_dirs_override(_FakeMainWindow(True), settings)

        assert result['customer_files_dir'] == 'C:\\unchanged'

    def test_malformed_kiosk_dirs_json_leaves_settings_unchanged(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, kiosk=True)
        (tmp_path / 'kiosk_dirs.json').write_text('{not valid json')
        settings = {'customer_files_dir': 'C:\\unchanged'}

        result = main.JobDocsMainWindow._apply_kiosk_dirs_override(_FakeMainWindow(True), settings)

        assert result['customer_files_dir'] == 'C:\\unchanged'
