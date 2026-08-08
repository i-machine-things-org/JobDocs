"""Tests for core/search_index.py — pure sqlite logic, no Qt."""

import os
import sqlite3

import pytest

from core.app_context import AppContext
from core.search_index import SearchIndex


def _make_index(tmp_path):
    return SearchIndex(tmp_path / 'search_index.db')


def _make_app_context(structure='{customer}/{job_folder}'):
    return AppContext(
        settings={'job_folder_structure': structure},
        history={},
        config_dir=None,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )


def _insert_job(
    index, *, prefix='', customer='Acme', job_number='12345',
    description='Bracket', drawings='DWG-A', path=None, mtime=1.0,
):
    with sqlite3.connect(str(index._db_path)) as conn:
        conn.execute(
            """INSERT INTO jobs (prefix, customer, job_number, description, drawings, path, mtime)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (prefix, customer, job_number, description, drawings, path or f'C:/{customer}/{job_number}', mtime),
        )


class TestFindJobByNumber:
    def test_no_match_returns_none(self, tmp_path):
        index = _make_index(tmp_path)
        assert index.find_job_by_number('99999') is None

    def test_exact_match(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index, job_number='12345', customer='Acme', path='C:/Acme/12345_Bracket')
        match = index.find_job_by_number('12345')
        assert match == {'customer': 'Acme', 'path': 'C:/Acme/12345_Bracket'}

    def test_match_is_case_insensitive(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index, job_number='ab-100', customer='Acme', path='C:/Acme/ab-100')
        assert index.find_job_by_number('AB-100') is not None

    def test_substring_does_not_match(self, tmp_path):
        # find_job_by_number must be an exact match, unlike search_jobs' LIKE search.
        index = _make_index(tmp_path)
        _insert_job(index, job_number='12345', customer='Acme')
        assert index.find_job_by_number('1234') is None
        assert index.find_job_by_number('123456') is None

    def test_itar_prefix_decorates_customer(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index, prefix='ITAR', job_number='12345', customer='Acme', path='C:/ITAR/Acme/12345')
        match = index.find_job_by_number('12345')
        assert match['customer'] == '[ITAR] Acme'

    def test_returns_most_recent_on_multiple_matches(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index, job_number='12345', customer='Old', path='C:/Old/12345', mtime=1.0)
        _insert_job(index, job_number='12345', customer='New', path='C:/New/12345', mtime=2.0)
        match = index.find_job_by_number('12345')
        assert match['customer'] == 'New'

    def test_query_failure_raises_instead_of_returning_none(self, tmp_path):
        # Callers rely on this to distinguish a failed lookup (fall back to a
        # filesystem scan) from a confirmed no-match (safe to treat as unique).
        index = _make_index(tmp_path)
        with sqlite3.connect(str(index._db_path)) as conn:
            conn.execute("DROP TABLE jobs")
        with pytest.raises(sqlite3.Error):
            index.find_job_by_number('12345')


class TestIsPopulated:
    def test_empty_index(self, tmp_path):
        index = _make_index(tmp_path)
        assert index.is_populated() is False

    def test_populated_after_insert(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index)
        assert index.is_populated() is True


class TestIsFullyCovered:
    """Regression coverage for #293, finding 2: search_jobs()/search_bp() returning
    zero results shouldn't always trigger a full filesystem walk — only when the
    index genuinely hasn't caught up with what's on disk yet.
    """

    def test_no_configured_dirs_is_vacuously_covered(self, tmp_path):
        index = _make_index(tmp_path)
        assert index.is_fully_covered([], []) is True

    def test_unindexed_customer_dir_is_not_covered(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme').mkdir(parents=True)
        index = _make_index(tmp_path)
        # Nothing has ever been indexed — Acme exists on disk but has no
        # indexed_dirs row, so a zero-result search can't be trusted yet.
        assert index.is_fully_covered([('', str(cf_root))], []) is False

    def test_covered_after_successful_update(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context()
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)
        assert index.is_fully_covered([('', str(cf_root))], []) is True

    def test_new_customer_added_after_last_update_is_not_covered(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context()
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        # A brand-new customer folder shows up on disk after the last index run
        # (e.g. the background indexer hasn't picked it up yet).
        (cf_root / 'NewCo' / '99999_Widget').mkdir(parents=True)
        assert index.is_fully_covered([('', str(cf_root))], []) is False

    def test_bp_dirs_checked_independently_of_cf_dirs(self, tmp_path):
        bp_root = tmp_path / 'blueprints'
        (bp_root / 'Acme').mkdir(parents=True)
        index = _make_index(tmp_path)
        assert index.is_fully_covered([], [('BP', str(bp_root))]) is False

    def test_missing_base_dir_does_not_break_coverage_check(self, tmp_path):
        # A configured directory that doesn't exist on disk shouldn't be
        # treated as "not covered" — there's nothing under it to miss.
        index = _make_index(tmp_path)
        missing_dir = str(tmp_path / 'does_not_exist')
        assert index.is_fully_covered([('', missing_dir)], []) is True

    def test_query_failure_returns_false(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme').mkdir(parents=True)
        index = _make_index(tmp_path)
        with sqlite3.connect(str(index._db_path)) as conn:
            conn.execute("DROP TABLE indexed_dirs")
        assert index.is_fully_covered([('', str(cf_root))], []) is False


def _assert_no_recursive_walk_needed(monkeypatch):
    """Fail the test if os.walk is called — is_fully_covered must only use
    shallow os.listdir() calls, never a recursive directory walk."""
    def _fail_on_walk(*_args, **_kwargs):
        raise AssertionError("is_fully_covered must not perform a recursive os.walk")
    monkeypatch.setattr(os, 'walk', _fail_on_walk)


class TestIsFullyCoveredDoesNotWalk:
    def test_covered_check_uses_only_shallow_listdir(self, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context()
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        _assert_no_recursive_walk_needed(monkeypatch)
        assert index.is_fully_covered([('', str(cf_root))], []) is True
