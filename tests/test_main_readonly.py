"""Tests for main._is_readonly_install() — read-only (search-only) install detection.

The actual marker-file detection lives in shared.utils.is_kiosk_install()
(main._is_readonly_install() just delegates to it — see its docstring), so
the simulated install layout is anchored on shared.utils's own __file__, not
main's. shared/utils.py sits one level deeper than main.py (app/shared/
vs. app/), hence app_dir / 'shared' / 'utils.py' below.
"""

import main
import shared.utils


def _set_layout(monkeypatch, tmp_path, *, runtime=False, marker=False, flatpak=False):
    app_dir = tmp_path / 'app'
    app_dir.mkdir()
    monkeypatch.setattr(shared.utils, '__file__', str(app_dir / 'shared' / 'utils.py'))
    if runtime:
        (tmp_path / 'runtime').mkdir()
    if marker:
        (tmp_path / 'readonly.marker').write_text('search-only')
    monkeypatch.delenv('FLATPAK_ID', raising=False)
    if flatpak:
        monkeypatch.setenv('FLATPAK_ID', 'io.github.i_machine_things.JobDocs')


class TestIsReadonlyInstall:
    def test_dev_checkout_is_never_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=False, marker=False)
        assert main._is_readonly_install() is False

    def test_embedded_install_without_marker_is_full(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, marker=False)
        assert main._is_readonly_install() is False

    def test_embedded_install_with_marker_is_readonly(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, marker=True)
        assert main._is_readonly_install() is True

    def test_flatpak_is_never_readonly_even_with_marker(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, marker=True, flatpak=True)
        assert main._is_readonly_install() is False


class TestGetConfigDirKioskIsolation:
    """Kiosk and the regular install are separate products meant to coexist
    on one machine (see build_scripts/JobDocs.iss) — get_config_dir() must
    give them different directories, or uninstalling either one would wipe
    the other's settings/history/search index (CodeRabbit, PR #315)."""

    def test_kiosk_install_gets_a_suffixed_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, marker=True)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs Kiosk'

    def test_full_install_gets_the_plain_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=True, marker=False)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs'

    def test_dev_checkout_gets_the_plain_config_dir(self, monkeypatch, tmp_path):
        _set_layout(monkeypatch, tmp_path, runtime=False, marker=False)
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
        config_dir = shared.utils.get_config_dir()
        assert config_dir.name == 'JobDocs'
