"""
Shared utility functions for JobDocs

Common helper functions used across multiple modules.
"""

import ctypes
import json
import logging
import os
import platform
import shutil
import re
import stat
import subprocess
import tempfile
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def atomic_write_json(path: Path, data: Any) -> None:
    """Write data as JSON to path atomically.

    Writes to a temp file in the same directory, fsyncs it, then
    os.replace()s it into place. This gives torn-write visibility
    atomicity — no reader ever observes a half-written file — and a
    process kill or crash between the write and the rename leaves the
    original file untouched instead of truncated/empty, unlike plain
    `open(path, 'w')` which truncates the file the instant it's opened,
    before any new content is written.

    Two caveats worth being explicit about:
    - `os.replace()`'s atomicity is best-effort, not an absolute
      guarantee, on the kind of target this is often used for (a network
      share): older SMB/exFAT-backed NAS exports don't uniformly support
      atomic replace-over-existing-file semantics, and on Windows a
      sharing violation from AV/backup/indexing software holding the
      destination open can make the replace itself fail (raised as
      OSError — callers already handle that).
    - This only makes a single write internally consistent. It adds no
      locking or versioning across writers, so two app instances (or an
      instance racing the remote sync path) can still last-writer-wins at
      the load-mutate-save level. That's a pre-existing limitation, not
      something atomic writes solve.
    """
    path = Path(path)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    try:
        # mkstemp() hardcodes mode 0o600 on POSIX regardless of the process
        # umask, which would silently narrow permissions on every save once
        # os.replace() swaps the temp file's inode in. Restore the original
        # file's mode if it exists (preserving whatever was already set),
        # otherwise derive what a plain open(path, 'w') would have produced
        # under the current umask. Only a missing target falls back to the
        # probe -- any other stat() failure (permission denied, I/O error)
        # propagates instead of silently continuing with a guessed mode.
        try:
            desired_mode = stat.S_IMODE(os.stat(path).st_mode)
        except FileNotFoundError:
            # os.umask() would work but mutates the process-wide mask while
            # reading it, racing any other thread creating a file in that
            # window. Probe with a throwaway file instead -- the kernel
            # applies the umask when it's created, so its resulting mode
            # reveals the mask without ever touching the global umask value.
            probe_path = path.parent / f'.{path.name}.{uuid.uuid4().hex}.umask_probe'
            probe_fd = os.open(str(probe_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            try:
                desired_mode = stat.S_IMODE(os.fstat(probe_fd).st_mode)
            finally:
                os.close(probe_fd)
                os.unlink(probe_path)

        try:
            os.chmod(tmp_path, desired_mode)
        except OSError:
            # fd is still a raw descriptor from mkstemp() at this point --
            # os.fdopen() below hasn't taken ownership of it yet, so it must
            # be closed explicitly here or it leaks for the process's life.
            os.close(fd)
            raise

        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        # os.replace() already removed tmp_path on success; only cleans up
        # the leftover temp file if the write or replace failed partway.
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def is_reparse_point(full_path: str) -> bool:
    """True for a symlink or (Windows) NTFS junction/mount point.

    Shared by modules/search/module.py (folder-tree traversal) and
    AppContext.find_job_folders()/find_quote_folders() (live search and
    indexing) so a link planted under a permitted customer/blueprint
    directory can't be used to reach an excluded ITAR directory through any
    of those paths (CodeRabbit, PR #315).

    Fails closed on Windows: os.path.islink() doesn't reliably detect
    junctions/mount points there, so a GetFileAttributesW lookup failure
    (INVALID_FILE_ATTRIBUTES, or a raised exception) is treated as a
    reparse point rather than falling through to a check that could miss
    one (CodeRabbit, PR #315).
    """
    if os.name != "nt":
        return os.path.islink(full_path)
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(full_path)
    except (AttributeError, OSError):
        return True
    if attrs == -1:  # INVALID_FILE_ATTRIBUTES
        return True
    return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def is_kiosk_install() -> bool:
    """True when running as JobDocs Kiosk — see build_scripts/JobDocs.iss.

    Single source of truth for this check: main.py's _is_readonly_install()
    delegates here rather than duplicating the detection, and
    get_config_dir() below uses it to keep Kiosk's settings/history/search
    index isolated from a regular JobDocs install on the same machine.
    Windows-only; always False in dev checkouts, Flatpak, and a regular
    JobDocs install.

    Checks for kiosk_build.marker, which the Kiosk installer's [Files]
    section bakes into the install payload at build time (`iscc /DKIOSK`).
    An earlier version checked a marker file the installer wrote via a
    post-install script instead, which meant deleting it after install
    silently switched get_config_dir() to the full app's directory and
    disabled the AppContext persistence guard — not just the cosmetic
    window title/menu bar it was assumed to control (CodeRabbit, PR #315).
    Baking the check into the install payload itself closes that: nothing
    a user can delete post-install changes the answer.
    """
    if os.getenv('FLATPAK_ID'):
        return False
    # This file lives at <install>/app/shared/utils.py; main.py lives at
    # <install>/app/main.py — one more parent hop to reach the same app/ dir.
    app_dir = Path(__file__).resolve().parent.parent
    if not (app_dir.parent / 'runtime').is_dir():
        return False  # dev checkout, not an embedded install
    return (app_dir / 'shared' / 'kiosk_build.marker').exists()


def get_config_dir() -> Path:
    """Get the appropriate config directory for the current OS.

    JobDocs Kiosk gets its own subdirectory (a "Kiosk" suffix), isolated
    from a regular JobDocs install's settings/history/search index. The two
    are separate installers meant to coexist on one machine (see
    build_scripts/JobDocs.iss); sharing a config dir would mean uninstalling
    either one wipes the other's data.
    """
    suffix = ' Kiosk' if is_kiosk_install() else ''
    if platform.system() == "Windows":
        # Windows: C:\Users\<Username>\AppData\Local\JobDocs[ Kiosk]
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        config_dir = base / f'JobDocs{suffix}'
    elif platform.system() == "Darwin":
        # macOS: ~/Library/Application Support/JobDocs[ Kiosk]
        config_dir = Path.home() / 'Library' / 'Application Support' / f'JobDocs{suffix}'
    else:
        # Linux/other: ~/.local/share/JobDocs[ Kiosk]
        xdg_data = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
        config_dir = Path(xdg_data) / f'JobDocs{suffix}'

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_os_type() -> str:
    """Get simplified OS type"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    else:
        return "linux"


def get_os_text(key: str) -> str:
    """Get OS-specific text for various UI elements"""
    os_type = get_os_type()

    text_map = {
        # Terminology
        'folder_term': {
            'windows': 'folder',
            'macos': 'folder',
            'linux': 'directory'
        },
        'file_browser': {
            'windows': 'File Explorer',
            'macos': 'Finder',
            'linux': 'file manager'
        },

        # Link type info (FILES only - no admin needed!)
        'hard_link_note': {
            'windows': 'Hard Link (recommended - files must be on same volume)',
            'macos': 'Hard Link (recommended)',
            'linux': 'Hard Link (recommended)'
        },
        'symlink_note': {
            'windows': 'Symbolic Link (requires admin/Developer Mode)',
            'macos': 'Symbolic Link',
            'linux': 'Symbolic Link'
        },

        # Path separators
        'path_sep': {
            'windows': '\\',
            'macos': '/',
            'linux': '/'
        },
        'path_example': {
            'windows': '{customer}\\{job_folder}\\job documents',
            'macos': '{customer}/{job_folder}/job documents',
            'linux': '{customer}/{job_folder}/job documents'
        }
    }

    if key in text_map:
        return text_map[key].get(os_type, text_map[key]['linux'])
    return ""


_PO_RFQ_NAME_RE = re.compile(
    r'(?<![A-Za-z])p\.?o\.?(?![A-Za-z])'
    r'|purchase[\s_\-]?order'
    r'|(?<![A-Za-z])rfq(?![A-Za-z])'
    r'|request[\s_\-]?for[\s_\-]?quote',
    re.IGNORECASE,
)

_PO_RFQ_TEXT_RE = re.compile(
    r'purchase\s+order|p\.?o\.?\s*(?:#|number|num|no\.?)'
    r'|request\s+for\s+quote|rfq\s*(?:#|number|num|no\.?)',
    re.IGNORECASE,
)


_MAX_CLASSIFY_CACHE = 500
_classify_cache: OrderedDict[str, Tuple[float, bool, str]] = OrderedDict()  # path -> (mtime, flagged, reason)


def classify_document(filepath: str) -> Tuple[bool, str]:
    """
    Detect if a file is likely a PO or RFQ.
    Checks filename first, then first-page PDF text when PyMuPDF is available.
    Results are cached by file path and mtime to avoid blocking repeated searches.
    Returns (is_po_rfq, reason).
    """
    try:
        mtime = os.path.getmtime(filepath)
        cached = _classify_cache.get(filepath)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]
    except OSError:
        pass

    flagged, reason = _classify_document_uncached(filepath)
    try:
        _classify_cache[filepath] = (os.path.getmtime(filepath), flagged, reason)
        _classify_cache.move_to_end(filepath)
        if len(_classify_cache) > _MAX_CLASSIFY_CACHE:
            _classify_cache.popitem(last=False)
    except OSError:
        pass
    return flagged, reason


def _classify_document_uncached(filepath: str) -> Tuple[bool, str]:
    stem = os.path.splitext(os.path.basename(filepath))[0]
    if _PO_RFQ_NAME_RE.search(stem):
        return True, "filename contains PO/RFQ keyword"

    if filepath.lower().endswith('.pdf'):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            try:
                if doc.page_count > 0 and _PO_RFQ_TEXT_RE.search(doc[0].get_text()):
                    return True, "PDF content contains PO/RFQ keyword"
            finally:
                doc.close()
        except Exception as e:
            logger.debug("classify_document: could not read PDF '%s': %s", filepath, e)

    return False, ""


def is_blueprint_file(filename: str, blueprint_extensions: List[str]) -> bool:
    """
    Check if a file is a blueprint based on its extension.

    Args:
        filename: The filename to check
        blueprint_extensions: List of valid blueprint extensions (e.g., ['.pdf', '.dwg', '.dxf'])

    Returns:
        True if the file is a blueprint, False otherwise
    """
    ext = Path(filename).suffix.lower()
    return ext in [e.lower() for e in blueprint_extensions]


def parse_job_numbers(job_input: str) -> List[str]:
    """
    Parse job numbers from input string, supporting ranges and comma-separated values.

    Examples:
        "1,2,3" -> ["1", "2", "3"]
        "1-5" -> ["1", "2", "3", "4", "5"]
        "1,3-5,7" -> ["1", "3", "4", "5", "7"]

    Args:
        job_input: Input string containing job numbers

    Returns:
        List of parsed job numbers
    """
    job_numbers = []
    for part in job_input.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                range_parts = part.split('-')
                if len(range_parts) == 2:
                    start = int(range_parts[0].strip())
                    end = int(range_parts[1].strip())
                    if start <= end:
                        job_numbers.extend(str(n) for n in range(start, end + 1))
                        continue
            except ValueError:
                pass
        job_numbers.append(part)
    return job_numbers


def create_file_link(source: Path, dest: Path, link_type: str = 'hard') -> bool:
    """
    Create a file link (hard link, symbolic link, or copy).

    Args:
        source: Source file path
        dest: Destination file path
        link_type: Type of link ('hard', 'symbolic', or 'copy')

    Returns:
        True if successful, False otherwise
    """
    try:
        if link_type == 'hard':
            os.link(source, dest)
        elif link_type == 'symbolic':
            os.symlink(source, dest)
        else:
            shutil.copy2(source, dest)
        return True
    except OSError as e:
        logger.warning("create_file_link: failed to link %s -> %s (%s): %s", source, dest, link_type, e)
        return False


def sanitize_filename(filename: str) -> str:
    """
    Remove invalid characters from a filename.

    Args:
        filename: The filename to sanitize

    Returns:
        Sanitized filename
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


def open_folder(path: str) -> Tuple[bool, Optional[str]]:
    """
    Open a folder in the OS file browser.

    Args:
        path: Path to the folder to open

    Returns:
        Tuple of (success, error_message)
    """
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True, None
    except FileNotFoundError:
        return False, f"Folder not found: {path}"
    except PermissionError:
        return False, f"Permission denied: {path}"
    except Exception as e:
        return False, f"Failed to open folder: {e}"


def reveal_in_file_manager(path: str) -> Tuple[bool, Optional[str]]:
    """
    Open path's containing directory in the OS file browser with path
    itself selected/highlighted, rather than opening path as a listing.

    Args:
        path: Path to the file or folder to select

    Returns:
        Tuple of (success, error_message)
    """
    if not os.path.exists(path):
        return False, f"Not found: {path}"
    try:
        # abspath(), not normpath() -- a relative path would leave the
        # Linux branch's os.path.dirname() unable to find a real parent
        # (dirname('folder') is '', so xdg-open gets an empty operand and
        # fails silently since Popen() doesn't wait for the child).
        norm_path = os.path.abspath(path)
        system = platform.system()
        if system == "Windows":
            # explorer.exe's own exit code is unreliable and not meaningful to
            # check here. Must be a single command-line *string*, not a list:
            # Popen's list form quotes the whole "/select,<path>" token when
            # the path has a space, and explorer's parser doesn't understand
            # a quoted comma-prefix -- it silently falls back to opening the
            # default library instead of raising or erroring. Quoting only
            # the path (comma left bare) is the form explorer actually
            # understands. Safe from injection: `"` is not a legal character
            # in a Windows path, so norm_path can't break out of the quotes.
            subprocess.Popen(f'explorer /select,"{norm_path}"')
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", norm_path])
        else:
            # No universal "select in file manager" command on Linux across
            # file managers; open the containing directory as the best
            # available fallback (no highlight).
            subprocess.Popen(["xdg-open", os.path.dirname(norm_path)])
        return True, None
    except FileNotFoundError:
        return False, f"File manager not found for path: {path}"
    except PermissionError:
        return False, f"Permission denied: {path}"
    except Exception as e:
        return False, f"Failed to reveal path: {e}"


def print_files(paths: List[str]) -> None:
    """Send each file to the OS print handler (opens the system print dialog)."""
    for path in paths:
        if not os.path.isfile(path):
            continue
        if platform.system() == 'Windows':
            os.startfile(path, 'print')  # type: ignore[attr-defined]
        else:
            lp = shutil.which('lp')
            if lp:
                subprocess.Popen([lp, path])
            else:
                logger.warning("print_files: 'lp' not found — cannot print %s", path)


def get_next_number(history: Dict[str, Any], entry_type: str, start_number: int = 10000,
                    scan_dirs: list | None = None, quote_folder: str = 'Quotes') -> str:
    """
    Get the next sequential number for jobs or quotes.

    Checks both the in-memory history and (optionally) the file system so that
    folders created outside of JobDocs are not re-used.

    scan_dirs: list of base directories whose immediate subdirectory names are
               scanned for leading numbers (e.g. customer-files and blueprints
               dirs).  Two levels are walked: base→customer→folder so that
               quote folders nested inside a Quotes sub-directory are found.
    quote_folder: name of the quotes sub-directory (matches quote_folder_path
                  setting, defaults to 'Quotes').
    """
    _leading_num = re.compile(r'^[A-Za-z]?(\d+)')

    max_number = start_number - 1

    if entry_type == 'job':
        history_key = 'recent_jobs'
        number_key = 'job_number'
    elif entry_type == 'quote':
        history_key = 'recent_quotes'
        number_key = 'quote_number'
    else:
        return str(start_number)

    # --- history ---
    for entry in history.get(history_key, []):
        number_str = entry.get(number_key, '')
        try:
            digits = ''.join(filter(str.isdigit, number_str))
            if digits:
                n = int(digits)
                if n > max_number:
                    max_number = n
        except (ValueError, TypeError):
            continue

    # --- file system ---
    # Jobs live at base/customer/<job_folder>; skip the quotes sub-directory.
    # Quotes live at base/customer/<quote_folder>/<quote_folder_entry>.
    if scan_dirs:
        def _check(name: str) -> None:
            nonlocal max_number
            m = _leading_num.match(name)
            if m:
                n = int(m.group(1))
                if n > max_number:
                    max_number = n

        for base_dir in scan_dirs:
            if not base_dir or not os.path.isdir(base_dir):
                continue
            try:
                for customer in os.listdir(base_dir):
                    customer_path = os.path.join(base_dir, customer)
                    if not os.path.isdir(customer_path):
                        continue
                    try:
                        if entry_type == 'quote':
                            quotes_path = os.path.join(customer_path, quote_folder)
                            if os.path.isdir(quotes_path):
                                for name in os.listdir(quotes_path):
                                    _check(name)
                        else:
                            for name in os.listdir(customer_path):
                                if name.lower() != quote_folder.lower():
                                    _check(name)
                    except OSError:
                        continue
            except OSError:
                continue

    return str(max_number + 1)
