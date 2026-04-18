"""
Shared custom widgets for JobDocs

Common UI widgets used across multiple modules.
"""

from PyQt6.QtWidgets import (
    QFrame, QDialog, QVBoxLayout, QScrollArea, QLabel, QDialogButtonBox,
    QPushButton, QFileDialog, QLineEdit, QListWidget, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QHeaderView,
    QWidget, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from pathlib import Path
import atexit
import logging
import os
import shutil
import struct
import tempfile

logger = logging.getLogger(__name__)


# Single atexit handler for all DropZone temp directories — avoids accumulating
# one handler per drag-and-drop operation.
_dropzone_tmp_dirs: list = []


def _cleanup_dropzone_tmp_dirs() -> None:
    for d in _dropzone_tmp_dirs:
        shutil.rmtree(d, True)


atexit.register(_cleanup_dropzone_tmp_dirs)


class DropZone(QFrame):
    """A widget that accepts file drops"""
    files_dropped = pyqtSignal(list)

    # Extensions filtered out during email attachment extraction when skip is enabled.
    _SKIP_EXTS: frozenset = frozenset()
    _IMAGE_EXTS: frozenset = frozenset({
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.tiff', '.tif', '.webp', '.ico', '.svg',
    })

    @classmethod
    def set_skip_image_attachments(cls, enabled: bool) -> None:
        """Enable or disable automatic skipping of image attachments from emails."""
        cls._SKIP_EXTS = cls._IMAGE_EXTS if enabled else frozenset()

    def __init__(self, label: str = "Drop files here", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(60)
        self.setMaximumHeight(100)
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 6px;
            }
            DropZone:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.label = QLabel(f"{label} or click Browse")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_files)
        self.browse_btn.setMaximumWidth(90)
        self.browse_btn.setMaximumHeight(22)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def _outlook_descriptor_format(mime_data) -> str:
        """Return the FileGroupDescriptor format name if present, else empty string."""
        for fmt in mime_data.formats():
            if 'filegroupdescriptor' in fmt.lower():
                return fmt
        return ''

    @staticmethod
    def _is_classic_outlook(mime_data) -> bool:
        """Return True if this drag is from the classic Outlook desktop app."""
        return 'application/x-qt-windows-mime;value="RenPrivateMessages"' in mime_data.formats()

    @staticmethod
    def _is_new_outlook(mime_data) -> bool:
        """Return True if this drag originates from New Outlook / Outlook Web (WebView2)."""
        try:
            taint = bytes(mime_data.data(
                'application/x-qt-windows-mime;value="chromium/x-renderer-taint"'
            ))
            return bool(taint and b'outlook' in taint.lower())
        except Exception:
            return False

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime = event.mimeData()
        print(f"[DropZone] dragEnter formats: {mime.formats()}", flush=True)
        if (mime.hasUrls() or self._outlook_descriptor_format(mime)
                or self._is_classic_outlook(mime) or self._is_new_outlook(mime)):
            event.acceptProposedAction()
            self.setStyleSheet("""
                DropZone {
                    background-color: #e3f2fd;
                    border: 2px dashed #2196f3;
                    border-radius: 8px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 6px;
            }
            DropZone:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("""
            DropZone {
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 6px;
            }
            DropZone:hover {
                border-color: #999;
                background-color: #e8e8e8;
            }
        """)
        mime = event.mimeData()
        print(f"[DropZone] dropEvent formats: {mime.formats()}", flush=True)

        # Log format names and sizes only — avoid printing raw bytes that may contain email content
        for fmt in mime.formats():
            try:
                data = bytes(mime.data(fmt))
                print(f"[DropZone]   {fmt}: {len(data)} bytes", flush=True)
            except Exception as e:
                print(f"[DropZone]   {fmt}: read error - {e}", flush=True)
        if mime.hasUrls():
            for url in mime.urls():
                print(f"[DropZone]   URL: {url.toString()!r}  local={url.toLocalFile()!r}", flush=True)

        # Outlook/Electron may not enumerate FileGroupDescriptorW via EnumFormatEtc but
        # still honour GetData for it — try asking explicitly.
        for probe in [
            'application/x-qt-windows-mime;value="FileGroupDescriptorW"',
            'application/x-qt-windows-mime;value="FileGroupDescriptor"',
            'application/x-qt-windows-mime;value="FileContents"',
        ]:
            try:
                data = bytes(mime.data(probe))
                if data:
                    print(f"[DropZone]   Probe hit: {probe}: {len(data)} bytes", flush=True)
            except Exception:
                pass

        descriptor_fmt = self._outlook_descriptor_format(mime)

        # Detect drag source
        is_outlook_web = DropZone._is_new_outlook(mime)
        is_classic_outlook = DropZone._is_classic_outlook(mime) and not is_outlook_web

        files: list = []
        if is_outlook_web:
            files = DropZone._handle_outlook_web_drop(mime)
            if not files and mime.hasUrls():
                # Attachment drag from New Outlook: the Chromium taint is present
                # but the MIME payload has no mail-row key (it's a file attachment,
                # not an email row). Fall through to the CF_HDROP URL handler below.
                print('[DropZone] New Outlook web-drop returned empty — '
                      'falling back to hasUrls() for attachment drag', flush=True)
                is_outlook_web = False
            elif not files:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, 'Email Not Retrieved',
                    'Could not retrieve the email from Outlook Web.\n\n'
                    'Make sure the Outlook desktop app is open and signed in with '
                    'the same account, then try again.\n\n'
                    'Alternatively, save the email to disk (File → Save As) and '
                    'drop the file here.'
                )
        if not is_outlook_web and not files and is_classic_outlook:
            files = DropZone._handle_classic_outlook_drop(mime)
            if not files:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, 'Email Not Retrieved',
                    'Could not retrieve the email from Outlook.\n\n'
                    'Make sure Outlook is open and signed in, then try again.\n\n'
                    'Alternatively, save the email to disk (File → Save As) and '
                    'drop the file here.'
                )
        if not files and not is_classic_outlook and mime.hasUrls():
            files = []
            for url in mime.urls():
                local = url.toLocalFile()
                if local:
                    ext = os.path.splitext(local)[1].lower()
                    if ext == '.eml' and os.path.exists(local):
                        files.extend(DropZone._extract_eml_attachments(local))
                    elif ext == '.msg' and os.path.exists(local):
                        files.extend(DropZone._extract_msg_attachments(local))
                    elif os.path.exists(local):
                        files.append(local)
                    else:
                        print(f"[DropZone]   Skipping non-existent file: {local}", flush=True)
                else:
                    # Non-local URL (blob:, https:, etc.) — log and skip for now
                    print(f"[DropZone]   Skipping non-local URL: {url.toString()}", flush=True)
        if not files and descriptor_fmt:
            files = DropZone._handle_outlook_drop(mime, descriptor_fmt)

        print(f"[DropZone] emitting {len(files)} file(s)", flush=True)
        for f in files:
            print(f"  - {f}", flush=True)
        if files:
            self.files_dropped.emit(files)

    # ------------------------------------------------------------------
    # Outlook Web / New Outlook desktop (WebView2) drag support
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_chromium_web_mime(data: bytes) -> dict:
        """Parse 'Chromium Web Custom MIME Data Format' binary blob.

        Format (all little-endian):
          4 bytes  total payload size
          4 bytes  entry count
          for each entry:
            4 bytes  key char-count  (UTF-16LE, no null)
            key_len*2 bytes  key
            2 bytes  UTF-16LE null terminator
            4 bytes  value char-count (UTF-16LE, no null)
            val_len*2 bytes  value  (JSON string)

        Returns dict {key: parsed_json_value}.
        """
        import json as _json
        result = {}
        if len(data) < 8:
            return result
        count = struct.unpack_from('<I', data, 4)[0]
        offset = 8
        for _ in range(count):
            if offset + 4 > len(data):
                break
            key_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            try:
                key = data[offset: offset + key_len * 2].decode('utf-16-le')
            except Exception:
                break
            offset += key_len * 2 + 2          # skip UTF-16LE null terminator
            if offset + 4 > len(data):
                break
            val_len = struct.unpack_from('<I', data, offset)[0]
            offset += 4
            if offset + val_len * 2 > len(data):
                break
            try:
                val_str = data[offset: offset + val_len * 2].decode('utf-16-le')
            except Exception:
                break
            offset += val_len * 2
            try:
                result[key] = _json.loads(val_str)
            except Exception:
                result[key] = val_str
        return result

    @staticmethod
    def _handle_outlook_web_drop(mime_data) -> list:
        """Handle a drag from the new Outlook desktop app (WebView2/O365).

        Reads the Chromium custom MIME payload to get the Exchange item ID,
        then saves the email via MAPI (Outlook COM) or falls back gracefully.
        Returns a list of local file paths (empty on failure).
        """
        raw = b''
        try:
            raw = bytes(mime_data.data(
                'application/x-qt-windows-mime;value="Chromium Web Custom MIME Data Format"'
            ))
        except Exception:
            pass

        if not raw:
            print('[DropZone] No Chromium Web MIME data', flush=True)
            return []

        web_data = DropZone._parse_chromium_web_mime(raw)
        # New Outlook uses different keys depending on context (inbox, search results, etc.)
        _ROW_KEYS = (
            'maillistrow',
            'multimaillistconversationrows',  # search results in New Outlook
            'conversationlistrow',
            'itemlistrow',
            'mailrow',
            'messagelistrow',
        )
        mail_info = None
        for _key in _ROW_KEYS:
            if isinstance(web_data.get(_key), dict):
                mail_info = web_data[_key]
                print(f'[DropZone] Chromium MIME key matched: {_key!r}', flush=True)
                break
        if not isinstance(mail_info, dict):
            print(
                f'[DropZone] No recognised mail row key in Chromium MIME data. '
                f'Keys present: {list(web_data.keys())}',
                flush=True,
            )
            return []

        # New Outlook uses parallel arrays: subjects[], itemIds[], mailboxInfos[]
        # Classic OWA used flat fields: subject, id
        subjects = mail_info.get('subjects') or []
        item_ids = (mail_info.get('itemIds') or
                    mail_info.get('latestItemIds') or [])

        # Fall back to flat field names used by some OWA versions
        if not subjects:
            s = mail_info.get('subject') or mail_info.get('Subject') or ''
            subjects = [s] if s else []
        if not item_ids:
            i = (mail_info.get('id') or mail_info.get('itemId') or
                 mail_info.get('ItemId') or '')
            item_ids = [i] if i else []

        print(
            f'[DropZone] OWA drag: {len(item_ids)} email(s), '
            f'subjects={subjects}',
            flush=True,
        )

        if not item_ids:
            print('[DropZone] No item IDs found in drag data', flush=True)
            return []

        tmp_dir = tempfile.mkdtemp(prefix='jobdocs_email_')
        _dropzone_tmp_dirs.append(tmp_dir)
        files = []
        for idx, raw_id in enumerate(item_ids):
            subj = subjects[idx] if idx < len(subjects) else ''
            # Returns [msg_path, att1, att2, ...] or []
            results = DropZone._mapi_save_email(raw_id, subj, tmp_dir, idx)
            files.extend(results)

        return files

    @staticmethod
    def _mapi_save_email(raw_id: str, subject: str, tmp_dir: str, idx: int = 0) -> list:
        """Retrieve one email via Outlook MAPI COM, save as .msg, extract attachments.

        Returns [msg_path, att1, att2, ...] on success, [] on failure.
        """
        import re

        def _safe_filename(s: str, fallback: str) -> str:
            name = re.sub(r'[\\/:*?"<>|]', '_', s).strip() if s else ''
            if not name:
                return fallback
            # Truncate to 200 chars (preserving extension) to stay under OS limits
            base, ext = os.path.splitext(name)
            max_base = max(0, 200 - len(ext))
            if len(base) > max_base:
                name = base[:max_base] + ext
            return name

        def _save_mail_item(mail_item, tag: str) -> list:
            """Save a MAPI MailItem and its attachments; return list of paths."""
            subj = ''
            try:
                subj = mail_item.Subject or ''
            except Exception:
                pass
            fname = _safe_filename(subj or subject, f'email_{idx}')
            msg_path = os.path.join(tmp_dir, f'{fname}.msg')
            try:
                mail_item.SaveAs(msg_path, 3)   # 3 = olMSGUnicode
            except Exception as e:
                print(f'[DropZone] MAPI SaveAs failed ({tag}): {e}', flush=True)
                return []
            if not os.path.exists(msg_path) or os.path.getsize(msg_path) == 0:
                return []
            print(f'[DropZone] MAPI saved ({tag}): {msg_path}', flush=True)

            # Extract attachments directly from the MAPI item
            att_paths = []
            try:
                count = mail_item.Attachments.Count
                print(f'[DropZone] MAPI: {count} attachment(s)', flush=True)
                for i in range(1, count + 1):
                    try:
                        att = mail_item.Attachments.Item(i)
                        att_name = _safe_filename(
                            att.FileName or att.DisplayName, f'attachment_{i}'
                        )
                        if os.path.splitext(att_name)[1].lower() in DropZone._SKIP_EXTS:
                            print(f'[DropZone] Skipping image attachment: {att_name}', flush=True)
                            continue
                        att_path = os.path.join(tmp_dir, att_name)
                        if os.path.exists(att_path):
                            base, ext = os.path.splitext(att_name)
                            counter = 1
                            while os.path.exists(att_path):
                                att_path = os.path.join(tmp_dir, f"{base}_{counter}{ext}")
                                counter += 1
                        att.SaveAsFile(att_path)
                        if os.path.exists(att_path) and os.path.getsize(att_path) > 0:
                            print(f'[DropZone] MAPI attachment: {att_name}', flush=True)
                            if os.path.splitext(att_name)[1].lower() == '.zip':
                                att_paths.extend(DropZone._expand_zip(att_path, tmp_dir))
                            else:
                                att_paths.append(att_path)
                        else:
                            sz = os.path.getsize(att_path) if os.path.exists(att_path) else -1
                            print(f'[DropZone] MAPI attachment empty/missing: {att_name} (size={sz})', flush=True)
                    except Exception as att_err:
                        print(f'[DropZone] MAPI attachment[{i}] error: {att_err}', flush=True)
            except Exception as e:
                print(f'[DropZone] MAPI attachment extraction error: {e}', flush=True)

            return [msg_path] + att_paths

        try:
            import win32com.client as _wc
        except ImportError:
            print('[DropZone] pywin32 not installed — MAPI unavailable', flush=True)
            return []

        try:
            outlook = _wc.Dispatch('Outlook.Application')
            ns = outlook.GetNamespace('MAPI')

            # --- 1. Direct entry-ID lookup (base64 → hex for GetItemFromID) ---
            if raw_id:
                for entry_id in DropZone._entry_id_variants(raw_id):
                    try:
                        item = ns.GetItemFromID(entry_id)
                        result = _save_mail_item(item, 'direct-id')
                        if result:
                            return result
                    except Exception:
                        pass

            # --- 2. Restrict search in Inbox + Sent by subject ---
            if subject:
                # Escape for MAPI SQL equality filter: only single-quotes need doubling.
                # % and _ are wildcards for LIKE but are literal in = queries.
                def _mapi_escape(s: str) -> str:
                    return s.replace("'", "''")

                safe_subj = _mapi_escape(subject)
                # Also try without a leading "Re: " prefix in case OWA adds one
                base_subj = re.sub(r'^(re:\s*)+', '', safe_subj, flags=re.IGNORECASE).strip()
                subjects_to_try = [safe_subj] if safe_subj == base_subj else [safe_subj, base_subj]
                for folder_const in (6, 5):     # 6=Inbox, 5=SentMail
                    try:
                        folder = ns.GetDefaultFolder(folder_const)
                        items = folder.Items
                        items.Sort('[ReceivedTime]', True)   # newest first
                        best_result = None
                        for subj_variant in subjects_to_try:
                            filter_str = f"[Subject] = '{subj_variant}'"
                            for mail in items.Restrict(filter_str):
                                result = _save_mail_item(mail, f'folder-{folder_const}')
                                if len(result) > 1:     # has real attachments
                                    return result
                                if result and best_result is None:
                                    best_result = result  # .msg only — keep as fallback
                        if best_result:
                            return best_result
                    except Exception as e:
                        print(f'[DropZone] MAPI folder {folder_const} error: {e}', flush=True)

        except Exception as e:
            print(f'[DropZone] MAPI error: {e}', flush=True)

        return []

    @staticmethod
    def _entry_id_variants(raw_id: str) -> list:
        """Return candidate entry-ID strings to try with GetItemFromID.

        The new Outlook puts a base64-encoded MAPI PR_ENTRYID in itemIds[].
        GetItemFromID needs a hex-encoded string of those same bytes.
        We also try the raw string in case the format differs.
        """
        import base64
        candidates = [raw_id]   # try raw first (handles EWS/Graph IDs)
        # Try base64 → hex (standard MAPI PR_ENTRYID encoding used by new Outlook)
        for pad in ('', '=', '=='):
            try:
                decoded = base64.b64decode(raw_id + pad)
                candidates.append(decoded.hex().upper())
                break
            except Exception:
                pass
        return candidates

    @staticmethod
    def _handle_classic_outlook_drop(mime_data) -> list:
        """Handle drag from the classic Outlook desktop app.

        Classic Outlook provides RenPrivateMessages (binary MAPI entry IDs) and a
        Csv format containing the same entry ID as a UTF-16LE hex string.  FileContents
        is typically 0 bytes when dropped on non-Shell targets, so we retrieve the email
        via MAPI COM using the entry ID directly.
        """
        # Entry ID is stored in the Csv format as a UTF-16LE hex string —
        # exactly the format GetItemFromID expects, no conversion needed.
        raw_id = ''
        try:
            csv_bytes = bytes(mime_data.data('application/x-qt-windows-mime;value="Csv"'))
            if csv_bytes:
                raw_id = csv_bytes.decode('utf-16-le').rstrip('\x00').strip()
                print(f"[DropZone] Classic Outlook entry ID: {raw_id[:40]}...", flush=True)
        except Exception as e:
            print(f"[DropZone] Could not read Csv entry ID: {e}", flush=True)

        # Subject from text/plain tab-delimited: header row then data row
        # "From\tSubject\tReceived\tSize\tCategories\t\nSender\tSubject..."
        subject = ''
        try:
            plain_bytes = bytes(mime_data.data('text/plain'))
            plain = plain_bytes.decode('utf-8', errors='replace')
            lines = [l for l in plain.splitlines() if l.strip()]
            for line in lines:
                cols = line.split('\t')
                if cols[0].strip().lower() not in ('from', ''):
                    if len(cols) >= 2:
                        subject = cols[1].strip()
                        break
            print(f"[DropZone] Classic Outlook subject: {subject!r}", flush=True)
        except Exception as e:
            print(f"[DropZone] Could not parse subject from text/plain: {e}", flush=True)

        # Fallback: read subject from FileGroupDescriptorW filename (strip .msg)
        if not subject:
            descriptor_fmt = DropZone._outlook_descriptor_format(mime_data)
            if descriptor_fmt:
                try:
                    descriptor_bytes = bytes(mime_data.data(descriptor_fmt))
                    is_unicode = descriptor_fmt.upper().endswith('W')
                    name_offset = 4 + 72
                    if is_unicode:
                        name_bytes = descriptor_bytes[name_offset:name_offset + 520]
                        parsed = name_bytes.decode('utf-16-le').split('\x00')[0]
                    else:
                        name_bytes = descriptor_bytes[name_offset:name_offset + 260]
                        parsed = name_bytes.decode('latin-1').split('\x00')[0]
                    if parsed:
                        subject = os.path.splitext(parsed)[0]
                        print(f"[DropZone] Classic Outlook subject (from descriptor): {subject!r}", flush=True)
                except Exception as e:
                    print(f"[DropZone] Could not parse descriptor for subject: {e}", flush=True)

        if not raw_id and not subject:
            print('[DropZone] Classic Outlook: no entry ID or subject — cannot retrieve email', flush=True)
            return []

        tmp_dir = tempfile.mkdtemp(prefix='jobdocs_email_')
        _dropzone_tmp_dirs.append(tmp_dir)
        return DropZone._mapi_save_email(raw_id, subject, tmp_dir, 0)

    @staticmethod
    def _handle_outlook_drop(mime_data, descriptor_fmt: str) -> list:
        """Save the Outlook virtual-file bytes to a temp file, then extract attachments."""
        try:
            descriptor_bytes = bytes(mime_data.data(descriptor_fmt))
            # CFSTR_FILECONTENTS has no W variant per Windows OLE spec — always 'FileContents'
            content_bytes = bytes(mime_data.data('FileContents'))
        except Exception as e:
            print(f"[DropZone] Could not read Outlook mime data: {e}", flush=True)
            return []

        if not descriptor_bytes or not content_bytes:
            print(f"[DropZone] Empty descriptor ({len(descriptor_bytes)}) or content ({len(content_bytes)})", flush=True)
            return []

        # Parse FILEGROUPDESCRIPTOR(W): 4-byte count, then FILEDESCRIPTOR structs.
        is_unicode = descriptor_fmt.upper().endswith('W')
        filename = 'email.eml'
        try:
            count = struct.unpack_from('<I', descriptor_bytes, 0)[0]
            print(f"[DropZone] descriptor count={count}, is_unicode={is_unicode}", flush=True)
            if count > 0:
                name_offset = 4 + 72
                if is_unicode:
                    name_bytes = descriptor_bytes[name_offset:name_offset + 520]
                    parsed = name_bytes.decode('utf-16-le').split('\x00')[0]
                else:
                    name_bytes = descriptor_bytes[name_offset:name_offset + 260]
                    parsed = name_bytes.decode('latin-1').split('\x00')[0]
                if parsed:
                    filename = parsed
                    print(f"[DropZone] Parsed filename: {filename}", flush=True)
        except Exception as e:
            print(f"[DropZone] Could not parse descriptor: {e}", flush=True)

        tmp_dir = tempfile.mkdtemp(prefix='jobdocs_email_')
        _dropzone_tmp_dirs.append(tmp_dir)
        email_path = os.path.join(tmp_dir, filename)
        try:
            with open(email_path, 'wb') as f:
                f.write(content_bytes)
            print(f"[DropZone] Saved email to: {email_path} ({len(content_bytes)} bytes)", flush=True)
        except Exception as e:
            print(f"[DropZone] Could not save email file: {e}", flush=True)
            return []

        ext = os.path.splitext(filename)[1].lower()
        if ext == '.eml':
            return DropZone._extract_eml_attachments(email_path, tmp_dir)
        elif ext == '.msg':
            return DropZone._extract_msg_attachments(email_path, tmp_dir)
        else:
            return [email_path]

    @classmethod
    def _expand_zip(cls, zip_path: str, extract_dir: str) -> list:
        """Extract a zip file and return paths of its contents. Returns [zip_path] on failure."""
        import zipfile
        _MAX_FILES = 100
        _MAX_UNCOMPRESSED = 100 * 1024 * 1024  # 100 MB
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                members = [m for m in zf.infolist() if not m.is_dir() and os.path.basename(m.filename)]
                if len(members) > _MAX_FILES:
                    print(f"[DropZone] zip has {len(members)} files; skipping (limit {_MAX_FILES})", flush=True)
                    return [zip_path]
                total_size = sum(m.file_size for m in members)
                if total_size > _MAX_UNCOMPRESSED:
                    print(f"[DropZone] zip uncompressed size {total_size} bytes exceeds limit; skipping", flush=True)
                    return [zip_path]
                extracted = []
                for member in members:
                    name = os.path.basename(member.filename)
                    if cls._SKIP_EXTS and os.path.splitext(name)[1].lower() in cls._SKIP_EXTS:
                        print(f"[DropZone] zip: skipping image {name}", flush=True)
                        continue
                    dest = os.path.join(extract_dir, name)
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(name)
                        counter = 1
                        while os.path.exists(dest):
                            dest = os.path.join(extract_dir, f"{base}_{counter}{ext}")
                            counter += 1
                    with zf.open(member) as src, open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(dest)
                    print(f"[DropZone] Extracted from zip: {os.path.basename(dest)}", flush=True)
                if extracted:
                    return extracted
        except Exception as e:
            print(f"[DropZone] zip extraction error: {e}", flush=True)
        return [zip_path]

    @staticmethod
    def _extract_eml_attachments(eml_path: str, extract_dir: str = None) -> list:
        """Extract attachments from a .eml file using the standard library."""
        import email as _email
        import email.policy as _policy

        if extract_dir is None:
            extract_dir = tempfile.mkdtemp(prefix='jobdocs_email_')
            _dropzone_tmp_dirs.append(extract_dir)

        try:
            with open(eml_path, 'rb') as f:
                msg = _email.message_from_binary_file(f, policy=_policy.default)

            saved = []
            for part in msg.walk():
                if part.get_content_disposition() != 'attachment':
                    continue
                name = part.get_filename()
                if not name:
                    continue
                if os.path.splitext(name)[1].lower() in DropZone._SKIP_EXTS:
                    print(f"[DropZone] Skipping image attachment: {name}", flush=True)
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                base, ext = os.path.splitext(name)
                dest = os.path.join(extract_dir, name)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(extract_dir, f"{base}_{counter}{ext}")
                    counter += 1
                with open(dest, 'wb') as f:
                    f.write(payload)
                print(f"[DropZone] Extracted from .eml: {name}", flush=True)
                if os.path.splitext(name)[1].lower() == '.zip':
                    saved.extend(DropZone._expand_zip(dest, extract_dir))
                else:
                    saved.append(dest)

            if saved:
                return [eml_path] + saved  # email first, then attachments
            print(f"[DropZone] No attachments in .eml", flush=True)
            return [eml_path]

        except Exception as e:
            print(f"[DropZone] .eml extraction error: {e}", flush=True)
            return [eml_path]

    @staticmethod
    def _extract_msg_attachments(msg_path: str, extract_dir: str = None) -> list:
        """Extract attachments from a .msg file."""
        if extract_dir is None:
            extract_dir = tempfile.mkdtemp(prefix='jobdocs_email_')
            _dropzone_tmp_dirs.append(extract_dir)

        # Try extract-msg (pip install extract-msg)
        try:
            import extract_msg
            with extract_msg.Message(msg_path) as msg:
                saved = []
                for att in msg.attachments:
                    name = att.longFilename or att.shortFilename or 'attachment'
                    if not att.data:
                        continue
                    if os.path.splitext(name)[1].lower() in DropZone._SKIP_EXTS:
                        print(f"[DropZone] Skipping image attachment: {name}", flush=True)
                        continue
                    base, ext = os.path.splitext(name)
                    dest = os.path.join(extract_dir, name)
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(extract_dir, f"{base}_{counter}{ext}")
                        counter += 1
                    with open(dest, 'wb') as f:
                        f.write(att.data)
                    print(f"[DropZone] Extracted via extract_msg: {name}", flush=True)
                    if os.path.splitext(name)[1].lower() == '.zip':
                        saved.extend(DropZone._expand_zip(dest, extract_dir))
                    else:
                        saved.append(dest)
                if saved:
                    return [msg_path] + saved
        except ImportError:
            pass
        except Exception as e:
            print(f"[DropZone] extract_msg error: {e}", flush=True)

        # Fallback: return the .msg file itself
        return [msg_path]

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files",
            "",
            "All Files (*.*)"
        )
        if files:
            self.files_dropped.emit(files)


class ScrollableMessageDialog(QDialog):
    """A custom dialog with scrollable content and defined size"""

    def __init__(self, parent, title: str, content: str, width: int = 600, height: int = 500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, height)

        # Create layout
        layout = QVBoxLayout(self)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Create content label
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setStyleSheet("padding: 10px;")

        # Set label as scroll area widget
        scroll_area.setWidget(content_label)

        # Add scroll area to layout
        layout.addWidget(scroll_area)

        # Add OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class JobSearchDialog(QDialog):
    """A search dialog for finding and copying job/quote information"""

    def __init__(self, parent, app_context, search_type="jobs/quotes"):
        super().__init__(parent)
        self.app_context = app_context
        self.selected_folder = None
        self.search_type = search_type

        self.setWindowTitle(f"Search {search_type.title()}")
        self.resize(700, 500)

        # Create layout
        layout = QVBoxLayout(self)

        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type customer, job#, description...")
        self.search_input.textChanged.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.results_list)

        # Status label
        self.status_label = QLabel("Enter search term...")
        layout.addWidget(self.status_label)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Focus search input
        self.search_input.setFocus()

    def perform_search(self):
        """Search for jobs/quotes matching the search term"""
        search_term = self.search_input.text().strip().lower()
        self.results_list.clear()

        if len(search_term) < 2:
            self.status_label.setText("Enter at least 2 characters...")
            return

        # Get directories to search
        cf_dir = self.app_context.get_setting('customer_files_dir', '')
        itar_cf_dir = self.app_context.get_setting('itar_customer_files_dir', '')
        quote_folder_path = self.app_context.get_setting('quote_folder_path', 'Quotes')

        results = []

        # Search both directories
        for base_dir, is_itar in [(cf_dir, False), (itar_cf_dir, True)]:
            if not base_dir or not os.path.exists(base_dir):
                continue

            # Walk through customer directories
            try:
                for customer_name in os.listdir(base_dir):
                    customer_path = os.path.join(base_dir, customer_name)
                    if not os.path.isdir(customer_path):
                        continue

                    # Search for job folders (in customer root)
                    for item in os.listdir(customer_path):
                        item_path = os.path.join(customer_path, item)

                        # Check if it's a job folder (has "job documents" subfolder)
                        job_docs_path = os.path.join(item_path, "job documents")
                        if os.path.isdir(job_docs_path):
                            # This is a job folder
                            if search_term in item.lower() or search_term in customer_name.lower():
                                prefix = '[ITAR] ' if is_itar else ''
                                display = f"{prefix}{customer_name}/{item}"
                                results.append((display, item_path))

                        # Check if it's the Quotes folder
                        elif item.lower() == quote_folder_path.lower():
                            # Search inside Quotes folder
                            quotes_path = item_path
                            if os.path.isdir(quotes_path):
                                for quote_item in os.listdir(quotes_path):
                                    quote_item_path = os.path.join(quotes_path, quote_item)
                                    if os.path.isdir(quote_item_path):
                                        # This is a quote folder
                                        if search_term in quote_item.lower() or search_term in customer_name.lower():
                                            prefix = '[ITAR] ' if is_itar else ''
                                            display = f"{prefix}{customer_name}/Quotes/{quote_item}"
                                            results.append((display, quote_item_path))
            except OSError:
                pass

        # Add to list (limit to 100 results)
        for display_name, full_path in sorted(results)[:100]:
            item = self.results_list.addItem(display_name)
            self.results_list.item(self.results_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, full_path
            )

        self.status_label.setText(f"Found {len(results)} result(s)" if results else "No matches found")

    def on_item_double_clicked(self, item):
        """Handle double-click on an item"""
        self.selected_folder = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def get_selected_folder(self):
        """Get the selected folder path"""
        current_item = self.results_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None


class FileCopyDialog(QDialog):
    """Dialog for selecting files to copy from a source folder"""

    def __init__(self, parent, source_folder: str, title: str = "Select Files to Copy"):
        super().__init__(parent)
        self.source_folder = Path(source_folder)
        self.selected_files = []

        self.setWindowTitle(title)
        self.resize(600, 450)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel(f"Source: {self.source_folder.name}")
        header_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(header_label)

        # File tree with checkboxes
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["File", "Size", "Type"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.file_tree)

        # Populate files
        self._populate_files()

        # Select All / Select None buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_none)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel()
        self._update_status()
        layout.addWidget(self.status_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_files(self):
        """Populate the file tree with files from source folder"""
        if not self.source_folder.exists():
            return

        # Collect all files (including from job documents subfolder)
        files_to_show = []

        # Files in main folder
        for item in self.source_folder.iterdir():
            if item.is_file():
                files_to_show.append(item)

        # Check for "job documents" subfolder
        job_docs = self.source_folder / "job documents"
        if job_docs.exists() and job_docs.is_dir():
            for item in job_docs.iterdir():
                if item.is_file():
                    files_to_show.append(item)

        # Sort by name
        files_to_show.sort(key=lambda f: f.name.lower())

        for file_path in files_to_show:
            item = QTreeWidgetItem()

            # Checkbox in first column
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)

            # File name (show relative path if from subfolder)
            try:
                rel_path = file_path.relative_to(self.source_folder)
                item.setText(0, str(rel_path))
            except ValueError:
                item.setText(0, file_path.name)

            # File size
            try:
                size = file_path.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                item.setText(1, size_str)
            except OSError:
                item.setText(1, "?")

            # File type (extension)
            item.setText(2, file_path.suffix.upper() or "File")

            # Store full path in data
            item.setData(0, Qt.ItemDataRole.UserRole, str(file_path))

            self.file_tree.addTopLevelItem(item)

        # Connect check state changes to update status
        self.file_tree.itemChanged.connect(self._update_status)

    def _select_all(self):
        """Select all files"""
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)

    def _select_none(self):
        """Deselect all files"""
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def _update_status(self):
        """Update the status label with selection count"""
        selected = 0
        total = self.file_tree.topLevelItemCount()
        for i in range(total):
            item = self.file_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                selected += 1
        self.status_label.setText(f"Selected: {selected} of {total} files")

    def get_selected_files(self) -> list:
        """Return list of selected file paths"""
        selected = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                file_path = item.data(0, Qt.ItemDataRole.UserRole)
                if file_path:
                    selected.append(file_path)
        return selected

    def has_files(self) -> bool:
        """Check if there are any files to show"""
        return self.file_tree.topLevelItemCount() > 0


class DrawingSearchDialog(QDialog):
    """Dialog for searching and linking existing drawings by drawing number"""

    def __init__(self, parent, app_context):
        super().__init__(parent)
        self.app_context = app_context
        self.selected_files = []

        self.setWindowTitle("Link Drawings")
        self.resize(750, 550)

        layout = QVBoxLayout(self)

        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Drawing Number:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter drawing number to search...")
        self.search_input.textChanged.connect(self.perform_search)
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Results tree with checkboxes
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["File", "Location", "Type"])
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.results_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.results_tree)

        # Select All / Select None buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_none)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("Enter drawing number to search...")
        layout.addWidget(self.status_label)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Focus search input
        self.search_input.setFocus()

    def perform_search(self):
        """Search for drawings matching the drawing number"""
        search_term = self.search_input.text().strip().lower()
        self.results_tree.clear()

        if len(search_term) < 2:
            self.status_label.setText("Enter at least 2 characters...")
            return

        # Get directories to search
        blueprints_dir = self.app_context.get_setting('blueprints_dir', '')
        itar_blueprints_dir = self.app_context.get_setting('itar_blueprints_dir', '')

        results = []

        # Search blueprints directories
        for base_dir, location_prefix in [
            (blueprints_dir, 'Blueprints'),
            (itar_blueprints_dir, 'ITAR Blueprints'),
        ]:
            if not base_dir or not os.path.exists(base_dir):
                continue

            try:
                # Walk through the directory tree
                for root, dirs, files in os.walk(base_dir):
                    for filename in files:
                        # Check if the drawing number is in the filename
                        if search_term in filename.lower():
                            file_path = os.path.join(root, filename)
                            # Get relative path from base for display
                            try:
                                rel_path = os.path.relpath(root, base_dir)
                                if rel_path == '.':
                                    location = location_prefix
                                else:
                                    location = f"{location_prefix}/{rel_path}"
                            except ValueError:
                                location = location_prefix

                            # Determine file type
                            ext = os.path.splitext(filename)[1].upper()
                            file_type = ext if ext else "File"

                            results.append((filename, location, file_type, file_path))
            except OSError:
                pass

        # Add results to tree (limit to 200)
        for filename, location, file_type, full_path in sorted(results)[:200]:
            item = QTreeWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setText(0, filename)
            item.setText(1, location)
            item.setText(2, file_type)
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            self.results_tree.addTopLevelItem(item)

        if results:
            self.status_label.setText(f"Found {len(results)} file(s)")
        else:
            self.status_label.setText("No matches found")

    def _select_all(self):
        """Select all files"""
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Checked)

    def _select_none(self):
        """Deselect all files"""
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            item.setCheckState(0, Qt.CheckState.Unchecked)

    def get_selected_files(self) -> list:
        """Return list of selected file paths"""
        selected = []
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                file_path = item.data(0, Qt.ItemDataRole.UserRole)
                if file_path:
                    selected.append(file_path)
        return selected


class FilePreviewWidget(QWidget):
    """Preview panel shown beside a drop-zone file list.

    Renders image thumbnails, PDF first pages (via pymupdf if installed),
    and shows type + size info for CAD, mesh, email, and all other files.
    """

    _IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp', '.ico'}
    _CAD_EXTS   = {'.step', '.stp', '.iges', '.igs', '.x_t', '.x_b', '.prt', '.asm'}
    _MESH_EXTS  = {'.stl', '.obj', '.ply', '.3mf'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setStyleSheet("background: #1e1e1e; border-radius: 3px;")
        layout.addWidget(self.image_label, stretch=1)

        self.info_label = QLabel("No file selected")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.info_label)

    # ------------------------------------------------------------------
    def preview_file(self, file_path: str | None):
        if not file_path or not os.path.exists(file_path):
            self.clear()
            return

        path = Path(file_path)
        ext = path.suffix.lower()
        try:
            size_str = self._fmt_size(path.stat().st_size)
        except OSError:
            size_str = ""

        if ext in self._IMAGE_EXTS:
            pix = QPixmap(file_path)
            if not pix.isNull():
                self._set_pixmap(pix, path.name, size_str)
                return

        if ext == '.pdf':
            if self._try_pdf_preview(file_path):
                self.info_label.setText(f"{path.name}\n{size_str}")
                return
            self._set_text("PDF", f"{path.name}\n{size_str}\n(install pymupdf\nfor page preview)")
            return

        if ext in self._CAD_EXTS:
            self._set_text("STEP / IGES", f"{path.name}\n{size_str}")
            return

        if ext in self._MESH_EXTS:
            self._set_text("3D Mesh", f"{path.name}\n{size_str}")
            return

        if ext == '.msg':
            self._set_text("Email (.msg)", f"{path.name}\n{size_str}")
            return

        type_label = (ext.upper().lstrip('.') + " file") if ext else "File"
        self._set_text(type_label, f"{path.name}\n{size_str}")

    def _try_pdf_preview(self, file_path: str) -> bool:
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            try:
                if doc.page_count == 0:
                    return False
                page = doc[0]
                # Cap rendered size: a fixed 1.5× scale can exceed Qt's 256 MB
                # allocation limit for high-res embedded images. Scale to fit
                # within MAX_DIM × MAX_DIM pixels instead.
                MAX_DIM = 600
                rect = page.rect
                scale = min(MAX_DIM / rect.width, MAX_DIM / rect.height, 1.5)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                data = pix.tobytes('png')
            finally:
                doc.close()
            qpix = QPixmap()
            if qpix.loadFromData(data) and not qpix.isNull():
                self._set_pixmap(qpix, "", "")
                return True
        except Exception:
            pass
        return False

    def _set_pixmap(self, pix: QPixmap, name: str, size_str: str):
        self._pixmap = pix
        self._scale_pixmap()
        detail = "\n".join(filter(None, [name, size_str]))
        self.info_label.setText(detail)

    def _set_text(self, type_label: str, detail: str):
        self._pixmap = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(type_label)
        self.info_label.setText(detail)

    def _scale_pixmap(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        size = self.image_label.size()
        if size.width() < 10 or size.height() < 10:
            size = QSize(200, 200)
        scaled = self._pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap:
            self._scale_pixmap()

    def clear(self):
        self._pixmap = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("")
        self.info_label.setText("No file selected")

    @staticmethod
    def _fmt_size(size: int) -> str:
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024 or unit == 'GB':
                return f"{size:.1f} {unit}"
            size = size / 1024.0
        raise AssertionError("unreachable")


def _draw_image_fitted(painter: 'QPainter', img: 'QImage', page_rect: 'QRectF') -> None:  # type: ignore[name-defined]
    """Draw img centred and scaled to fit page_rect preserving aspect ratio."""
    from PyQt6.QtCore import QRectF as _QRectF
    img_ratio = img.width() / max(img.height(), 1)
    page_ratio = page_rect.width() / max(page_rect.height(), 1)
    if img_ratio > page_ratio:
        w = page_rect.width()
        h = w / img_ratio
    else:
        h = page_rect.height()
        w = h * img_ratio
    x = (page_rect.width() - w) / 2
    y = (page_rect.height() - h) / 2
    painter.drawImage(_QRectF(x, y, w, h), img)


def print_files_with_dialog(paths: list, parent=None, app_context=None) -> None:
    """Show a print dialog then render and print each file.

    If a print provider is registered via app_context.register_print_provider()
    (e.g. the HoneyBatchr plugin), files are sent there instead.

    Otherwise: PDF files are rendered via PyMuPDF (fitz); common image formats
    are loaded directly; other types (DWG, DXF, etc.) fall back to the OS print
    handler (os.startfile on Windows, lp on macOS/Linux).
    """
    if app_context is not None:
        provider = app_context.get_print_provider()
        if provider is not None:
            provider.add_files_to_list(paths)
            return
    import platform
    from PyQt6.QtPrintSupport import QPrinter
    from PyQt6.QtGui import QPainter, QImage
    from PyQt6.QtCore import QRectF

    _IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    _RENDERABLE = _IMAGE_EXTS | {'.pdf'}

    renderable = [p for p in paths if os.path.isfile(p) and Path(p).suffix.lower() in _RENDERABLE]
    fallback   = [p for p in paths if os.path.isfile(p) and Path(p).suffix.lower() not in _RENDERABLE]

    cancelled = False
    failed_pre_render: list[str] = []
    failed_print_render: list[str] = []
    if renderable:
        # Pre-check fitz so the paintRequested closure doesn't import on every call
        try:
            import fitz as _fitz  # pymupdf
        except ImportError:
            _fitz = None
            # PDFs can't be previewed — move them to OS fallback
            for _p in list(renderable):
                if Path(_p).suffix.lower() == '.pdf':
                    fallback.append(_p)
                    renderable.remove(_p)

        if renderable:
            # preview_printer: PDF-format virtual printer — no system printer
            # connection, no I/O, no timeouts.  QPrintPreviewDialog uses it only
            # to record QPicture data; the output file is never written.
            # print_printer: HighResolution native printer, only created and
            # configured by QPrintDialog when the user actually clicks Print.
            preview_printer = QPrinter()
            preview_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            preview_printer.setResolution(96)

            # Pre-cache at 48 DPI. Each A4 page is ~397×561 px — small enough
            # that QPicture serialisation and overview-mode replay are instant.
            # The actual print job re-renders from fitz at 200 DPI.
            _PREVIEW_DPI = 48
            preview_cache: list[QImage] = []
            renderable_for_print: list[str] = []
            for path in renderable:
                ext = Path(path).suffix.lower()
                if ext == '.pdf' and _fitz is not None:
                    try:
                        doc = _fitz.open(path)
                        try:
                            _page_imgs: list[QImage] = []
                            for page_num in range(doc.page_count):
                                pg = doc[page_num]
                                pix = pg.get_pixmap(
                                    matrix=_fitz.Matrix(
                                        _PREVIEW_DPI / 72, _PREVIEW_DPI / 72
                                    ),
                                    alpha=False,
                                )
                                samples = bytes(pix.samples)
                                _page_imgs.append(
                                    QImage(
                                        samples, pix.width, pix.height,
                                        pix.stride, QImage.Format.Format_RGB888,
                                    ).copy()
                                )
                            preview_cache.extend(_page_imgs)
                            renderable_for_print.append(path)
                        finally:
                            doc.close()
                    except Exception:
                        logger.warning(
                            "print_files_with_dialog: failed to pre-render PDF %s",
                            path, exc_info=True,
                        )
                        failed_pre_render.append(os.path.basename(path))
                else:
                    img = QImage(path)
                    if not img.isNull():
                        preview_cache.append(img)
                        renderable_for_print.append(path)

            def _render_to(pr: 'QPrinter', dpi: float) -> None:
                """Render renderable files to pr at the given DPI."""
                _pa = QPainter(pr)
                try:
                    _pr = QRectF(_pa.viewport())
                    _first = True
                    for path in renderable_for_print:
                        ext = Path(path).suffix.lower()
                        if ext == '.pdf' and _fitz is not None:
                            try:
                                doc = _fitz.open(path)
                                try:
                                    for page_num in range(doc.page_count):
                                        if not _first:
                                            pr.newPage()
                                            _pr = QRectF(_pa.viewport())
                                        _first = False
                                        pg = doc[page_num]
                                        pix = pg.get_pixmap(
                                            matrix=_fitz.Matrix(dpi / 72, dpi / 72),
                                            alpha=False,
                                        )
                                        samples = bytes(pix.samples)
                                        img = QImage(
                                            samples, pix.width, pix.height,
                                            pix.stride, QImage.Format.Format_RGB888,
                                        ).copy()
                                        _draw_image_fitted(_pa, img, _pr)
                                finally:
                                    doc.close()
                            except Exception:
                                logger.warning(
                                    "print_files_with_dialog: failed to render"
                                    " PDF %s at %.0f DPI",
                                    path, dpi, exc_info=True,
                                )
                                failed_print_render.append(os.path.basename(path))
                        else:
                            img = QImage(path)
                            if img.isNull():
                                continue
                            if not _first:
                                pr.newPage()
                                _pr = QRectF(_pa.viewport())
                            _first = False
                            _draw_image_fitted(_pa, img, _pr)
                finally:
                    _pa.end()

            def do_render(pr: 'QPrinter') -> None:  # type: ignore[name-defined]
                # Preview only — blit 48 DPI cache into the 96 DPI preview printer
                _pa = QPainter(pr)
                try:
                    _pr = QRectF(_pa.viewport())
                    for i, img in enumerate(preview_cache):
                        if i > 0:
                            pr.newPage()
                            _pr = QRectF(_pa.viewport())
                        _draw_image_fitted(_pa, img, _pr)
                finally:
                    _pa.end()

            from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrintDialog
            from PyQt6.QtGui import QKeySequence, QAction

            preview = QPrintPreviewDialog(preview_printer, parent)
            preview.resize(600, 450)
            preview.paintRequested.connect(do_render)

            # Intercept the built-in Print toolbar button so we can render at
            # 200 DPI on a native HighResolution printer, not the PDF preview printer.
            def _do_print() -> None:
                _print_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                _pdlg = QPrintDialog(_print_printer, preview)
                if _pdlg.exec() != QPrintDialog.DialogCode.Accepted:
                    return
                _render_to(_print_printer, 200)
                preview.accept()

            # Hook the toolbar Print button to use our high-res render path.
            # Qt assigns QKeySequence.StandardKey.Print on Windows/macOS; on
            # Linux the action has no shortcut but carries the object name
            # "qt_print_preview_print" or plain text "Print".
            _hooked = False
            for _act in preview.findChildren(QAction):
                _shortcut_match = _act.shortcut().matches(
                    QKeySequence(QKeySequence.StandardKey.Print)
                ) == QKeySequence.SequenceMatch.ExactMatch
                _name_match = "print" in (_act.objectName() or "").lower()
                _text_match = "print" in (_act.text() or "").lower()
                if _shortcut_match or _name_match or _text_match:
                    try:
                        _act.triggered.disconnect()
                    except TypeError:
                        pass
                    _act.triggered.connect(_do_print)
                    _hooked = True
                    break
            if not _hooked:
                logger.warning(
                    "print_files_with_dialog: could not locate Print toolbar "
                    "action in QPrintPreviewDialog; printing directly at high resolution."
                )
                _do_print()
            else:
                if preview.exec() != QPrintPreviewDialog.DialogCode.Accepted:
                    cancelled = True

    if cancelled:
        return

    import subprocess as _sp
    lp = shutil.which('lp') if platform.system() != 'Windows' else None
    unprinted: list[str] = []

    for path in fallback:
        if platform.system() == 'Windows':
            try:
                os.startfile(path, 'print')  # type: ignore[attr-defined]
            except OSError:
                unprinted.append(os.path.basename(path))
        elif lp:
            _sp.Popen([lp, path])
        else:
            unprinted.append(os.path.basename(path))

    sections = []
    if unprinted:
        names = '\n'.join(f'  • {n}' for n in unprinted)
        sections.append(f"Could not be printed (no print handler registered):\n{names}")
    if failed_pre_render:
        names = '\n'.join(f'  • {n}' for n in failed_pre_render)
        sections.append(f"Could not be loaded for preview and were skipped:\n{names}")
    if failed_print_render:
        names = '\n'.join(f'  • {n}' for n in sorted(set(failed_print_render)))
        sections.append(f"Could not be rendered for printing:\n{names}")
    if sections:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(parent, "Print", "\n\n".join(sections))


def attach_file_preview(
    files_list,
    parent_layout,
    splitter_sizes=(320, 320),
    min_preview_width=200,
) -> FilePreviewWidget:
    """Remove files_list from parent_layout, wrap it with a FilePreviewWidget
    in a QSplitter, reinsert at the same index, and return the preview widget.
    The caller must connect currentRowChanged → preview_file.
    """
    list_index = parent_layout.indexOf(files_list)
    if list_index == -1:
        raise ValueError("files_list widget is not a direct child of parent_layout")
    parent_layout.removeWidget(files_list)
    files_list.setMaximumHeight(16777215)   # lift any UI-file height cap

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(files_list)

    preview = FilePreviewWidget()
    preview.setMinimumWidth(min_preview_width)
    splitter.addWidget(preview)
    splitter.setSizes(list(splitter_sizes))

    parent_layout.insertWidget(list_index, splitter)
    return preview
