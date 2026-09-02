"""Tests for AppContext file-operation helpers — pure filesystem logic, no Qt."""

import logging
import os

import core.app_context as app_context_module
from core.app_context import AppContext


def _make_context(structure='{customer}/{job_folder}'):
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


def _make_readonly_context(readonly_mode):
    calls = {'settings': 0, 'history': 0}

    def _save_settings():
        calls['settings'] += 1

    def _save_history():
        calls['history'] += 1

    ctx = AppContext(
        settings={},
        history={},
        config_dir=None,
        save_settings_callback=_save_settings,
        save_history_callback=_save_history,
        log_message_callback=lambda *a: None,
        show_error_callback=lambda *a: None,
        show_info_callback=lambda *a: None,
        get_customer_list_callback=lambda: [],
        add_to_history_callback=lambda *a: None,
        readonly_mode=readonly_mode,
    )
    return ctx, calls


class TestPersistenceReadonlyGuard:
    """AppContext.save_settings/save_history are the central defense-in-depth
    guard for readonly_mode — every module's persistence funnels through here,
    not just Search's own check."""

    def test_readonly_mode_blocks_save_settings(self):
        ctx, calls = _make_readonly_context(readonly_mode=True)
        ctx.save_settings()
        assert calls['settings'] == 0

    def test_readonly_mode_blocks_save_history(self):
        ctx, calls = _make_readonly_context(readonly_mode=True)
        ctx.save_history()
        assert calls['history'] == 0

    def test_writable_mode_still_saves_settings(self):
        ctx, calls = _make_readonly_context(readonly_mode=False)
        ctx.save_settings()
        assert calls['settings'] == 1

    def test_writable_mode_still_saves_history(self):
        ctx, calls = _make_readonly_context(readonly_mode=False)
        ctx.save_history()
        assert calls['history'] == 1


def _make_readonly_search_context(structure='{customer}/{job_folder}'):
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


class TestFindFoldersRejectsReparsePointCustomer:
    """A junction/symlink standing in for customer_path could target an
    excluded ITAR directory. find_job_folders()/find_quote_folders() refuse
    it outright on a read-only install — defense-in-depth alongside the
    caller-side customer-listing filters in SearchWorker._strict_search()
    and SearchIndex.update() (CodeRabbit, PR #315)."""

    def test_find_job_folders_returns_empty_for_reparse_point_when_readonly(
        self, tmp_path, monkeypatch
    ):
        customer_path = tmp_path / 'LinkedCustomer'
        (customer_path / '10001').mkdir(parents=True)
        monkeypatch.setattr(app_context_module, 'is_reparse_point', lambda p: True)

        ctx = _make_readonly_search_context()

        assert ctx.find_job_folders(str(customer_path)) == []

    def test_find_job_folders_still_works_for_real_dir_when_readonly(self, tmp_path, monkeypatch):
        customer_path = tmp_path / 'RealCustomer'
        (customer_path / '10001').mkdir(parents=True)
        monkeypatch.setattr(app_context_module, 'is_reparse_point', lambda p: False)

        ctx = _make_readonly_search_context()

        assert ctx.find_job_folders(str(customer_path)) == [('10001', str(customer_path / '10001'))]

    def test_find_job_folders_ignores_reparse_points_when_not_readonly(self, tmp_path, monkeypatch):
        """The guard is a read-only (kiosk) restriction, not a general one —
        the full app has no ITAR-exclusion concern to defend here."""
        customer_path = tmp_path / 'LinkedCustomer'
        (customer_path / '10001').mkdir(parents=True)
        monkeypatch.setattr(app_context_module, 'is_reparse_point', lambda p: True)

        ctx = _make_context()

        assert ctx.find_job_folders(str(customer_path)) == [('10001', str(customer_path / '10001'))]

    def test_find_quote_folders_returns_empty_for_reparse_point_when_readonly(
        self, tmp_path, monkeypatch
    ):
        customer_path = tmp_path / 'LinkedCustomer'
        (customer_path / 'Quotes' / 'Q1001').mkdir(parents=True)
        monkeypatch.setattr(app_context_module, 'is_reparse_point', lambda p: True)

        ctx = _make_readonly_search_context()

        assert ctx.find_quote_folders(str(customer_path)) == []


class TestFindQuoteFoldersLogsOnError:
    def test_returns_empty_list_and_logs_on_oserror(self, tmp_path, monkeypatch, caplog):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'Quotes').mkdir(parents=True)

        def _raise(*_args, **_kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr(os, 'listdir', _raise)

        ctx = _make_context()
        with caplog.at_level(logging.DEBUG, logger='core.app_context'):
            result = ctx.find_quote_folders(str(customer_path))

        # Fallback behavior callers rely on is unchanged...
        assert result == []
        # ...but the failure is no longer silent.
        assert any('find_quote_folders' in rec.message for rec in caplog.records)

    def test_no_error_when_quotes_dir_missing(self, tmp_path):
        ctx = _make_context()
        assert ctx.find_quote_folders(str(tmp_path / 'NoSuchCustomer')) == []


class TestFindJobFoldersWithPoNumber:
    def test_literal_prefix_sharing_po_number_segment(self, tmp_path):
        # Regression test for #295: "PO-{po_number}" puts literal text in the
        # same path segment as the placeholder, so the PO folder name is
        # "PO-1001", not a subdirectory literally named "PO-".
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'PO-1001' / '12345_Bracket').mkdir(parents=True)
        (customer_path / 'job documents' / 'PO-1002' / '67890_Shaft').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        jobs = ctx.find_job_folders(str(customer_path))

        assert sorted(name for name, _ in jobs) == ['12345_Bracket', '67890_Shaft']

    def test_legacy_job_folders_without_a_po_wrapper_are_still_found(self, tmp_path):
        # Regression test for #295's actual root cause: once PO folders were
        # introduced, older job folders that were never moved under a PO
        # folder stopped being found at all, because every entry under the
        # base dir was assumed to be a PO container. A folder that doesn't
        # match the PO naming convention must be treated as a job folder in
        # its own right, not silently skipped.
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / '11111_LegacyJob').mkdir(parents=True)
        (customer_path / 'job documents' / 'PO-1001' / '22222_NewJob').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        jobs = ctx.find_job_folders(str(customer_path))

        assert sorted(name for name, _ in jobs) == ['11111_LegacyJob', '22222_NewJob']

    def test_po_number_as_its_own_path_segment_still_works(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / '1001' / '12345_Bracket').mkdir(parents=True)

        ctx = _make_context('{customer}/{po_number}/{job_folder}')
        jobs = ctx.find_job_folders(str(customer_path))

        assert [name for name, _ in jobs] == ['12345_Bracket']

    def test_legacy_job_folder_found_when_po_number_is_a_whole_path_segment(self, tmp_path):
        # Regression test (CodeRabbit finding on PR #305): when the PO number
        # placeholder occupies a whole path segment on its own (no literal
        # prefix/suffix sharing that segment, e.g. "{po_number}" rather than
        # "PO-{po_number}"), matches_po_name is unconditionally True, so a
        # legacy job folder that predates PO folders was always treated as a
        # PO container and its own job-documents suffix underneath it was
        # never discovered.
        customer_path = tmp_path / 'Acme'
        (customer_path / '12345_LegacyBracket' / 'job documents').mkdir(parents=True)
        (customer_path / '1001' / '22222_NewJob' / 'job documents').mkdir(parents=True)

        ctx = _make_context('{customer}/{po_number}/{job_folder}/job documents')
        jobs = ctx.find_job_folders(str(customer_path))

        assert sorted(name for name, _ in jobs) == ['12345_LegacyBracket', '22222_NewJob']

    def test_named_po_folder_with_intermediate_path_is_not_reported_as_a_job(self, tmp_path):
        # Regression test (CodeRabbit finding on PR #316): the legacy-folder
        # detection above must only fire for the genuinely ambiguous
        # whole-segment case (po_name_prefix, po_name_suffix, and post_po all
        # empty). When the PO folder has a named prefix ("PO-") and an
        # intermediate path segment before {job_folder} that happens to share
        # its literal name with the job-documents suffix (both "job
        # documents" here), po_path/suffix always exists for *every* valid PO
        # folder -- it's the same directory as sub_path, which is already
        # confirmed to exist. Without the extra guards, every real PO folder
        # would also be reported as a spurious job in its own right.
        customer_path = tmp_path / 'Acme'
        (customer_path / 'PO-1001' / 'job documents' / '22222_NewJob' / 'job documents').mkdir(parents=True)

        ctx = _make_context('{customer}/PO-{po_number}/job documents/{job_folder}/job documents')
        jobs = ctx.find_job_folders(str(customer_path))

        assert [name for name, _ in jobs] == ['22222_NewJob']


class TestFindJobFoldersFlagsUnrecognizedNames:
    """A folder that neither matches the PO naming convention nor looks like
    a job folder (no leading digit) is currently found by find_job_folders()
    and then silently dropped by every caller's digit-first filter -- with no
    trace anywhere. The optional `unrecognized` collector surfaces these so a
    "Check Folder Naming" report can show the user what needs fixing."""

    def test_unrelated_folder_name_is_flagged_as_unrecognized(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'New folder').mkdir(parents=True)
        (customer_path / 'job documents' / 'PO-1001' / '22222_NewJob').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        unrecognized = []
        jobs = ctx.find_job_folders(str(customer_path), unrecognized=unrecognized)

        assert [os.path.basename(p) for p, _ in unrecognized] == ['New folder']
        assert unrecognized[0][1] == 'unrecognized folder'
        # jobs/other behavior is unaffected -- still found (and still the
        # caller's job to filter out non-digit names downstream, unchanged).
        assert 'New folder' in [name for name, _ in jobs]
        assert '22222_NewJob' in [name for name, _ in jobs]

    def test_near_miss_po_folder_name_is_flagged(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'PO 1001').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        unrecognized = []
        ctx.find_job_folders(str(customer_path), unrecognized=unrecognized)

        assert [os.path.basename(p) for p, _ in unrecognized] == ['PO 1001']
        assert unrecognized[0][1] == 'near-miss PO folder'

    def test_empty_but_correctly_named_po_folder_is_not_flagged(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'PO-1001').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        unrecognized = []
        ctx.find_job_folders(str(customer_path), unrecognized=unrecognized)

        assert unrecognized == []

    def test_unrecognized_none_is_default_and_no_op(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'New folder').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        # Must not raise when the caller doesn't pass unrecognized at all.
        jobs = ctx.find_job_folders(str(customer_path))

        assert 'New folder' in [name for name, _ in jobs]
