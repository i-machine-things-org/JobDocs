"""
Shared utility functions for JobDocs

Common helper functions used across multiple modules.
"""

import os
import platform
import shutil
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


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
    import subprocess
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


def get_next_number(history: Dict[str, Any], entry_type: str, start_number: int = 10000) -> str:
    """
    Get the next sequential number for jobs or quotes (tracked separately).

    Args:
        history: Application history dictionary
        entry_type: Type of entry ('job' or 'quote')
        start_number: Starting number if no history exists (default: 10000)

    Returns:
        Next number as a string
    """
    max_number = start_number - 1

    # Determine which history key to use (jobs and quotes are tracked separately)
    if entry_type == 'job':
        history_key = 'recent_jobs'
        number_key = 'job_number'
    elif entry_type == 'quote':
        history_key = 'recent_quotes'
        number_key = 'quote_number'
    else:
        return str(start_number)

    # Check history for the highest number
    recent_entries = history.get(history_key, [])
    for entry in recent_entries:
        number_str = entry.get(number_key, '')
        # Try to parse as integer
        try:
            number = int(number_str)
            if number > max_number:
                max_number = number
        except ValueError:
            # Not a pure number, skip it
            continue

    return str(max_number + 1)
