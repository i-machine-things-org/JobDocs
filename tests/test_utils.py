"""Tests for shared/utils.py — pure functions only (no Qt, no filesystem side-effects)."""

import os

import shared.utils as utils
from shared.utils import (
    is_blueprint_file,
    parse_job_numbers,
    sanitize_filename,
    get_os_text,
    get_next_number,
    is_reparse_point,
)


# ---------------------------------------------------------------------------
# is_blueprint_file
# ---------------------------------------------------------------------------

class TestIsBlueprintFile:
    EXTS = ('.pdf', '.dwg', '.dxf')

    def test_matching_extension(self):
        assert is_blueprint_file('drawing.pdf', self.EXTS) is True

    def test_matching_extension_uppercase(self):
        assert is_blueprint_file('DRAWING.PDF', self.EXTS) is True

    def test_non_blueprint_extension(self):
        assert is_blueprint_file('photo.jpg', self.EXTS) is False

    def test_no_extension(self):
        assert is_blueprint_file('README', self.EXTS) is False

    def test_empty_extensions_list(self):
        assert is_blueprint_file('drawing.pdf', []) is False


# ---------------------------------------------------------------------------
# parse_job_numbers
# ---------------------------------------------------------------------------

class TestParseJobNumbers:
    def test_single_number(self):
        assert parse_job_numbers('5') == ['5']

    def test_comma_separated(self):
        assert parse_job_numbers('1,2,3') == ['1', '2', '3']

    def test_range(self):
        assert parse_job_numbers('1-5') == ['1', '2', '3', '4', '5']

    def test_mixed(self):
        assert parse_job_numbers('1,3-5,7') == ['1', '3', '4', '5', '7']

    def test_whitespace_tolerance(self):
        assert parse_job_numbers(' 1 , 2 , 3 ') == ['1', '2', '3']

    def test_empty_string(self):
        assert parse_job_numbers('') == []

    def test_non_numeric_passthrough(self):
        # Non-numeric parts that can't be parsed as ranges pass through as-is
        result = parse_job_numbers('ABC')
        assert result == ['ABC']


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_clean_filename_unchanged(self):
        assert sanitize_filename('drawing_rev1.pdf') == 'drawing_rev1.pdf'

    def test_replaces_colon(self):
        assert sanitize_filename('job:123') == 'job_123'

    def test_replaces_all_invalid_chars(self):
        result = sanitize_filename('<file>/name\\test|bad?name*here"end')
        assert all(c not in result for c in r'<>:"/\|?*')

    def test_empty_string(self):
        assert sanitize_filename('') == ''


# ---------------------------------------------------------------------------
# get_os_text
# ---------------------------------------------------------------------------

class TestGetOsText:
    def test_known_key_returns_string(self):
        result = get_os_text('folder_term')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_key_returns_empty(self):
        assert get_os_text('nonexistent_key') == ''

    def test_path_sep_is_single_char(self):
        assert len(get_os_text('path_sep')) == 1


# ---------------------------------------------------------------------------
# get_next_number
# ---------------------------------------------------------------------------

class TestGetNextNumber:
    def test_empty_history_returns_start(self):
        assert get_next_number({}, 'job') == '10000'

    def test_increments_from_highest(self):
        history = {'recent_jobs': [{'job_number': '10005'}, {'job_number': '10002'}]}
        assert get_next_number(history, 'job') == '10006'

    def test_quote_uses_separate_history(self):
        # Jobs and quotes are tracked independently; high job numbers don't affect quote sequence.
        history = {
            'recent_jobs': [{'job_number': '10099'}],
            'recent_quotes': [{'quote_number': 'Q10200'}],
        }
        assert get_next_number(history, 'quote') == '10201'
        assert get_next_number(history, 'job') == '10100'

    def test_non_numeric_entries_ignored(self):
        history = {'recent_jobs': [{'job_number': 'N/A'}, {'job_number': '10003'}]}
        assert get_next_number(history, 'job') == '10004'

    def test_unknown_type_returns_start(self):
        assert get_next_number({}, 'unknown') == '10000'


# ---------------------------------------------------------------------------
# is_reparse_point
# ---------------------------------------------------------------------------

class _FakeKernel32:
    def __init__(self, attrs=None, raises=None):
        self._attrs = attrs
        self._raises = raises

    def GetFileAttributesW(self, _path):
        if self._raises is not None:
            raise self._raises
        return self._attrs


class TestIsReparsePoint:
    """A junction/symlink under a permitted customer/blueprint folder can
    target an excluded ITAR directory. This must fail closed: a
    GetFileAttributesW lookup failure on Windows is treated as a reparse
    point rather than falling through to os.path.islink(), which doesn't
    reliably detect junctions/mount points there (CodeRabbit, PR #315)."""

    def _set_windows(self, monkeypatch, attrs=None, raises=None):
        monkeypatch.setattr(os, 'name', 'nt')
        fake_windll = type('FakeWindll', (), {'kernel32': _FakeKernel32(attrs=attrs, raises=raises)})()
        monkeypatch.setattr(utils.ctypes, 'windll', fake_windll, raising=False)

    def test_windows_reparse_bit_set(self, monkeypatch):
        self._set_windows(monkeypatch, attrs=0x400)
        assert is_reparse_point(r'Z:\link') is True

    def test_windows_ordinary_directory(self, monkeypatch):
        self._set_windows(monkeypatch, attrs=0x10)  # FILE_ATTRIBUTE_DIRECTORY
        assert is_reparse_point(r'Z:\dir') is False

    def test_windows_invalid_file_attributes_fails_closed(self, monkeypatch):
        self._set_windows(monkeypatch, attrs=-1)  # INVALID_FILE_ATTRIBUTES
        assert is_reparse_point(r'Z:\missing') is True

    def test_windows_api_exception_fails_closed(self, monkeypatch):
        self._set_windows(monkeypatch, raises=OSError('access denied'))
        assert is_reparse_point(r'Z:\denied') is True

    def test_windows_missing_api_binding_fails_closed(self, monkeypatch):
        self._set_windows(monkeypatch, raises=AttributeError('kernel32 unavailable'))
        assert is_reparse_point(r'Z:\denied') is True

    def test_non_windows_uses_islink(self, monkeypatch):
        monkeypatch.setattr(os, 'name', 'posix')
        monkeypatch.setattr(utils.os.path, 'islink', lambda p: True)
        assert is_reparse_point('/mnt/link') is True

    def test_non_windows_real_directory_is_not_a_reparse_point(self, monkeypatch, tmp_path):
        monkeypatch.setattr(os, 'name', 'posix')
        assert is_reparse_point(str(tmp_path)) is False
