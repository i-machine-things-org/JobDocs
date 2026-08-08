"""Tests for DropZone's Outlook drag-drop paths (issue #271).

Covers the actually-fixable parts of "only a fraction of dropped files are
captured": FILEGROUPDESCRIPTOR(W) parsing now walks every entry (not just
entry 0), the single-file-content limitation of Qt's QMimeData API is now
surfaced to the user instead of silently dropping the rest, and classic
Outlook's multi-select drag now retrieves every selected email instead of
just the first.

The exact wire format of classic Outlook's multi-select "Csv" MIME blob
(assumed here to be newline-separated entry IDs, mirroring the already
-established row-per-item layout of the neighbouring text/plain subject
data) could not be verified against a real Outlook instance in this
environment — flagged for verification on Windows.
"""

import os
import struct

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from shared.widgets import DropZone  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_filedescriptorw_entry(filename: str) -> bytes:
    name = filename.encode('utf-16-le')
    name = name + b'\x00' * (520 - len(name))
    return (
        struct.pack('<I', 0)      # dwFlags
        + b'\x00' * 16            # clsid
        + b'\x00' * 8             # sizel
        + b'\x00' * 8             # pointl
        + struct.pack('<I', 0)    # dwFileAttributes
        + b'\x00' * 8 * 3         # 3x FILETIME
        + struct.pack('<I', 0)    # nFileSizeHigh
        + struct.pack('<I', 0)    # nFileSizeLow
        + name
    )


def _make_descriptor_blob(filenames: list) -> bytes:
    entries = b''.join(_make_filedescriptorw_entry(f) for f in filenames)
    return struct.pack('<I', len(filenames)) + entries


class _FakeMime:
    """Stand-in for QMimeData — DropZone's static helpers only call .data()/.formats()."""

    def __init__(self, payloads: dict):
        self._payloads = payloads

    def data(self, fmt):
        return self._payloads.get(fmt, b'')

    def formats(self):
        return list(self._payloads.keys())


class TestParseDescriptorFilenames:
    def test_parses_all_entries_not_just_the_first(self, qapp):
        blob = _make_descriptor_blob(['invoice.pdf', 'photo.jpg', 'notes.txt'])
        names = DropZone._parse_descriptor_filenames(blob, is_unicode=True)
        assert names == ['invoice.pdf', 'photo.jpg', 'notes.txt']

    def test_single_entry(self, qapp):
        blob = _make_descriptor_blob(['email.eml'])
        names = DropZone._parse_descriptor_filenames(blob, is_unicode=True)
        assert names == ['email.eml']

    def test_zero_entries(self, qapp):
        blob = struct.pack('<I', 0)
        names = DropZone._parse_descriptor_filenames(blob, is_unicode=True)
        assert names == []

    def test_truncated_blob_does_not_crash(self, qapp):
        blob = _make_descriptor_blob(['a.txt', 'b.txt'])[:100]  # cut mid-entry
        names = DropZone._parse_descriptor_filenames(blob, is_unicode=True)
        assert names == []  # first entry itself is truncated


class TestHandleOutlookDropMultiFile:
    def test_warns_user_when_multiple_files_in_descriptor(self, qapp, tmp_path, monkeypatch):
        blob = _make_descriptor_blob(['invoice.pdf', 'photo.jpg'])
        mime = _FakeMime({
            'FileGroupDescriptorW': blob,
            'FileContents': b'PDF-CONTENT-BYTES',
        })

        warnings = []
        monkeypatch.setattr(
            QMessageBox, 'warning',
            lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok,
        )

        files = DropZone._handle_outlook_drop(mime, 'FileGroupDescriptorW')

        assert len(files) == 1
        assert files[0].endswith('invoice.pdf')
        # The user must be told a file was missed — not a silent partial success.
        assert len(warnings) == 1
        warning_text = str(warnings[0])
        assert 'photo.jpg' in warning_text

    def test_no_warning_for_a_single_file_drop(self, qapp, tmp_path, monkeypatch):
        blob = _make_descriptor_blob(['email.eml'])
        mime = _FakeMime({
            'FileGroupDescriptorW': blob,
            'FileContents': b'EML-CONTENT-BYTES',
        })

        warnings = []
        monkeypatch.setattr(
            QMessageBox, 'warning',
            lambda *a, **k: warnings.append(a) or QMessageBox.StandardButton.Ok,
        )

        files = DropZone._handle_outlook_drop(mime, 'FileGroupDescriptorW')

        assert len(files) == 1
        assert warnings == []


class TestHandleClassicOutlookDropMultiSelect:
    def test_retrieves_every_selected_email_not_just_the_first(self, qapp, monkeypatch):
        csv_text = "ID-AAAA\r\nID-BBBB\r\nID-CCCC\r\n"
        plain_text = (
            "From\tSubject\tReceived\tSize\tCategories\t\n"
            "Alice\tFirst email\t2026-01-01\t1KB\t\t\n"
            "Bob\tSecond email\t2026-01-02\t2KB\t\t\n"
            "Carol\tThird email\t2026-01-03\t3KB\t\t\n"
        )
        mime = _FakeMime({
            'application/x-qt-windows-mime;value="Csv"': csv_text.encode('utf-16-le'),
            'text/plain': plain_text.encode('utf-8'),
        })

        calls = []

        def _fake_mapi_save_email(raw_id, subject, tmp_dir, idx=0):
            calls.append((raw_id, subject, idx))
            return [f"{tmp_dir}/email_{idx}.msg"]

        monkeypatch.setattr(DropZone, '_mapi_save_email', staticmethod(_fake_mapi_save_email))

        files = DropZone._handle_classic_outlook_drop(mime)

        assert len(calls) == 3
        assert [c[0] for c in calls] == ['ID-AAAA', 'ID-BBBB', 'ID-CCCC']
        assert [c[1] for c in calls] == ['First email', 'Second email', 'Third email']
        assert [c[2] for c in calls] == [0, 1, 2]
        assert len(files) == 3

    def test_single_selection_still_works(self, qapp, monkeypatch):
        csv_text = "ID-SOLO\r\n"
        plain_text = (
            "From\tSubject\tReceived\tSize\tCategories\t\n"
            "Alice\tOnly email\t2026-01-01\t1KB\t\t\n"
        )
        mime = _FakeMime({
            'application/x-qt-windows-mime;value="Csv"': csv_text.encode('utf-16-le'),
            'text/plain': plain_text.encode('utf-8'),
        })

        calls = []
        monkeypatch.setattr(
            DropZone, '_mapi_save_email',
            staticmethod(lambda raw_id, subject, tmp_dir, idx=0: calls.append((raw_id, subject, idx)) or ['x.msg']),
        )

        files = DropZone._handle_classic_outlook_drop(mime)

        assert calls == [('ID-SOLO', 'Only email', 0)]
        assert files == ['x.msg']

    def test_no_id_or_subject_returns_empty(self, qapp):
        mime = _FakeMime({})
        assert DropZone._handle_classic_outlook_drop(mime) == []
