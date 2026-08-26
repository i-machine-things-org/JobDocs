"""Tests for JobModule.create_single_job()'s search-index integration
(review finding 1 on PR #298 / issue #293).

Requires PyQt6 (JobModule/BaseModule import PyQt6 widget classes at module
level) but does not need a QApplication or any .ui file — create_single_job()
doesn't touch widgets.
"""

import os

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.app_context import AppContext  # noqa: E402
from core.search_index import SearchIndex  # noqa: E402
from modules.job.module import JobAlreadyExistsError, JobModule  # noqa: E402


def _make_app_context(tmp_path, cf_root, bp_root):
    return AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(bp_root),
            'allow_duplicate_jobs': False,
        },
        history={},
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )


def test_create_single_job_makes_job_immediately_searchable(tmp_path):
    """Reproduces the review's mid-session scenario end-to-end: a customer
    is already fully indexed (simulating the once-per-launch background
    indexer having already run), then a new job is created for that same
    customer via the real job-creation code path. Before this fix, nothing
    in create_single_job() touched the search index, so the new job would
    stay invisible to search until the app restarted and re-indexed.
    """
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'
    (cf_root / 'Acme' / '12345_ExistingBracket').mkdir(parents=True)

    ctx = _make_app_context(tmp_path, cf_root, bp_root)

    # Simulate the one-time background indexer having already run and
    # covered 'Acme' before our new job is created.
    index = ctx.get_search_index()
    assert isinstance(index, SearchIndex)
    index.update(cf_dirs=[('', str(cf_root))], bp_dirs=[], app_context=ctx)
    assert index.is_fully_covered([('', str(cf_root))], []) is True
    assert index.search_jobs('99999') == []  # not created yet

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
    ) is True

    # The new job must be searchable this session without any further
    # indexing — search_jobs() (what modules/search/module.py queries
    # first, before ever consulting is_fully_covered()) must find it.
    results = index.search_jobs('99999')
    assert len(results) == 1
    assert results[0]['customer'] == 'Acme'
    assert results[0]['job_number'] == '99999'


def test_create_single_job_raises_when_folder_already_exists(tmp_path):
    """Regression test for the atomic-creation fix (CodeRabbit, PR #317
    promotion review): mkdir(parents=True, exist_ok=True) couldn't tell "I
    created this" from "it already existed", so two racing callers (e.g.
    two workstations on the shared drive) both got a truthy result and
    both added history/index entries for one folder. create_single_job()
    now reserves the job folder atomically and raises
    JobAlreadyExistsError if it loses that race, rather than silently
    succeeding a second time.
    """
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'
    ctx = _make_app_context(tmp_path, cf_root, bp_root)

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
    ) is True

    # A second caller for the identical job -- e.g. another workstation
    # racing this one -- must lose, not silently succeed and double-add
    # history/index entries for the same folder.
    with pytest.raises(JobAlreadyExistsError):
        job_module.create_single_job(
            'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
        )

    index = ctx.get_search_index()
    assert len(index.search_jobs('99999')) == 1


def test_create_single_job_rolls_back_reservation_on_later_failure(tmp_path):
    """Regression test (CodeRabbit, PR #320 follow-up): job_path is
    reserved (created on disk) before file processing, history, and index
    updates run. If any of those fail, the reservation must be rolled back
    -- otherwise a retry hits the FileExistsError guard and is told
    "duplicate" for a job that was never actually completed, with no way
    to finish it or recover its history/index records.
    """
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'

    def failing_save_history():
        raise OSError('disk full')

    ctx = AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(bp_root),
            'allow_duplicate_jobs': False,
        },
        history={},
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=failing_save_history,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
    ) is False

    # The reservation must not be left behind -- the customer dir (shared,
    # not the uniqueness key) still exists, but the job folder itself must
    # be gone so a retry isn't told the job is a duplicate.
    acme_dir = cf_root / 'Acme'
    assert acme_dir.exists()
    assert list(acme_dir.iterdir()) == []

    # A retry goes through the same generic-failure path again -- if the
    # rollback hadn't happened, this would raise JobAlreadyExistsError
    # instead of returning False.
    assert job_module.create_single_job(
        'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
    ) is False
    assert list(acme_dir.iterdir()) == []


def test_create_single_job_rollback_clears_history_entry_too(tmp_path):
    """Regression test (CodeRabbit, PR #320 follow-up on the rollback fix
    above): add_to_history() mutates the shared in-memory history dict
    before save_history() runs. If save_history() then fails, removing
    job_path alone isn't enough -- the stale history entry would make
    _check_duplicate_job() report the job as a duplicate on retry, even
    though its folder no longer exists.
    """
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'
    history = {}

    def real_add_to_history(entry_type, data):
        history.setdefault(f'recent_{entry_type}s', []).insert(0, data)

    def failing_save_history():
        raise OSError('disk full')

    ctx = AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(bp_root),
            'allow_duplicate_jobs': False,
        },
        history=history,
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=failing_save_history,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=real_add_to_history,
    )

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'Acme', '99999', 'PO1', '', 'New Widget', [], '', False, [],
    ) is False

    # The rollback must undo the add_to_history() mutation, not just the
    # folder -- otherwise the duplicate check (keyed on recent_jobs) would
    # still find this job_number and permanently block a retry.
    is_dup, _ = job_module._check_duplicate_job('Acme', '99999')
    assert is_dup is False
    assert history.get('recent_jobs', []) == []


def test_create_single_job_still_creates_brand_new_customer(tmp_path):
    """Splitting mkdir(parents=True, exist_ok=True) into a parent.mkdir()
    plus a bare job_path.mkdir() must not regress the first-job-ever case,
    where multiple ancestor levels (the customer dir itself, plus any
    configured intermediate levels) don't exist yet.
    """
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'
    assert not (cf_root / 'BrandNewCo').exists()
    ctx = _make_app_context(tmp_path, cf_root, bp_root)

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'BrandNewCo', '10001', 'PO1', '', 'First Job', [], '', False, [],
    ) is True
    assert (cf_root / 'BrandNewCo').is_dir()


def test_create_single_job_itar_uses_itar_prefix_in_index(tmp_path):
    cf_root = tmp_path / 'customer_files'
    bp_root = tmp_path / 'blueprints'
    itar_cf_root = tmp_path / 'itar_customer_files'
    itar_bp_root = tmp_path / 'itar_blueprints'

    ctx = AppContext(
        settings={
            'job_folder_structure': '{customer}/{job_folder}',
            'customer_files_dir': str(cf_root),
            'blueprints_dir': str(bp_root),
            'itar_customer_files_dir': str(itar_cf_root),
            'itar_blueprints_dir': str(itar_bp_root),
            'allow_duplicate_jobs': False,
        },
        history={},
        config_dir=tmp_path,
        save_settings_callback=lambda: None,
        save_history_callback=lambda: None,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
    )

    job_module = JobModule()
    job_module.initialize(ctx)

    assert job_module.create_single_job(
        'Acme', '88888', 'PO1', '', 'Restricted Part', [], '', True, [],
    ) is True

    index = ctx.get_search_index()
    match = index.find_job_by_number('88888')
    assert match is not None
    assert match['customer'] == '[ITAR] Acme'
