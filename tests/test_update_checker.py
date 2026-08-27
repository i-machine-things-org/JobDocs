"""Regression tests for _UpdateChecker's release-asset matching.

v0.11.1's checker picked whichever `.exe` came first in the GitHub API's
asset list. That was harmless as long as a release only ever shipped one
Windows installer, but v0.11.2 was the first release to ship two (JobDocs
and JobDocs Kiosk -- see build_scripts/JobDocs.iss) -- and it happened to
list the Kiosk asset before the standard one. A user's full v0.11.1 install
ran "Check for Updates," matched "first .exe," and got the Kiosk installer.

The fix (commit a200694, PR #315) already matches the asset's own "kiosk"
filename token against _is_readonly_install() instead, but had zero test
coverage until the bug actually happened in the wild. These tests pin that
behavior against the exact asset ordering that caused the incident.
"""

import json
import os

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _release_payload(tag, asset_names):
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/i-machine-things-org/JobDocs/releases/tag/{tag}",
        "assets": [
            {"name": name, "browser_download_url": f"https://example.com/{name}"}
            for name in asset_names
        ],
    }


def _run_checker(monkeypatch, *, is_kiosk, asset_names, tag="v99.0.0"):
    monkeypatch.setattr(main, "APP_VERSION", "v0.0.0")
    monkeypatch.setattr(main, "_is_readonly_install", lambda: is_kiosk)
    payload = _release_payload(tag, asset_names)
    monkeypatch.setattr(
        main.urllib.request, "urlopen",
        lambda *a, **k: _FakeResponse(payload),
    )

    checker = main._UpdateChecker()
    events = []
    checker.update_available.connect(lambda *args: events.append(("available", args)))
    checker.up_to_date.connect(lambda: events.append(("up_to_date", ())))
    checker.run()
    return events


class TestUpdateCheckerAssetMatching:
    def test_full_install_gets_standard_asset_even_when_kiosk_listed_first(self, qapp, monkeypatch):
        """Reproduces the actual incident: the Kiosk asset was listed before
        the standard one, and the old "first .exe" logic picked it for a
        non-Kiosk install."""
        events = _run_checker(
            monkeypatch, is_kiosk=False,
            asset_names=[
                "JobDocs-Kiosk-v99.0.0-windows-setup.exe",
                "JobDocs-v99.0.0-windows-setup.exe",
            ],
        )
        assert len(events) == 1
        kind, (_tag, _html_url, asset_url) = events[0]
        assert kind == "available"
        assert asset_url == "https://example.com/JobDocs-v99.0.0-windows-setup.exe"

    def test_kiosk_install_gets_kiosk_asset_even_when_standard_listed_first(self, qapp, monkeypatch):
        events = _run_checker(
            monkeypatch, is_kiosk=True,
            asset_names=[
                "JobDocs-v99.0.0-windows-setup.exe",
                "JobDocs-Kiosk-v99.0.0-windows-setup.exe",
            ],
        )
        assert len(events) == 1
        kind, (_tag, _html_url, asset_url) = events[0]
        assert kind == "available"
        assert asset_url == "https://example.com/JobDocs-Kiosk-v99.0.0-windows-setup.exe"

    def test_no_matching_variant_leaves_asset_url_empty(self, qapp, monkeypatch):
        """If a release somehow ships only the other variant's installer,
        fall back to an empty asset_url (the dialog then just links to the
        releases page) rather than silently offering the wrong installer."""
        events = _run_checker(
            monkeypatch, is_kiosk=True,
            asset_names=["JobDocs-v99.0.0-windows-setup.exe"],
        )
        assert len(events) == 1
        kind, (_tag, _html_url, asset_url) = events[0]
        assert kind == "available"
        assert asset_url == ""

    def test_up_to_date_when_no_newer_tag(self, qapp, monkeypatch):
        events = _run_checker(
            monkeypatch, is_kiosk=False,
            asset_names=["JobDocs-v0.0.0-windows-setup.exe"],
            tag="v0.0.0",
        )
        assert events == [("up_to_date", ())]
