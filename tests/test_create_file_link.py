"""Tests for shared/utils.create_file_link — has real filesystem side effects,
kept separate from test_utils.py's pure-function scope."""

import logging

from shared.utils import create_file_link


class TestCreateFileLinkLogsOnError:
    def test_returns_false_and_logs_on_oserror(self, tmp_path, caplog):
        source = tmp_path / 'source.txt'
        source.write_text('hello')
        # Destination directory doesn't exist — os.link/symlink/copy2 all raise OSError.
        dest = tmp_path / 'does_not_exist' / 'dest.txt'

        with caplog.at_level(logging.DEBUG, logger='shared.utils'):
            result = create_file_link(source, dest, link_type='hard')

        # Fallback behavior callers rely on is unchanged...
        assert result is False
        # ...but the failure is no longer silent.
        assert any('create_file_link' in rec.message for rec in caplog.records)

    def test_hard_link_succeeds(self, tmp_path):
        source = tmp_path / 'source.txt'
        source.write_text('hello')
        dest = tmp_path / 'dest.txt'

        assert create_file_link(source, dest, link_type='hard') is True
        assert dest.read_text() == 'hello'

    def test_copy_succeeds(self, tmp_path):
        source = tmp_path / 'source.txt'
        source.write_text('hello')
        dest = tmp_path / 'dest_copy.txt'

        assert create_file_link(source, dest, link_type='copy') is True
        assert dest.read_text() == 'hello'
