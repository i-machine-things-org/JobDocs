"""Tests for AppContext.find_job_folders — pure filesystem logic, no Qt widgets used."""

from core.app_context import AppContext


def _make_context(structure):
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
