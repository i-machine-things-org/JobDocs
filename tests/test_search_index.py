"""Tests for core/search_index.py — pure sqlite logic, no Qt."""

import os
import shutil
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
    description='Bracket', drawings='DWG-A', path=None, mtime=1.0, po_number='',
):
    with sqlite3.connect(str(index._db_path)) as conn:
        conn.execute(
            """INSERT INTO jobs (prefix, customer, job_number, description, drawings, po_number, path, mtime)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                prefix, customer, job_number, description, drawings, po_number,
                path or f'C:/{customer}/{job_number}', mtime,
            ),
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


class TestClearAll:
    """clear_all() must wipe indexed_dirs too, not just jobs/bp_files/quotes
    -- otherwise update() would still see fresh mtimes recorded there and
    skip re-scanning directories on the very rebuild meant to force it."""

    def test_wipes_jobs_and_is_populated_goes_false(self, tmp_path):
        index = _make_index(tmp_path)
        _insert_job(index)
        assert index.is_populated() is True

        index.clear_all()

        assert index.is_populated() is False

    def test_wipes_indexed_dirs_staleness_bookkeeping(self, tmp_path):
        index = _make_index(tmp_path)
        with sqlite3.connect(str(index._db_path)) as conn:
            conn.execute(
                "INSERT INTO indexed_dirs (dir_path, prefix, kind, mtime, indexed_at)"
                " VALUES ('C:/Acme', '', 'cf', 1.0, 1.0)"
            )

        index.clear_all()

        with sqlite3.connect(str(index._db_path)) as conn:
            row = conn.execute("SELECT COUNT(*) FROM indexed_dirs").fetchone()
        assert row[0] == 0

    def test_returns_false_when_database_is_locked(self, tmp_path, monkeypatch):
        # CodeRabbit finding, PR #328: the caller (rebuild_search_index())
        # must be able to tell "nothing was actually cleared" from success
        # -- silently returning as if it had would let it proceed straight
        # to an ordinary incremental update() and call that a rebuild.
        index = _make_index(tmp_path)

        def _raise_locked():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(index, '_connect', _raise_locked)

        assert index.clear_all() is False

    def test_reraises_other_operational_errors(self, tmp_path, monkeypatch):
        index = _make_index(tmp_path)

        def _raise_other():
            raise sqlite3.OperationalError("disk I/O error")

        monkeypatch.setattr(index, '_connect', _raise_other)

        with pytest.raises(sqlite3.OperationalError):
            index.clear_all()


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

    def test_new_job_in_existing_po_container_is_not_covered(self, tmp_path):
        # A customer directory's own mtime only reflects changes to its
        # *direct* children -- adding a job folder inside an already-indexed
        # PO-container subdirectory changes that container's mtime, not the
        # customer dir's. is_fully_covered() must check previously-recorded
        # containers too, not just the customer-level indexed_dirs row
        # (CodeRabbit finding, PR #305 independent review).
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        po_dir = customer_path / 'job documents' / 'PO-1001'
        (po_dir / '11111_LegacyBracket').mkdir(parents=True)

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)
        assert index.is_fully_covered([('', str(cf_root))], []) is True

        # A new job shows up inside the existing PO-1001 container after the
        # last index run -- customer_path itself is untouched.
        (po_dir / '22222_NewShaft').mkdir(parents=True)
        assert index.is_fully_covered([('', str(cf_root))], []) is False

    def test_new_job_in_initially_empty_po_container_is_not_covered(self, tmp_path):
        # CodeRabbit finding on PR #316: update() used to derive container_dirs
        # only from *found* jobs' ancestor paths, so a PO folder that matched
        # the naming convention but held zero jobs at index time was never
        # recorded in indexed_dirs at all. A job created in it afterward left
        # is_fully_covered() with no row to compare a changed mtime against,
        # so it kept trusting a zero-result search. find_job_folders() now
        # reports every examined PO container via its `containers` out-param,
        # whether or not it currently holds any jobs.
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        po_dir = customer_path / 'job documents' / 'PO-1001'
        po_dir.mkdir(parents=True)  # PO folder exists but is empty

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)
        assert index.is_fully_covered([('', str(cf_root))], []) is True

        # A job is created inside the previously-empty PO-1001 container.
        (po_dir / '22222_NewShaft').mkdir(parents=True)
        assert index.is_fully_covered([('', str(cf_root))], []) is False

    def test_new_job_in_po_container_missing_its_subdir_is_not_covered(self, tmp_path):
        # CodeRabbit finding on PR #316 (a gap in the fix directly above): the
        # prior fix only appended po_path to `containers` *after* confirming
        # sub_path exists. For a structure with a literal subdirectory between
        # the PO folder and {job_folder} (post_po non-empty, e.g. "job
        # documents"), a PO folder that exists but doesn't have that
        # subdirectory yet (truly empty, not even the container dir) was never
        # recorded at all -- not just stale, invisible to is_fully_covered().
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        po_dir = customer_path / 'PO-1001'
        po_dir.mkdir(parents=True)  # PO-1001 exists but has no "job documents" yet

        ctx = _make_app_context('{customer}/PO-{po_number}/job documents/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)
        assert index.is_fully_covered([('', str(cf_root))], []) is True

        # "job documents" is created inside PO-1001, with a job inside it.
        (po_dir / 'job documents' / '22222_NewShaft').mkdir(parents=True)
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


class TestAddJobAndAddQuote:
    """Regression coverage for review finding 1 (#298): a job/quote created
    mid-session must be searchable immediately, not just after the next full
    index build. is_fully_covered() only proves a customer dir was indexed
    *once*, not that it's fresh, so search_jobs()/search_quotes() finding the
    new row directly is what actually closes the gap — add_job()/add_quote()
    are what job/quote creation call to make that happen.
    """

    def test_add_job_makes_new_job_immediately_searchable(self, tmp_path):
        index = _make_index(tmp_path)
        assert index.search_jobs('99999') == []

        index.add_job('', 'Acme', '99999', 'New Widget', ['DWG-A'], 'C:/Acme/99999_NewWidget')

        results = index.search_jobs('99999')
        assert len(results) == 1
        assert results[0]['customer'] == 'Acme'
        assert results[0]['job_number'] == '99999'
        assert results[0]['path'] == 'C:/Acme/99999_NewWidget'

    def test_add_job_reproduces_and_fixes_mid_session_scenario(self, tmp_path):
        """The exact scenario from the review finding: a customer directory
        is fully indexed once, then a new job is created for that same
        customer later in the same session (no second background index
        run). Before add_job() was wired into job creation, search_jobs()
        would return 0 results for the new job's number and (in
        modules/search/module.py) is_fully_covered() would then
        incorrectly report the search as trustworthy, since it only checks
        that 'Acme' was indexed at some point — never that a new job
        folder was added afterwards.
        """
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'Acme' / '12345_Bracket').mkdir(parents=True)
        ctx = _make_app_context()
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        # Sanity check: the pre-existing job is indexed, and the customer
        # dir is (correctly) reported as fully covered at this point.
        assert index.search_jobs('12345') != []
        assert index.is_fully_covered([('', str(cf_root))], []) is True

        # A new job for the same, already-indexed customer is created mid-
        # session — mirroring create_single_job() calling add_job() right
        # after making the folder on disk, without waiting for a re-index.
        (cf_root / 'Acme' / '99999_NewWidget').mkdir(parents=True)
        index.add_job('', 'Acme', '99999', 'New Widget', [], str(cf_root / 'Acme' / '99999_NewWidget'))

        # The new job is found directly via search_jobs() now — the search
        # module never even reaches the is_fully_covered() 0-result check
        # for this query, so the staleness in is_fully_covered() itself no
        # longer matters for this case.
        results = index.search_jobs('99999')
        assert len(results) == 1
        assert results[0]['job_number'] == '99999'

    def test_add_job_upserts_on_reindex(self, tmp_path):
        # A later full re-index shouldn't produce a duplicate row for a job
        # that was already added incrementally at the same path.
        index = _make_index(tmp_path)
        index.add_job('', 'Acme', '99999', 'New Widget', [], 'C:/Acme/99999_NewWidget', mtime=1.0)
        index.add_job('', 'Acme', '99999', 'New Widget', [], 'C:/Acme/99999_NewWidget', mtime=2.0)
        results = index.search_jobs('99999')
        assert len(results) == 1

    def test_add_job_persists_po_number(self, tmp_path):
        # Regression test (CodeRabbit, PR #317 promotion review): add_job()
        # used to omit po_number from its INSERT entirely, so a job created
        # mid-session was indexed with a blank PO number until the next full
        # re-index.
        index = _make_index(tmp_path)
        index.add_job(
            '', 'Acme', '99999', 'New Widget', [], 'C:/Acme/99999_NewWidget',
            po_number='PO-123',
        )
        results = index.search_jobs('99999')
        assert len(results) == 1
        assert results[0]['po_number'] == 'PO-123'

    def test_add_job_upsert_does_not_erase_po_number_the_caller_still_has(self, tmp_path):
        # Same bug, the more damaging half: because the INSERT is
        # INSERT OR REPLACE keyed on UNIQUE(prefix, path), calling add_job()
        # again for an already-indexed path replaced the whole row and
        # SQLite filled the omitted po_number column with its schema
        # default '' -- silently wiping a real PO number a prior full
        # update() scan had written. The real caller (create_single_job())
        # always has po_number in scope, so a fixed add_job() must persist
        # it on every call, not just the first.
        index = _make_index(tmp_path)
        _insert_job(index, job_number='99999', path='C:/Acme/99999_NewWidget', po_number='PO-123')
        assert index.search_jobs('99999')[0]['po_number'] == 'PO-123'

        index.add_job(
            '', 'Acme', '99999', 'New Widget', [], 'C:/Acme/99999_NewWidget',
            mtime=2.0, po_number='PO-123',
        )
        results = index.search_jobs('99999')
        assert len(results) == 1
        assert results[0]['po_number'] == 'PO-123'

    def test_add_job_query_failure_does_not_raise(self, tmp_path):
        # Creating a job must never fail because the index write failed —
        # add_job() logs and swallows sqlite3.Error rather than propagating it.
        index = _make_index(tmp_path)
        with sqlite3.connect(str(index._db_path)) as conn:
            conn.execute("DROP TABLE jobs")
        index.add_job('', 'Acme', '99999', 'New Widget', [], 'C:/Acme/99999_NewWidget')  # must not raise

    def test_add_quote_makes_new_quote_immediately_searchable(self, tmp_path):
        index = _make_index(tmp_path)
        assert index.search_quotes('55555') == []

        index.add_quote('', 'Acme', '55555_NewQuote', 'C:/Acme/Quotes/55555_NewQuote')

        results = index.search_quotes('55555')
        assert len(results) == 1
        assert results[0]['job_number'] == '55555_NewQuote'

    def test_add_quote_query_failure_does_not_raise(self, tmp_path):
        index = _make_index(tmp_path)
        with sqlite3.connect(str(index._db_path)) as conn:
            conn.execute("DROP TABLE quotes")
        index.add_quote('', 'Acme', '55555_NewQuote', 'C:/Acme/Quotes/55555_NewQuote')  # must not raise


class TestUpdateExcludesReparsePointCustomers:
    """A junction/symlink standing in for a "customer" folder under cf_dirs/
    bp_dirs could target an excluded ITAR directory — os.walk()'s own
    followlinks=False default doesn't help here since the link is the walk's
    own starting point, not something encountered mid-walk. update() must
    exclude it from the customer listing itself before any indexing happens
    on a read-only install (CodeRabbit, PR #315)."""

    def _readonly_app_context(self, structure='{customer}/{job_folder}'):
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
            readonly_mode=True,
        )

    def test_reparse_point_customer_not_indexed_under_cf_dirs(self, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'LinkedCustomer' / '12345_Bracket').mkdir(parents=True)
        monkeypatch.setattr(
            'core.search_index.is_reparse_point',
            lambda p: os.path.basename(p) == 'LinkedCustomer',
        )
        ctx = self._readonly_app_context()
        index = _make_index(tmp_path)

        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        assert index.search_jobs('12345') == []

    def test_reparse_point_customer_not_indexed_under_bp_dirs(self, tmp_path, monkeypatch):
        bp_root = tmp_path / 'blueprints'
        linked = bp_root / 'LinkedCustomer'
        linked.mkdir(parents=True)
        (linked / 'drawing.pdf').write_text('secret')
        monkeypatch.setattr(
            'core.search_index.is_reparse_point',
            lambda p: os.path.basename(p) == 'LinkedCustomer',
        )
        ctx = self._readonly_app_context()
        index = _make_index(tmp_path)

        index.update(cf_dirs=[], bp_dirs=[('BP', str(bp_root))], app_context=ctx)

        assert index.search_bp('drawing') == []

    def test_reparse_point_customer_still_indexed_when_not_readonly(self, tmp_path, monkeypatch):
        cf_root = tmp_path / 'customer_files'
        (cf_root / 'LinkedCustomer' / '12345_Bracket').mkdir(parents=True)
        monkeypatch.setattr(
            'core.search_index.is_reparse_point',
            lambda p: os.path.basename(p) == 'LinkedCustomer',
        )
        ctx = _make_app_context()
        index = _make_index(tmp_path)

        index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)

        assert len(index.search_jobs('12345')) == 1


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
        # Migration cascades on to v5 too (path normalization, also a forced
        # cf re-index) since that's the current schema version.
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
        assert version == 5
        assert cf_dirs_remaining == 0  # forced re-index so po_number gets backfilled
        assert job_row == ('12345', '')

    def test_v3_database_with_po_number_already_present_still_forces_reindex(self, tmp_path):
        # Edge case: a database somehow reached user_version=3 with the
        # po_number column already present (e.g. state reached outside the
        # normal migration path). The "column already exists" branch must
        # still clear cf indexed_dirs markers — otherwise customers indexed
        # before po_number existed keep an empty value forever, since
        # update()'s mtime precheck would skip re-scanning them.
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

        assert version == 5  # cascades on to v5 (path normalization), also current schema
        assert cf_dirs_remaining == 0  # forced re-index despite column already existing


class TestUpdateHandlesMixedPathSeparators:
    """Regression test: Qt's QFileDialog.getExistingDirectory() returns forward-slash
    paths even on Windows, so a customer_files_dir picked via Settings' "Browse..."
    button ends up saved like "Z:/Customer Files". os.path.join(base_dir, customer)
    preserves that forward slash, while container paths derived via
    pathlib.Path(...).parents always normalize to the OS-native separator --
    without normalizing both to the same form, the two representations of the same
    directory ("job documents") don't string-match. update()'s incremental "cheap
    precheck" then can't find the previously-recorded "job documents" container via
    its LIKE-prefix lookup, falls back to checking only the customer root's own mtime
    (which never changes -- job folders are never a direct child of the customer root
    under this structure), and wrongly treats the customer as fully up to date --
    silently freezing the index for that customer on every subsequent update(), no
    matter what's added inside it later. Confirmed against real production data
    (a customer's job added weeks after the last successful scan never appeared in
    Strict search, despite "Search All Folders" -- an uncached os.walk -- finding it
    immediately).
    """

    @pytest.mark.skipif(
        os.name != 'nt',
        reason="Windows-only: pathlib.PosixPath never diverges from os.path.join "
               "the way WindowsPath does, so this mismatch can't occur on POSIX.",
    )
    def test_job_added_after_first_index_is_picked_up_on_second_update(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        (customer_path / 'job documents' / '11111_First').mkdir(parents=True)

        # Mimic Qt's QFileDialog output -- forward slashes even on Windows.
        base_dir = str(cf_root).replace(os.sep, '/')

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', base_dir)], bp_dirs=[], app_context=ctx)

        assert [r['job_number'] for r in index.search_jobs('11111', search_customer=False)] == ['11111']

        # A second job appears after the first index run. This only gets
        # picked up if the customer-root LIKE-prefix lookup for previously
        # recorded containers (like "job documents") actually finds them.
        (customer_path / 'job documents' / '22222_Second').mkdir(parents=True)
        index.update(cf_dirs=[('', base_dir)], bp_dirs=[], app_context=ctx)

        results = index.search_jobs('22222', search_customer=False)
        assert [r['job_number'] for r in results] == ['22222']

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only, see class docstring")
    def test_is_fully_covered_does_not_falsely_trust_stale_data(self, tmp_path):
        cf_root = tmp_path / 'customer_files'
        customer_path = cf_root / 'Acme'
        (customer_path / 'job documents' / '11111_First').mkdir(parents=True)
        base_dir = str(cf_root).replace(os.sep, '/')

        ctx = _make_app_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        index = _make_index(tmp_path)
        index.update(cf_dirs=[('', base_dir)], bp_dirs=[], app_context=ctx)

        (customer_path / 'job documents' / '22222_Second').mkdir(parents=True)

        assert index.is_fully_covered(cf_dirs=[('', base_dir)], bp_dirs=[]) is False


class TestUpdateNormalizesBlueprintCleanupPaths:
    """Regression test (CodeRabbit finding on this PR): the bp customer-purge
    cleanup built its LIKE prefix and valid_paths from raw base_dir, not
    normalized the way the per-customer staleness check just below it is --
    so a removed blueprint customer under a forward-slash root (same Qt
    QFileDialog scenario as the cf staleness bug) left an orphaned
    indexed_dirs row behind forever instead of being pruned.
    """

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-only, see class docstring")
    def test_removed_blueprint_customer_is_pruned_under_forward_slash_root(self, tmp_path):
        bp_root = tmp_path / 'blueprints'
        customer_path = bp_root / 'Acme'
        customer_path.mkdir(parents=True)
        (customer_path / 'drawing.pdf').write_text('x')

        # Mimic Qt's QFileDialog output -- forward slashes even on Windows.
        base_dir = str(bp_root).replace(os.sep, '/')

        ctx = _make_app_context()
        index = _make_index(tmp_path)
        index.update(cf_dirs=[], bp_dirs=[('', base_dir)], app_context=ctx)

        with sqlite3.connect(str(index._db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM indexed_dirs WHERE kind='bp'").fetchone()[0]
        assert count == 1

        shutil.rmtree(customer_path)
        index.update(cf_dirs=[], bp_dirs=[('', base_dir)], app_context=ctx)

        with sqlite3.connect(str(index._db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM indexed_dirs WHERE kind='bp'").fetchone()[0]
        assert count == 0


class TestMigrationToV5NormalizesPaths:
    def test_existing_v4_database_forces_cf_and_bp_reindex(self, tmp_path):
        # Simulate a database already migrated to v4 (po_number column
        # present) whose indexed_dirs rows may have been written under the
        # pre-fix mixed-separator representation -- both cf (the customer
        # staleness precheck) and bp (the blueprint customer-purge cleanup,
        # which had the same unnormalized-base_dir bug). Opening it with the
        # current SearchIndex must bump to v5 and force a clean re-index of
        # both kinds so those rows get rebuilt under consistently-normalized
        # paths.
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
                VALUES ('', 'Acme', '12345', 'Bracket', '', '', 'Z:/Acme/12345', 1.0);
            INSERT INTO indexed_dirs (dir_path, prefix, kind, mtime, indexed_at)
                VALUES ('Z:/Acme', '', 'cf', 1.0, 1.0);
            INSERT INTO indexed_dirs (dir_path, prefix, kind, mtime, indexed_at)
                VALUES ('Z:/Blueprints/Acme', '', 'bp', 1.0, 1.0);
            PRAGMA user_version = 4;
        """)
        conn.commit()
        conn.close()

        SearchIndex(db_path)

        conn = sqlite3.connect(str(db_path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        dirs_remaining = conn.execute("SELECT COUNT(*) FROM indexed_dirs").fetchone()[0]
        job_row = conn.execute("SELECT job_number FROM jobs").fetchone()

        assert version == 5
        assert dirs_remaining == 0  # forced re-index of both cf and bp
        assert job_row == ('12345',)  # existing job rows preserved, not wiped
