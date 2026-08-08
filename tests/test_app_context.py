"""Tests for AppContext file-operation helpers — pure filesystem logic, no Qt."""

import logging
import os

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
