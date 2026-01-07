"""
Remote settings and history synchronization utility

Handles syncing JSON files to/from a remote server path (network share, etc.)
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


class RemoteSyncManager:
    """Manages synchronization of settings and history files with remote server"""

    def __init__(self, remote_path: str):
        """
        Initialize the remote sync manager

        Args:
            remote_path: Network path or URL where files should be synced
                        (e.g., \\\\server\\share\\jobdocs or /mnt/share/jobdocs)
        """
        self.remote_path = Path(remote_path) if remote_path else None

    def is_enabled(self) -> bool:
        """Check if remote sync is configured and available"""
        if not self.remote_path:
            return False

        try:
            # Check if path exists and is accessible
            return self.remote_path.exists() and self.remote_path.is_dir()
        except (OSError, PermissionError):
            return False

    def load_json_from_remote(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Load a JSON file from the remote server

        Args:
            filename: Name of the JSON file (e.g., 'settings.json')

        Returns:
            Dictionary containing the JSON data, or None if not available
        """
        if not self.is_enabled():
            return None

        remote_file = self.remote_path / filename

        try:
            if remote_file.exists():
                with open(remote_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError, PermissionError) as e:
            print(f"Warning: Could not load {filename} from remote: {e}")

        return None

    def save_json_to_remote(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        Save a JSON file to the remote server

        Args:
            filename: Name of the JSON file (e.g., 'settings.json')
            data: Dictionary to save as JSON

        Returns:
            True if successful, False otherwise
        """
        if not self.is_enabled():
            return False

        remote_file = self.remote_path / filename

        try:
            # Ensure the remote directory exists
            self.remote_path.mkdir(parents=True, exist_ok=True)

            # Write the JSON file
            with open(remote_file, 'w') as f:
                json.dump(data, f, indent=2)

            return True
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not save {filename} to remote: {e}")
            return False

    def sync_from_remote(self, local_file: Path, filename: str) -> bool:
        """
        Sync a file FROM remote TO local (download)

        Args:
            local_file: Local file path
            filename: Remote filename

        Returns:
            True if sync occurred, False otherwise
        """
        if not self.is_enabled():
            return False

        remote_file = self.remote_path / filename

        try:
            if remote_file.exists():
                # Copy from remote to local
                shutil.copy2(remote_file, local_file)
                print(f"Synced {filename} from remote server")
                return True
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not sync {filename} from remote: {e}")

        return False

    def sync_to_remote(self, local_file: Path, filename: str) -> bool:
        """
        Sync a file FROM local TO remote (upload)

        Args:
            local_file: Local file path
            filename: Remote filename

        Returns:
            True if sync occurred, False otherwise
        """
        if not self.is_enabled():
            return False

        remote_file = self.remote_path / filename

        try:
            if local_file.exists():
                # Ensure remote directory exists
                self.remote_path.mkdir(parents=True, exist_ok=True)

                # Copy from local to remote
                shutil.copy2(local_file, remote_file)
                print(f"Synced {filename} to remote server")
                return True
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not sync {filename} to remote: {e}")

        return False
