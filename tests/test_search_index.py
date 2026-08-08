"""Tests for core/search_index.py — pure sqlite logic, no Qt."""

import sqlite3

import pytest

from core.app_context import AppContext
from core.search_index import SearchIndex


def _make_index(tmp_path):
    return SearchIndex(tmp_path / 'search_index.db')


def _make_app_context(structure):
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
