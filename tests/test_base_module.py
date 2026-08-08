"""Tests for BaseModule.is_widget_built() (issue #286)."""

import os

import pytest

from core.app_context import AppContext

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from modules.quote.module import QuoteModule  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context(tmp_path):
    return AppContext(
        settings={'job_folder_structure': '{customer}/{job_folder}'},
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


def test_is_widget_built_reflects_lazy_construction(qapp, tmp_path):
    m = QuoteModule()
    m.initialize(_make_app_context(tmp_path))

    assert m.is_widget_built() is False
    m.get_widget()
    assert m.is_widget_built() is True
