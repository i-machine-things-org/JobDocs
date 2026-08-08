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

    def test_non_po_directories_are_excluded_by_name_prefix(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / 'job documents' / 'PO-1001' / '12345_Bracket').mkdir(parents=True)
        (customer_path / 'job documents' / 'NotAPO' / '99999_ShouldBeExcluded').mkdir(parents=True)

        ctx = _make_context('{customer}/job documents/PO-{po_number}/{job_folder}')
        jobs = ctx.find_job_folders(str(customer_path))

        assert [name for name, _ in jobs] == ['12345_Bracket']

    def test_po_number_as_its_own_path_segment_still_works(self, tmp_path):
        customer_path = tmp_path / 'Acme'
        (customer_path / '1001' / '12345_Bracket').mkdir(parents=True)

        ctx = _make_context('{customer}/{po_number}/{job_folder}')
        jobs = ctx.find_job_folders(str(customer_path))

        assert [name for name, _ in jobs] == ['12345_Bracket']
