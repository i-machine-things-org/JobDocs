"""Tests for BaseModule.is_widget_built()/mark_widget_built() (issue #286,
CodeRabbit follow-up on PR #306)."""

import os

import pytest

from core.app_context import AppContext
from core.base_module import BaseModule

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

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


class _UncachedPluginModule(BaseModule):
    """A get_widget() implementation that doesn't follow the
    `if self._widget is None: ...` caching convention -- e.g. a plugin
    that builds a fresh widget every call, or caches it under a different
    attribute name. Still a valid BaseModule per the abstract contract,
    which only requires get_widget() to return a QWidget."""

    def get_name(self):
        return "Uncached Plugin"

    def get_widget(self):
        return QWidget()  # never touches self._widget

    def initialize(self, app_context):
        super().initialize(app_context)


def test_is_widget_built_requires_explicit_mark(qapp, tmp_path):
    """get_widget() succeeding is not, by itself, enough to flip
    is_widget_built() -- only the caller's explicit mark_widget_built()
    (called by main.py's _on_tab_activated after a successful get_widget())
    does. This is what makes the tracking correct for modules that don't
    cache to self._widget."""
    m = QuoteModule()
    m.initialize(_make_app_context(tmp_path))

    assert m.is_widget_built() is False
    m.get_widget()
    assert m.is_widget_built() is False  # not yet marked

    m.mark_widget_built()
    assert m.is_widget_built() is True


def test_is_widget_built_works_for_uncached_get_widget(tmp_path):
    """Regression test: a get_widget() that never sets self._widget must
    still report built correctly once mark_widget_built() is called --
    the old self._widget-is-not-None check would have permanently reported
    False for a module like this, silently skipping it in
    populate_customer_lists()."""
    m = _UncachedPluginModule()
    m.initialize(_make_app_context(tmp_path))

    assert m.is_widget_built() is False
    widget = m.get_widget()
    assert widget is not None
    assert m._widget is None  # confirms this module never caches it

    m.mark_widget_built()
    assert m.is_widget_built() is True
