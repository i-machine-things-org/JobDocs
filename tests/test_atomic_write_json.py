"""Tests for shared/utils.atomic_write_json — has real filesystem side effects,
kept separate from test_utils.py's pure-function scope."""

import json
import os
import stat

import pytest

from shared.utils import atomic_write_json


class TestAtomicWriteJson:
    def test_writes_json_content(self, tmp_path):
        target = tmp_path / 'settings.json'
        atomic_write_json(target, {'a': 1, 'b': [1, 2, 3]})
        assert json.loads(target.read_text()) == {'a': 1, 'b': [1, 2, 3]}

    def test_overwrites_existing_file(self, tmp_path):
        target = tmp_path / 'settings.json'
        target.write_text('{"old": true}')
        atomic_write_json(target, {'new': True})
        assert json.loads(target.read_text()) == {'new': True}

    def test_no_leftover_temp_file_on_success(self, tmp_path):
        target = tmp_path / 'settings.json'
        atomic_write_json(target, {'a': 1})
        remaining = list(tmp_path.iterdir())
        assert remaining == [target]

    def test_original_file_untouched_if_write_fails_midway(self, tmp_path, monkeypatch):
        target = tmp_path / 'settings.json'
        target.write_text('{"original": true}')

        def _boom(*_args, **_kwargs):
            raise TypeError("not JSON serializable")

        monkeypatch.setattr(json, 'dump', _boom)

        with pytest.raises(TypeError):
            atomic_write_json(target, {'new': True})

        # The original file must still be intact — not truncated/empty —
        # and no leftover temp file should remain.
        assert json.loads(target.read_text()) == {"original": True}
        assert list(tmp_path.iterdir()) == [target]

    def test_no_leftover_temp_file_if_replace_fails(self, tmp_path, monkeypatch):
        import os as os_module

        target = tmp_path / 'settings.json'

        def _boom_replace(*_args, **_kwargs):
            raise OSError("simulated replace failure")

        monkeypatch.setattr(os_module, 'replace', _boom_replace)

        with pytest.raises(OSError):
            atomic_write_json(target, {'a': 1})

        assert not target.exists()
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.skipif(os.name == 'nt', reason="POSIX permission bits only")
    def test_new_file_permissions_respect_umask_not_hardcoded_0600(self, tmp_path):
        # tempfile.mkstemp() hardcodes 0o600 on POSIX regardless of umask.
        # A new atomic_write_json() target must match what plain
        # open(path, 'w') would have produced under the same umask, not be
        # silently narrowed to owner-only.
        old_umask = os.umask(0o022)
        try:
            target = tmp_path / 'settings.json'
            atomic_write_json(target, {'a': 1})
            actual_mode = stat.S_IMODE(target.stat().st_mode)

            control = tmp_path / 'control.json'
            with open(control, 'w') as f:
                f.write('{}')
            expected_mode = stat.S_IMODE(control.stat().st_mode)
        finally:
            os.umask(old_umask)

        assert actual_mode == expected_mode
        assert actual_mode != 0o600

    @pytest.mark.skipif(os.name == 'nt', reason="POSIX permission bits only")
    def test_preserves_existing_file_permissions(self, tmp_path):
        target = tmp_path / 'settings.json'
        target.write_text('{"old": true}')
        os.chmod(target, 0o640)

        atomic_write_json(target, {'new': True})

        assert stat.S_IMODE(target.stat().st_mode) == 0o640

    def test_fsync_called_before_replace(self, tmp_path, monkeypatch):
        calls = []
        original_fsync = os.fsync
        original_replace = os.replace

        def _tracking_fsync(fd):
            calls.append('fsync')
            return original_fsync(fd)

        def _tracking_replace(src, dst):
            calls.append('replace')
            return original_replace(src, dst)

        monkeypatch.setattr(os, 'fsync', _tracking_fsync)
        monkeypatch.setattr(os, 'replace', _tracking_replace)

        target = tmp_path / 'settings.json'
        atomic_write_json(target, {'a': 1})

        assert calls == ['fsync', 'replace']
