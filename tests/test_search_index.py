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


class TestSearchJobsFindsPoAndNonPoFolders:
    """End-to-end: real AppContext.find_job_folders() feeding a real SearchIndex.update(),
    over an on-disk tree that mixes PO-nested and non-PO job folders. Regression coverage
    for #295 — search_jobs() must return a job regardless of whether it lives inside a PO
    folder or directly under the customer's job-documents dir.
    """

    def test_search_jobs_returns_jobs_in_and_out_of_po_folders(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        (customer_path / 'job documents' / '11111_LegacyBracket').mkdir(parents=True)
        (customer_path / 'job documents' / 'PO-1001' / '22222_NewShaft').mkdir(parents=True)

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        legacy_results = index.search_jobs('11111', search_customer=False)
        new_results = index.search_jobs('22222', search_customer=False)

        assert [r['job_number'] for r in legacy_results] == ['11111']
        assert [r['job_number'] for r in new_results] == ['22222']
        assert legacy_results[0]['path'].endswith('11111_LegacyBracket')
        assert new_results[0]['path'].endswith('22222_NewShaft')
        # A job outside any PO folder has no PO number; a job nested inside
        # "PO-1001" reports '1001' with the literal "PO-" prefix stripped.
        assert legacy_results[0]['po_number'] == ''
        assert new_results[0]['po_number'] == '1001'

    def test_job_number_search_after_update(self, tmp_path):
        # search_jobs by job number (not just customer) picks up both kinds of folder.
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        (customer_path / 'job documents' / '33333_Widget').mkdir(parents=True)
        (customer_path / 'job documents' / 'PO-2002' / '44444_Gadget').mkdir(parents=True)

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        assert index.find_job_by_number('33333') is not None
        assert index.find_job_by_number('44444') is not None


class TestMigrationToV4AddsPoNumber:
    def test_existing_v3_database_gains_po_number_column(self, tmp_path):
        # Simulate a database created before the po_number column existed
        # (schema v3: quotes table present, no po_number) and confirm opening
        # it with the current SearchIndex adds the column, preserves existing
        # rows (defaulting po_number to ''), and forces a re-index so already
        # -indexed customers pick up po_number on the next update() call.
        db_path = tmp_path / 'search_index.db'
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE jobs (
                id          INTEGER PRIMARY KEY,
                prefix      TEXT    NOT NULL DEFAULT '',
                customer    TEXT    NOT NULL,
                job_number  TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                drawings    TEXT    NOT NULL DEFAULT '',
                path        TEXT    NOT NULL,
                mtime       REAL    NOT NULL,
                UNIQUE(prefix, path)
            );
            CREATE TABLE indexed_dirs (
                dir_path    TEXT    NOT NULL,
                prefix      TEXT    NOT NULL DEFAULT '',
                kind        TEXT    NOT NULL DEFAULT '',
                mtime       REAL    NOT NULL,
                indexed_at  REAL    NOT NULL,
                PRIMARY KEY (dir_path, prefix, kind)
            );
            INSERT INTO jobs (prefix, customer, job_number, description, drawings, path, mtime)
                VALUES ('', 'Acme', '12345', 'Bracket', '', 'C:/Acme/12345', 1.0);
            INSERT INTO indexed_dirs (dir_path, prefix, kind, mtime, indexed_at)
                VALUES ('C:/Acme', '', 'cf', 1.0, 1.0);
            PRAGMA user_version = 3;
        """)
        conn.commit()
        conn.close()

        SearchIndex(db_path)

        conn = sqlite3.connect(str(db_path))
        cols = [row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        cf_dirs_remaining = conn.execute(
            "SELECT COUNT(*) FROM indexed_dirs WHERE kind='cf'"
        ).fetchone()[0]
        job_row = conn.execute("SELECT job_number, po_number FROM jobs").fetchone()

        assert 'po_number' in cols
        assert version == 4
        assert cf_dirs_remaining == 0  # forced re-index so po_number gets backfilled
        assert job_row == ('12345', '')

    def test_v3_database_with_po_number_already_present_still_forces_reindex(self, tmp_path):
        # Edge case: a database somehow reached user_version=3 with the
        # po_number column already present (e.g. state reached outside the
        # normal migration path). The "column already exists" branch must
        # still clear cf indexed_dirs markers — otherwise customers indexed
        # before po_number existed keep an empty value forever, since
        # update()'s mtime precheck would skip re-scanning them.
        db_path = tmp_path / 'search_index2.db'
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE jobs (
                id          INTEGER PRIMARY KEY,
                prefix      TEXT    NOT NULL DEFAULT '',
                customer    TEXT    NOT NULL,
                job_number  TEXT    NOT NULL DEFAULT '',
                description TEXT    NOT NULL DEFAULT '',
                drawings    TEXT    NOT NULL DEFAULT '',
                po_number   TEXT    NOT NULL DEFAULT '',
                path        TEXT    NOT NULL,
                mtime       REAL    NOT NULL,
                UNIQUE(prefix, path)
            );
            CREATE TABLE indexed_dirs (
                dir_path    TEXT    NOT NULL,
                prefix      TEXT    NOT NULL DEFAULT '',
                kind        TEXT    NOT NULL DEFAULT '',
                mtime       REAL    NOT NULL,
                indexed_at  REAL    NOT NULL,
                PRIMARY KEY (dir_path, prefix, kind)
            );
            INSERT INTO jobs (prefix, customer, job_number, description, drawings, po_number, path, mtime)
                VALUES ('', 'Acme', '12345', 'Bracket', '', '', 'C:/Acme/12345', 1.0);
            INSERT INTO indexed_dirs (dir_path, prefix, kind, mtime, indexed_at)
                VALUES ('C:/Acme', '', 'cf', 1.0, 1.0);
            PRAGMA user_version = 3;
        """)
        conn.commit()
        conn.close()

        SearchIndex(db_path)

        conn = sqlite3.connect(str(db_path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        cf_dirs_remaining = conn.execute(
            "SELECT COUNT(*) FROM indexed_dirs WHERE kind='cf'"
        ).fetchone()[0]

        assert version == 4
        assert cf_dirs_remaining == 0  # forced re-index despite column already existing


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
