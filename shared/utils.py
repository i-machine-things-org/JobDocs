"""
Shared utility functions for JobDocs

Common helper functions used across multiple modules.
"""

import logging
import os
import platform
import shutil
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """Get the appropriate config directory for the current OS"""
    if platform.system() == "Windows":
        # Windows: C:\Users\<Username>\AppData\Local\JobDocs
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        config_dir = base / 'JobDocs'
    elif platform.system() == "Darwin":
        # macOS: ~/Library/Application Support/JobDocs
        config_dir = Path.home() / 'Library' / 'Application Support' / 'JobDocs'
    else:
        # Linux/other: ~/.local/share/JobDocs
        xdg_data = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
        config_dir = Path(xdg_data) / 'JobDocs'

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
    except OSError:
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
