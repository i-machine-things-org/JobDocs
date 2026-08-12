"""Tests for main._is_readonly_install() — read-only (search-only) install detection."""

import main


def _set_layout(monkeypatch, tmp_path, *, runtime=False, marker=False, flatpak=False):
    app_dir = tmp_path / 'app'
    app_dir.mkdir()
    monkeypatch.setattr(main, '__file__', str(app_dir / 'main.py'))
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
