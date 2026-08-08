"""Tests for shared/utils.atomic_write_json — has real filesystem side effects,
kept separate from test_utils.py's pure-function scope."""

import json

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
