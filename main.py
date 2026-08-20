#!/usr/bin/env python3
"""
JobDocs - Modular Blueprint and Job Management System

Main application entry point using the modular plugin architecture.
"""

import argparse
import io
import logging
import os
import shutil
import subprocess
import sys
import json
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox, QDialog,
    QInputDialog, QLineEdit, QProgressDialog,
    QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox, QWidget,
)

from core.module_loader import ModuleLoader
from core.app_context import AppContext
from core.base_module import BaseModule
from shared.utils import atomic_write_json, get_config_dir, get_os_text, is_kiosk_install
from shared.remote_sync import RemoteSyncManager

logger = logging.getLogger(__name__)


def _get_app_version() -> str:
    
    try:
        from core._version import __version__ as _v
        if _v and _v != "dev":
            return _v
    except ImportError:
        pass
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=3,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "dev"


def _is_readonly_install() -> bool:
    """True when running as "JobDocs Kiosk" — see build_scripts/JobDocs.iss.

    JobDocs Kiosk is a separate installer/product (own AppId, own release
    asset — not a Task checkbox on the main installer): a search-only kiosk
    build for shared/shop-floor machines. Detected via a marker file its
    installer drops next to app/runtime/plugins. Windows-only; always False
    in dev checkouts, Flatpak, and the regular JobDocs install.

    This flag only controls UI chrome and the AppContext persistence guard —
    the window title, hidden menu bar, and forced "search only" module list
    (see load_modules() below). It is not itself the containment: the Kiosk
    build's [Files] selection (build_scripts/JobDocs.iss) never copies
    write-capable modules to disk in the first place, so deleting this
    marker on a Kiosk install has nothing to unlock. Real access control
    for a shared machine still requires a separately managed Windows account
    with the install directory locked down.

    Delegates to shared.utils.is_kiosk_install() — the single source of
    truth, also used by get_config_dir() to isolate Kiosk's settings/
    history/search index from a regular JobDocs install on the same
    machine.
    """
    return is_kiosk_install()


APP_VERSION = _get_app_version()
_GITHUB_REPO = "i-machine-things-org/JobDocs"


def _version_tuple(v: str) -> tuple:
    try:
        numeric = v.lstrip("v").split("-")[0]  # strip pre-release suffix (e.g. -rc1, -test)
        return tuple(int(x) for x in numeric.split(".")[:3])
    except ValueError:
        return (0, 0, 0)


class _UpdateChecker(QThread):
    """Queries the GitHub releases API on a background thread."""
    update_available = pyqtSignal(str, str, str)  # (tag, html_url, asset_url)
    up_to_date = pyqtSignal()

    def run(self):
        try:
            url = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "JobDocs"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "")
            html_url = data.get("html_url", "")
            if tag and _version_tuple(tag) > _version_tuple(APP_VERSION):
                # A release carries two Windows installers (JobDocs and
                # JobDocs Kiosk) — match this install's own variant by
                # filename, not just "the first .exe", or a Kiosk machine
                # could silently be offered the full installer and vice
                # versa. See _is_readonly_install() for what "kiosk" means.
                is_kiosk = _is_readonly_install()
                asset_url = ""
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe") and ("kiosk" in name) == is_kiosk:
                        asset_url = asset.get("browser_download_url", "")
                        break
                self.update_available.emit(tag, html_url, asset_url)
            else:
                self.up_to_date.emit()
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
            pass


class _UpdateDownloader(QThread):
    """Downloads a release asset to a temp file on a background thread."""
    progress = pyqtSignal(int, int)  # (bytes_done, total_bytes)
    finished = pyqtSignal(str)       # dest_path on success
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, asset_url: str, dest_path: str):
        super().__init__()
        self._asset_url = asset_url
        self._dest_path = dest_path

    def run(self):
        try:
            if not self._asset_url.startswith("https://"):
                self.error.emit("Invalid asset URL scheme")
                return
            req = urllib.request.Request(
                self._asset_url,
                headers={"User-Agent": "JobDocs"},
            )
            cancelled = False
            with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
                total = int(resp.headers.get("Content-Length", 0))
                done = 0
                with open(self._dest_path, "wb") as f:
                    while True:
                        if self.isInterruptionRequested():
                            cancelled = True
                            break
                        buf = resp.read(65536)
                        if not buf:
                            break
                        f.write(buf)
                        done += len(buf)
                        self.progress.emit(done, total)
            if cancelled:
                try:
                    os.remove(self._dest_path)
                except OSError:
                    pass
                self.cancelled.emit()
                return
            if total > 0 and done != total:
                try:
                    os.remove(self._dest_path)
                except OSError:
                    pass
                self.error.emit(f"Download truncated: received {done} of {total} bytes")
                return
            self.finished.emit(self._dest_path)
        except Exception as exc:
            try:
                os.remove(self._dest_path)
            except OSError:
                pass
            self.error.emit(str(exc))


class _UpdateDialog(QDialog):
    """Non-blocking update-available prompt."""

    def __init__(self, latest_version: str, release_url: str, asset_url: str, app_context, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setMinimumWidth(340)
        self._app_context = app_context
        self._latest_version = latest_version
        self._release_url = release_url
        self._asset_url = asset_url

        import platform as _platform
        self._is_flatpak = _platform.system() == 'Linux' and bool(os.getenv('FLATPAK_ID'))
        self._can_download = _platform.system() == 'Windows' and bool(asset_url)

        layout = QVBoxLayout(self)

        import html as _html
        label = QLabel(f"<b>{_html.escape(latest_version)}</b> is available. Upgrade now?")
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        self._disable_cb = QCheckBox("Don't show update notifications")
        layout.addWidget(self._disable_cb)

        buttons = QDialogButtonBox()
        ok_label = "Download && Install" if self._can_download else "Update Now"
        buttons.addButton(ok_label, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("Skip This Version", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self._on_later)
        layout.addWidget(buttons)

    def _save_disabled(self) -> None:
        if self._disable_cb.isChecked() and self._app_context is not None:
            self._app_context.set_setting('updates_notifications_disabled', True)
            self._app_context.save_settings()

    def _on_ok(self) -> None:
        self._save_disabled()
        if self._is_flatpak:
            try:
                subprocess.Popen(
                    ['flatpak-spawn', '--host', 'xdg-open',
                     'appstream://io.github.i_machine_things.JobDocs'],
                )
            except Exception:
                import webbrowser
                webbrowser.open(self._release_url)
            self.accept()
        elif self._can_download:
            self._start_download()
        else:
            import webbrowser
            webbrowser.open(self._release_url)
            self.accept()

    def _start_download(self) -> None:
        safe_ver = ''.join(c if c.isalnum() or c in '._-' else '_' for c in self._latest_version)
        fd, dest = tempfile.mkstemp(suffix=".exe", prefix=f"JobDocs-{safe_ver}-")
        os.close(fd)

        progress_dlg = QProgressDialog(
            f"Downloading {self._latest_version}...", "Cancel", 0, 100, self,
        )
        progress_dlg.setWindowTitle("Downloading Update")
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)

        downloader = _UpdateDownloader(self._asset_url, dest)
        self._downloader = downloader
        progress_dlg.canceled.connect(downloader.requestInterruption)

        def _on_progress(done: int, total: int) -> None:
            progress_dlg.setValue(int(done * 100 / total) if total else 50)

        def _on_done(path: str) -> None:
            progress_dlg.close()
            try:
                with open(path, 'rb') as _f:
                    if _f.read(2) != b'MZ':
                        raise ValueError("Not a valid Windows executable (bad MZ header)")
                    _f.seek(0x3C)
                    e_lfanew = int.from_bytes(_f.read(4), 'little')
                    _f.seek(e_lfanew)
                    if _f.read(4) != b'PE\x00\x00':
                        raise ValueError("Not a valid Windows executable (bad PE signature)")
            except (OSError, ValueError) as exc:
                QMessageBox.critical(
                    self, "Verification Failed",
                    f"The downloaded installer failed verification:\n{exc}\n\n"
                    "Opening the releases page instead.",
                )
                try:
                    os.remove(path)
                except OSError:
                    pass
                import webbrowser
                webbrowser.open(self._release_url)
                self.accept()
                return
            reply = QMessageBox.question(
                self, "Ready to Install",
                f"{self._latest_version} downloaded.\n\n"
                "JobDocs will close and the installer will launch.\nReady to install?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    subprocess.Popen([path])
                except OSError as exc:
                    QMessageBox.critical(
                        self, "Launch Failed",
                        f"Could not launch the installer:\n{exc}\n\nInstaller saved at:\n{path}",
                    )
                    self.accept()
                    return
                QApplication.quit()
            self.accept()

        def _on_cancelled() -> None:
            progress_dlg.close()

        def _on_error(msg: str) -> None:
            progress_dlg.close()
            QMessageBox.warning(
                self, "Download Failed",
                f"Could not download the update:\n{msg}\n\nOpening the releases page instead.",
            )
            import webbrowser
            webbrowser.open(self._release_url)
            self.accept()

        downloader.progress.connect(_on_progress)
        downloader.finished.connect(_on_done)
        downloader.cancelled.connect(_on_cancelled)
        downloader.error.connect(_on_error)
        downloader.finished.connect(downloader.deleteLater)
        downloader.cancelled.connect(downloader.deleteLater)
        downloader.error.connect(downloader.deleteLater)
        downloader.start()

    def _on_later(self) -> None:
        self._save_disabled()
        if self._app_context is not None:
            self._app_context.set_setting('updates_skipped_version', self._latest_version)
            self._app_context.save_settings()
        self.reject()


def _parse_prefill_args(argv: list) -> tuple:
    """Extract JobDocs prefill args from argv.

    Returns (prefill_dict, remaining_argv_for_qt). Known flags (--customer,
    --j_no, --q_no, --po_no, --desc, --drawings) are consumed; unrecognised
    args are left in remaining so Qt can consume platform/style flags.
    """
    parser = argparse.ArgumentParser(prog='JobDocs', add_help=False)
    parser.add_argument('--customer', metavar='NAME')
    parser.add_argument('--j_no', metavar='NUMBER')
    parser.add_argument('--q_no', metavar='NUMBER')
    parser.add_argument('--po_no', metavar='NUMBER')
    parser.add_argument('--po_line', metavar='LINE')
    parser.add_argument('--desc', metavar='TEXT')
    parser.add_argument('--drawings', metavar='NUMS',
                        help='Comma-separated drawing numbers')
    parser.add_argument('--revision', metavar='REV')
    known, remaining = parser.parse_known_args(argv)

    prefill = {k: v for k, v in vars(known).items() if v is not None}
    return prefill, remaining


def _flatpak_dns_fix() -> None:
    """Patch socket.getaddrinfo for Flatpak sandboxes where DNS fails.

    On systemd-resolved distros, /etc/resolv.conf contains 'nameserver 127.0.0.53'
    (the stub resolver). That address only listens on the host loopback and is
    unreachable inside the Flatpak network namespace, causing Errno -3 on every
    name lookup. This reads the real upstream nameservers and falls back to a
    direct UDP DNS query when the system resolver fails.
    """
    if not os.getenv('FLATPAK_ID'):
        return
    import re
    import socket
    import struct
    import random

    try:
        socket.getaddrinfo('github.com', 443, socket.AF_INET)
        return  # DNS works — nothing to do
    except (socket.gaierror, OSError):
        pass

    nameservers: list = []
    for path in ('/run/systemd/resolve/resolv.conf',
                 '/run/host/etc/resolv.conf',
                 '/etc/resolv.conf'):
        try:
            with open(path) as _f:
                for _line in _f:
                    _m = re.match(r'^nameserver\s+(\S+)', _line)
                    if _m:
                        _ns = _m.group(1)
                        if not _ns.startswith('127.') and _ns != '::1':
                            nameservers.append(_ns)
        except OSError:
            continue
        if nameservers:
            break

    if not nameservers:
        nameservers = ['1.1.1.1', '8.8.8.8']

    def _dns_a(host: str, ns: str) -> list:
        """Minimal DNS A-record query sent directly to nameserver ns."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        try:
            qid = random.randint(0, 65535)
            labels = b''.join(bytes([len(p)]) + p.encode()
                              for p in host.rstrip('.').split('.')) + b'\x00'
            pkt = (struct.pack('!HHHHHH', qid, 0x0100, 1, 0, 0, 0)
                   + labels + struct.pack('!HH', 1, 1))
            sock.sendto(pkt, (ns, 53))
            resp = sock.recv(512)
        finally:
            sock.close()
        ancount = struct.unpack('!H', resp[6:8])[0]
        pos = 12
        while resp[pos]:
            pos += resp[pos] + 1
        pos += 5
        ips: list = []
        for _ in range(ancount):
            if resp[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while resp[pos]:
                    pos += resp[pos] + 1
                pos += 1
            if pos + 10 > len(resp):
                break
            rtype, _, _, rdlen = struct.unpack('!HHIH', resp[pos:pos + 10])
            pos += 10
            if rtype == 1 and rdlen == 4:
                ips.append(socket.inet_ntoa(resp[pos:pos + 4]))
            pos += rdlen
        return ips

    _orig_getaddrinfo = socket.getaddrinfo
    _ns_list = nameservers[:]

    def _getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        try:
            return _orig_getaddrinfo(host, port, family, type, proto, flags)
        except (socket.gaierror, OSError):
            pass
        p = port if isinstance(port, int) else 0
        for _ns in _ns_list:
            try:
                for _ip in _dns_a(host, _ns):
                    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (_ip, p)),
                            (socket.AF_INET, socket.SOCK_DGRAM, 17, '', (_ip, p))]
            except Exception:
                continue
        return _orig_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = _getaddrinfo


_flatpak_dns_fix()


class _PluginInstallWorker(QThread):
    """Background worker that downloads and extracts a GitHub plugin."""

    success = pyqtSignal(str, str, str)  # module_name, dest_path, dep_warning
    error = pyqtSignal(str)
    status = pyqtSignal(str)  # progress message for the UI

    def __init__(self, owner: str, repo: str, plugins_dir: Path):
        super().__init__()
        self._owner = owner
        self._repo = repo
        self._plugins_dir = plugins_dir

    def _install_deps(self, plugin_dir: Path) -> str:
        """Install plugin requirements into a JobDocs-managed deps directory.

        Deps land in <data_dir>/deps/ (a sibling of plugins/) so they are
        isolated from the system Python and survive across plugin updates.
        Returns a non-empty warning string on failure, or '' on success /
        no requirements.txt present.
        """
        req_file = plugin_dir / 'requirements.txt'
        if not req_file.exists():
            return ''

        # deps/ is a sibling of plugins/ inside the writable data dir
        deps_dir = plugin_dir.parent.parent / 'deps'
        deps_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.status.emit("Installing dependencies...")
            if os.getenv('FLATPAK_ID'):
                # /app is read-only at runtime; spawn pip on the host so it can
                # write to the deps dir (same absolute path, accessible on host).
                cmd = ['flatpak-spawn', '--host', 'pip', 'install',
                       '--target', str(deps_dir),
                       '--no-warn-script-location', '-r', str(req_file)]
                flags = 0
            else:
                cmd = [sys.executable, '-m', 'pip', 'install',
                       '--target', str(deps_dir),
                       '--no-warn-script-location', '-r', str(req_file)]
                flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=flags,
            )
            output_lines: list[str] = []
            for line in proc.stdout:  # type: ignore[union-attr]
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    self.status.emit(line)
            proc.wait(timeout=300)
            if proc.returncode == 0:
                return ''
            err = '\n'.join(output_lines[-20:])
            return (f"\n\nDependency installation failed.\n"
                    f"Error: {err}")
        except Exception as exc:
            return f"\n\nDependency installation failed: {exc}"

    def run(self):
        owner, repo = self._owner, self._repo
        plugins_dir = self._plugins_dir

        # Fix CR: wrap mkdir so PermissionError is surfaced via error signal
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.error.emit(f"Could not create plugins directory:\n{plugins_dir}\n\n{e}")
            return

        # Fix CR: resolve default branch from GitHub API; fall back to main/master
        branches_to_try: list = []
        self.status.emit(f"Connecting to GitHub ({owner}/{repo})...")
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
                meta = json.loads(resp.read())
            branches_to_try = [meta.get("default_branch", "main")]
        except Exception:
            branches_to_try = ["main", "master"]

        last_error = None
        for branch in branches_to_try:
            zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
            try:
                self.status.emit(f"Downloading {owner}/{repo}...")
                with urllib.request.urlopen(zip_url, timeout=30) as resp:  # nosec B310
                    zip_data = resp.read()

                self.status.emit("Extracting files...")
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    top_dirs = {n.split('/')[0] for n in zf.namelist() if '/' in n}
                    if len(top_dirs) != 1:
                        self.error.emit("Unexpected ZIP structure — could not determine module root.")
                        return
                    zip_root = top_dirs.pop()

                    with tempfile.TemporaryDirectory() as tmp:
                        zf.extractall(tmp)
                        src_root = Path(tmp) / zip_root

                        if (src_root / 'module.py').exists():
                            dest = plugins_dir / repo
                            module_name = repo
                            src = src_root
                        else:
                            candidates = [
                                d for d in src_root.iterdir()
                                if d.is_dir() and (d / 'module.py').exists()
                            ]
                            if not candidates:
                                self.error.emit(
                                    f"No module.py found in {owner}/{repo}. "
                                    "Ensure the repo contains a JobDocs plugin module."
                                )
                                return
                            # Fix CR: fail fast if multiple plugin roots are found
                            if len(candidates) > 1:
                                self.error.emit(
                                    f"Found multiple plugin roots in {owner}/{repo}. "
                                    "Ensure the repo contains exactly one JobDocs plugin module."
                                )
                                return
                            module_folder = candidates[0]
                            dest = plugins_dir / module_folder.name
                            module_name = module_folder.name
                            src = module_folder

                        # Fix CR: backup-then-swap so the old plugin survives a failed rename
                        tmp_dest = dest.with_name(dest.name + '.tmp')
                        backup_dest = dest.with_name(dest.name + '.bak')
                        try:
                            if tmp_dest.exists():
                                shutil.rmtree(tmp_dest)
                            if backup_dest.exists():
                                shutil.rmtree(backup_dest)
                            shutil.copytree(src, tmp_dest)
                            if dest.exists():
                                dest.rename(backup_dest)
                            tmp_dest.rename(dest)
                            if backup_dest.exists():
                                shutil.rmtree(backup_dest)
                        except Exception:
                            if tmp_dest.exists():
                                shutil.rmtree(tmp_dest, ignore_errors=True)
                            if backup_dest.exists() and not dest.exists():
                                backup_dest.rename(dest)
                            raise

                dep_warning = self._install_deps(dest)
                self.success.emit(module_name, str(dest), dep_warning)
                return

            except urllib.error.HTTPError as e:
                last_error = str(e)
                continue
            except Exception as e:
                self.error.emit(f"Download failed:\n{e}")
                return

        self.error.emit(
            f"Could not download {owner}/{repo} (tried: {', '.join(branches_to_try)}).\n{last_error}"
        )


class JobDocsMainWindow(QMainWindow):
    """Main application window with modular plugin system"""

    DEFAULT_SETTINGS = {
        'blueprints_dir': '',
        'customer_files_dir': '',
        'itar_blueprints_dir': '',
        'itar_customer_files_dir': '',
        'link_type': 'hard',
        'blueprint_extensions': ['.pdf', '.dwg', '.dxf'],
        'allow_duplicate_jobs': False,
        'ui_style': 'Fusion',
        'job_folder_structure': '{customer}/job documents/{job_folder}',
        # 'quote_folder_path': 'Quotes',
        'legacy_mode': True,
        'default_tab': 0,
        # 'experimental_features': False,
        'disabled_modules': [],  # List of disabled module names
        # 'db_type': 'mssql',
        # 'db_host': 'localhost',
        # 'db_port': 1433,
        # 'db_name': '',
        # 'db_username': '',
        # 'db_password': '',
        # 'remote_server_path': '',  # Network path or URL for remote settings sync
        'report_template_path': '',  # Path to Excel template for Report Fixer
        'suppress_bp_link_notification': False,  # Suppress "linked to blueprints" confirmation dialog
        'skip_image_attachments': True,
    }

    def __init__(self, prefill: Dict[str, str] | None = None):
        super().__init__()

        # Configuration
        self.config_dir = get_config_dir()
        self.settings_file = self.config_dir / 'settings.json'
        self.history_file = self.config_dir / 'history.json'

        # Read-only (search-only) install: only the Search tab loads, and the
        # menu bar (Settings, Install Plugin, etc.) is hidden entirely. This
        # must be determined *before* settings/history are loaded so the
        # local-cache write-back paths in load_settings()/load_history() below
        # can respect it — read-only mode must prevent all automatic
        # persistence, not just the module-selection/UI behavior.
        self.readonly_mode = _is_readonly_install()

        # Load settings first (needed for remote sync setup)
        self.settings = self.load_settings()

        # Initialize remote sync manager
        remote_path = self.settings.get('remote_server_path', '')
        self.remote_sync = RemoteSyncManager(remote_path)

        self.history = self.load_history()
        self.modules = []  # Store loaded modules
        self._pending_tab_modules: Dict[int, BaseModule] = {}  # lazy tab construction
        self._available_modules_cache: List[tuple] = []  # for Settings dialog

        # Setup UI
        self.setWindowTitle("JobDocs — Search" if self.readonly_mode else "JobDocs")
        self.resize(700, 600)
        self._set_window_icon()

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create app context for modules
        self.app_context = AppContext(
            settings=self.settings,
            history=self.history,
            config_dir=self.config_dir,
            save_settings_callback=self.save_settings,
            save_history_callback=self.save_history,
            log_message_callback=self.log_message,
            show_error_callback=self.show_error_dialog,
            show_info_callback=self.show_info_dialog,
            get_customer_list_callback=self.get_customer_list,
            add_to_history_callback=self.add_to_history,
            main_window=self,
            readonly_mode=self.readonly_mode
        )

        # Load modules
        self.load_modules()

        # Setup menu (read-only installs hide the menu bar entirely — there's
        # nothing behind it to reach: Settings, Install Plugin, other tabs)
        if not self.readonly_mode:
            self.setup_menu()

        # Apply UI style
        self.apply_ui_style()

        # Apply email attachment settings
        from shared.widgets import DropZone
        DropZone.set_skip_image_attachments(self.settings.get('skip_image_attachments', True))

        # Set default tab (stored as display name string; fall back to integer for old settings)
        default_tab = self.settings.get('default_tab', 0)
        if isinstance(default_tab, str):
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == default_tab:
                    self.tabs.setCurrentIndex(i)
                    break
            else:
                print(f"[JobDocs] Warning: saved default tab '{default_tab}' not found; using first tab", flush=True)
        elif isinstance(default_tab, int) and 0 <= default_tab < self.tabs.count():
            self.tabs.setCurrentIndex(default_tab)

        # setCurrentIndex() above only emits currentChanged if the index
        # actually changed — e.g. index 0 was already current by default, so
        # the lazy-build handler never fires for it on its own. Force-build
        # whichever tab actually ends up shown; a no-op for anything already built.
        self._on_tab_activated(self.tabs.currentIndex())

        self.statusBar().showMessage("Ready")  # pyright: ignore[reportOptionalMemberAccess]

        if prefill:
            self._apply_prefill(prefill)

    # ==================== Settings & History ====================

    _KIOSK_DIR_SETTING_KEYS = (
        'customer_files_dir', 'itar_customer_files_dir',
        'blueprints_dir', 'itar_blueprints_dir',
    )

    def _apply_kiosk_dirs_override(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Override the four directory settings from {app}/kiosk_dirs.json
        on a Kiosk install.

        JobDocs Kiosk has no Settings UI and doesn't ship the OOBE wizard
        (both write-capable admin tools, excluded from its installer's
        [Files] selection) — its search directories are configured once at
        install time instead (build_scripts/JobDocs.iss's custom wizard
        pages write this file). Always wins over settings.json for these
        four keys on a Kiosk install: kiosk_dirs.json is the actual source
        of truth here, and a Kiosk install never writes settings.json
        itself (see save_settings()'s readonly_mode guard) so there would
        be no other way to reconfigure them short of reinstalling anyway.
        """
        if not self.readonly_mode:
            return settings
        kiosk_dirs_file = Path(__file__).resolve().parent.parent / 'kiosk_dirs.json'
        if not kiosk_dirs_file.exists():
            return settings
        try:
            with open(kiosk_dirs_file, 'r', encoding='utf-8') as f:
                kiosk_dirs = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load kiosk_dirs.json: {e}")
            return settings
        for key in self._KIOSK_DIR_SETTING_KEYS:
            if key in kiosk_dirs:
                settings[key] = kiosk_dirs[key]
        return settings

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file, trying remote server first if configured"""
        # First try to load from local to get remote_server_path
        local_settings = None
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    local_settings = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load local settings: {e}")

        # If we have a remote path configured, try loading from remote (remote is source of truth)
        if local_settings and local_settings.get('remote_server_path'):
            remote_sync = RemoteSyncManager(local_settings['remote_server_path'])
            remote_settings = remote_sync.load_json_from_remote('settings.json')
            if remote_settings:
                # Remote settings loaded successfully - use them
                merged = self.DEFAULT_SETTINGS.copy()
                merged.update(remote_settings)
                # Save to local to keep in sync — never on a read-only
                # (search-only) install, which must not write a local cache.
                if not self.readonly_mode:
                    try:
                        atomic_write_json(self.settings_file, merged)
                    except OSError:
                        pass
                return self._apply_kiosk_dirs_override(merged)

        # Fall back to local settings
        if local_settings:
            merged = self.DEFAULT_SETTINGS.copy()
            merged.update(local_settings)
            return self._apply_kiosk_dirs_override(merged)

        return self._apply_kiosk_dirs_override(self.DEFAULT_SETTINGS.copy())

    def save_settings(self):
        """Save settings to file and sync to remote server if configured"""
        if self.readonly_mode:
            logger.debug("save_settings: skipped (read-only install)")
            return
        try:
            # Save locally first
            atomic_write_json(self.settings_file, self.settings)

            # Sync to remote if configured
            if self.remote_sync.is_enabled():
                self.remote_sync.save_json_to_remote('settings.json', self.settings)

        except OSError as e:
            self.show_error_dialog("Error", f"Failed to save settings: {e}")

    def load_history(self) -> Dict[str, Any]:
        """Load history from file, trying remote server first if configured"""
        # Try loading from remote first (remote is source of truth)
        if self.remote_sync.is_enabled():
            remote_history = self.remote_sync.load_json_from_remote('history.json')
            if remote_history:
                # Save to local to keep in sync — never on a read-only
                # (search-only) install, which must not write a local cache.
                if not self.readonly_mode:
                    try:
                        atomic_write_json(self.history_file, remote_history)
                    except OSError:
                        pass
                return remote_history

        # Fall back to local history
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load history: {e}")

        return {'customers': {}, 'recent_jobs': []}

    def save_history(self):
        """Save history to file and sync to remote server if configured"""
        if self.readonly_mode:
            logger.debug("save_history: skipped (read-only install)")
            return
        try:
            # Save locally first
            atomic_write_json(self.history_file, self.history)

            # Sync to remote if configured
            if self.remote_sync.is_enabled():
                self.remote_sync.save_json_to_remote('history.json', self.history)

        except OSError as e:
            self.show_error_dialog("Error", f"Failed to save history: {e}")

    # ==================== Window Icon ====================

    def _set_window_icon(self):
        """Set application window icon from bundled or filesystem icon."""
        # PyInstaller frozen: data files land in sys._MEIPASS.
        # Embedded Python: icon is staged into app/ alongside main.py.
        # Dev: same directory as main.py.
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).resolve().parent
        candidates = [
            base / 'windows' / 'icon.ico',
            base / 'JobDocs.iconset' / 'icon_256x256.png',
        ]
        for path in candidates:
            if path.exists():
                self.setWindowIcon(QIcon(str(path)))
                return
        # Flatpak / system install: icon is in the hicolor theme, not next to main.py
        theme_icon = QIcon.fromTheme("io.github.i_machine_things.JobDocs")
        if not theme_icon.isNull():
            self.setWindowIcon(theme_icon)

    # ==================== Module Loading ====================

    def _get_plugins_dir(self) -> Path:
        """Return the plugins directory.

        Embedded install layout:
            {app}/app/main.py   ← __file__
            {app}/runtime/      ← signals we're in an embedded install
            {app}/plugins/      ← plugins live here

        Dev / source layout:
            repo/main.py
            repo/plugins/       ← plugins live here

        Flatpak: /app is read-only at runtime; plugins must live in the
        per-user writable data dir so they survive across app updates.
        """
        flatpak_id = os.getenv('FLATPAK_ID')
        if flatpak_id:
            xdg_data = os.getenv('XDG_DATA_HOME') or os.path.join(
                os.path.expanduser('~'), '.var', 'app', flatpak_id, 'data'
            )
            return Path(xdg_data) / 'plugins'
        app_dir = Path(__file__).resolve().parent
        if (app_dir.parent / 'runtime').is_dir():
            return app_dir.parent / 'plugins'
        return app_dir / 'plugins'

    def load_modules(self):
        """Load all modules using the module loader"""
        modules_dir = Path(__file__).parent / 'modules'
        loader = ModuleLoader(modules_dir, plugins_dir=self._get_plugins_dir())

        try:
            # Load modules with experimental flag and disabled modules list
            experimental_enabled = self.settings.get('experimental_features', False)
            if self.readonly_mode:
                # Only the search module loads; ignore the user's disabled_modules
                # setting entirely so a synced settings.json can't re-enable tabs.
                disabled_modules = [
                    name for name in loader.discover_modules() if name != 'search'
                ]
            else:
                disabled_modules = self.settings.get('disabled_modules', [])
            self.modules = loader.load_all_modules(self.app_context, experimental_enabled, disabled_modules)

            if not self.modules:
                QMessageBox.warning(
                    self,
                    "No Modules",
                    "No modules were loaded. Check the modules/ directory."
                )
                return

            # Cache the (module_name, display_name) list once instead of having
            # open_settings() re-discover and re-instantiate every module class
            # on every single Settings-dialog open.
            self._available_modules_cache = self._discover_available_modules(loader)

            # Add each tab module as an empty placeholder; its real widget is
            # only built (get_widget()) the first time that tab is actually
            # activated, via _on_tab_activated below — building every module's
            # full widget tree (and, for Job/Quote, the customer-list data
            # that comes with it) eagerly at startup wastes memory on tabs the
            # user may never open in this session.
            self._pending_tab_modules: Dict[int, BaseModule] = {}
            for module in self.modules:
                if not module.is_tab_module():
                    continue
                try:
                    name = module.get_name()
                    placeholder = QWidget()
                    index = self.tabs.addTab(placeholder, name)
                    self._pending_tab_modules[index] = module
                except Exception as e:
                    self.log_message(f"ERROR: Failed to register module {module.__class__.__name__}: {e}")
                    import traceback
                    traceback.print_exc()

            self.tabs.currentChanged.connect(self._on_tab_activated)

            self.statusBar().showMessage(  # pyright: ignore[reportOptionalMemberAccess]
                f"Loaded {len(self.modules)} module(s)"
            )

            # Kick off the search index build after the event loop starts
            QTimer.singleShot(0, self._start_search_indexer)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Module Load Error",
                f"Failed to load modules:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def _start_search_indexer(self):
        # The search index is a local performance cache, not a write into
        # shop job/blueprint directories, so read-only installs still build
        # and use it — a read-only kiosk searching a large shared drive is
        # exactly the case that benefits most from not re-walking the
        # filesystem on every query.
        for module in self.modules:
            if hasattr(module, 'start_indexer'):
                try:
                    module.start_indexer()
                except Exception as exc:
                    logger.warning("_start_search_indexer: %s: %s", module.__class__.__name__, exc)

    def _discover_available_modules(self, loader: ModuleLoader) -> List[tuple]:
        """Discover every module on disk (regardless of enabled/disabled state)
        and its display name, for the Settings dialog's module list. Computed
        once at startup and cached — see load_modules()."""
        available_module_names = loader.discover_modules()
        available_modules = []
        for module_name in available_module_names:
            try:
                module_class = loader.load_module(module_name)
                instance = module_class()
                display_name = instance.get_name()
                available_modules.append((module_name, display_name))
            except Exception:
                available_modules.append((module_name, module_name))
        return available_modules

    def _refresh_available_modules_cache(self) -> None:
        """Recompute _available_modules_cache from disk. Must be called after
        install_plugin()/uninstall_plugin() change what's on disk — otherwise
        a plugin installed/uninstalled mid-session stays invisible/stuck in
        the Settings dialog's module list until restart (the cache is
        otherwise only computed once, at startup, in load_modules())."""
        modules_dir = Path(__file__).parent / 'modules'
        loader = ModuleLoader(modules_dir, plugins_dir=self._get_plugins_dir())
        self._available_modules_cache = self._discover_available_modules(loader)

    def _on_tab_activated(self, index: int) -> None:
        """Build a lazily-registered tab's real widget the first time it's
        shown. No-ops for tabs that are already built (or aren't lazy tabs).

        The module is only popped from _pending_tab_modules *after*
        get_widget() succeeds — if construction fails, it stays pending so a
        later click on the tab retries construction instead of leaving the
        tab permanently stuck as a blank placeholder for the rest of the
        session."""
        module = self._pending_tab_modules.get(index)
        if module is None:
            return
        try:
            widget = module.get_widget()
        except Exception as e:
            self.log_message(f"ERROR: Failed to load module {module.__class__.__name__}: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Module Load Error",
                f"Failed to load the \"{module.get_name()}\" tab:\n\n{e}\n\n"
                "You can try selecting this tab again."
            )
            return

        module.mark_widget_built()
        del self._pending_tab_modules[index]

        self.tabs.blockSignals(True)
        try:
            self.tabs.removeTab(index)
            self.tabs.insertTab(index, widget, module.get_name())
            self.tabs.setCurrentIndex(index)
        finally:
            self.tabs.blockSignals(False)

        self.log_message(f"Loaded module: {module.get_name()}")
        self._populate_module_customer_lists(module)

    def _populate_module_customer_lists(self, module) -> None:
        """Call every populate_*_customer_list method a single module defines."""
        for method_name in dir(module):
            if method_name.startswith('populate_') and method_name.endswith('_customer_list'):
                method = getattr(module, method_name, None)
                if callable(method):
                    try:
                        method()
                    except Exception as e:
                        self.log_message(f"Error refreshing {module.get_name()} customer list: {e}")

    # ==================== Menu ====================

    def setup_menu(self):
        """Setup application menu"""
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)  # Force menu to appear in window (not system menu bar)

        # File menu
        file_menu = menubar.addMenu("&File")  # pyright: ignore[reportOptionalMemberAccess]

        settings_action = file_menu.addAction("&Settings")  # pyright: ignore[reportOptionalMemberAccess]
        settings_action.triggered.connect(self.open_settings)  # pyright: ignore[reportOptionalMemberAccess]

        install_plugin_action = file_menu.addAction("&Install Plugin...")  # pyright: ignore[reportOptionalMemberAccess]
        install_plugin_action.triggered.connect(self.install_plugin)  # pyright: ignore[reportOptionalMemberAccess]

        uninstall_plugin_action = file_menu.addAction(  # pyright: ignore[reportOptionalMemberAccess]
            "&Uninstall Plugin...")
        uninstall_plugin_action.triggered.connect(self.uninstall_plugin)  # pyright: ignore[reportOptionalMemberAccess]

        file_menu.addSeparator()  # pyright: ignore[reportOptionalMemberAccess]

        exit_action = file_menu.addAction("E&xit")  # pyright: ignore[reportOptionalMemberAccess]
        exit_action.triggered.connect(self.close)  # pyright: ignore[reportOptionalMemberAccess]

        # Help menu
        help_menu = menubar.addMenu("&Help")  # pyright: ignore[reportOptionalMemberAccess]

        setup_wizard_action = help_menu.addAction("&Run Setup Wizard...")  # pyright: ignore[reportOptionalMemberAccess]
        setup_wizard_action.triggered.connect(self.run_setup_wizard)  # pyright: ignore[reportOptionalMemberAccess]

        check_updates_action = help_menu.addAction("Check for &Updates")  # pyright: ignore[reportOptionalMemberAccess]
        check_updates_action.triggered.connect(self.check_for_updates)  # pyright: ignore[reportOptionalMemberAccess]

        enable_updates_action = help_menu.addAction(  # pyright: ignore[reportOptionalMemberAccess]
            "Re-enable Update &Notifications")
        enable_updates_action.triggered.connect(  # pyright: ignore[reportOptionalMemberAccess]
            self.reenable_update_notifications)

        help_menu.addSeparator()  # pyright: ignore[reportOptionalMemberAccess]

        about_action = help_menu.addAction("&About")  # pyright: ignore[reportOptionalMemberAccess]
        about_action.triggered.connect(self.show_about)  # pyright: ignore[reportOptionalMemberAccess]

    def open_settings(self):
        """Open settings dialog"""
        # Import here to avoid circular dependency
        from core.settings_dialog import SettingsDialog

        # Reuse the (module_name, display_name) list computed once in
        # load_modules() instead of re-discovering and re-instantiating every
        # module class from scratch on every single Settings-dialog open.
        dialog = SettingsDialog(
            self.settings, self, self._available_modules_cache,
            active_keys=set(self.DEFAULT_SETTINGS)
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings = dialog.settings

            # Reinitialize remote sync manager if path changed
            remote_path = self.settings.get('remote_server_path', '')
            self.remote_sync = RemoteSyncManager(remote_path)

            self.save_settings()
            self.populate_customer_lists()
            from shared.widgets import DropZone
            DropZone.set_skip_image_attachments(self.settings.get('skip_image_attachments', True))
            QMessageBox.information(self, "Settings", "Settings saved. Please restart for all changes to take effect.")

    def install_plugin(self):
        """Prompt for a GitHub repo and install it as a plugin."""
        repo_input, ok = QInputDialog.getText(
            self, "Install Plugin",
            "GitHub repo (owner/repo or https://github.com/owner/repo):",
            QLineEdit.EchoMode.Normal
        )
        if not ok or not repo_input.strip():
            return

        repo_input = repo_input.strip().rstrip('/')
        if repo_input.startswith('https://github.com/'):
            repo_slug = repo_input[len('https://github.com/'):]
        elif repo_input.startswith('github.com/'):
            repo_slug = repo_input[len('github.com/'):]
        else:
            repo_slug = repo_input

        parts = repo_slug.split('/')
        if len(parts) < 2:
            QMessageBox.warning(self, "Install Plugin", f"Could not parse repo from: {repo_input}")
            return

        owner, repo = parts[0], parts[1]
        plugins_dir = self._get_plugins_dir()

        progress = QProgressDialog("Connecting...", None, 0, 0, self)
        progress.setWindowTitle("Installing Plugin")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(420)
        progress.setCancelButton(None)
        progress.setValue(0)
        self._install_progress = progress

        worker = _PluginInstallWorker(owner, repo, plugins_dir)
        worker.status.connect(progress.setLabelText)
        worker.success.connect(lambda name, dest, warn: self._on_plugin_install_success(name, dest, warn, worker))
        worker.error.connect(lambda msg: self._on_plugin_install_error(msg, worker))
        self._install_worker = worker  # prevent GC while running
        worker.start()

    def _on_plugin_install_success(self, module_name: str, dest: str, dep_warning: str, worker: _PluginInstallWorker):
        self._install_progress.close()
        self._refresh_available_modules_cache()
        if dep_warning:
            msg = (f"Plugin '{module_name}' files copied to:\n{dest}\n\n"
                   f"The plugin may not load until dependencies are resolved.")
            QMessageBox.warning(self, "Plugin Installed", msg + dep_warning)
        else:
            msg = f"Plugin '{module_name}' installed to:\n{dest}\n\nRestart JobDocs to load it."
            QMessageBox.information(self, "Plugin Installed", msg)
        worker.deleteLater()

    def _on_plugin_install_error(self, message: str, worker: _PluginInstallWorker):
        self._install_progress.close()
        QMessageBox.critical(self, "Install Plugin", message)
        worker.deleteLater()

    def uninstall_plugin(self):
        """List installed plugins and remove the one the user selects."""
        plugins_dir = self._get_plugins_dir()
        if not plugins_dir or not plugins_dir.exists():
            QMessageBox.information(self, "Uninstall Plugin", "No plugins directory found.")
            return

        try:
            entries = list(plugins_dir.iterdir())
        except OSError as e:
            QMessageBox.critical(self, "Uninstall Plugin", f"Could not scan plugins directory:\n{e}")
            return

        installed_raw = []
        for d in entries:
            try:
                if d.is_dir() and (d / "module.py").exists():
                    installed_raw.append(d)
            except OSError:
                pass
        installed = sorted(installed_raw, key=lambda p: p.name.lower())
        if not installed:
            QMessageBox.information(self, "Uninstall Plugin", "No installed plugins found.")
            return

        names = [d.name for d in installed]
        choice, ok = QInputDialog.getItem(
            self, "Uninstall Plugin", "Select plugin to uninstall:", names, 0, False
        )
        if not ok or not choice:
            return

        confirm = QMessageBox.question(
            self, "Uninstall Plugin",
            f"Remove plugin '{choice}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        target = plugins_dir / choice
        try:
            shutil.rmtree(target)
        except (OSError, shutil.Error) as e:
            QMessageBox.critical(self, "Uninstall Plugin", f"Failed to remove plugin:\n{e}")
            return

        self._refresh_available_modules_cache()

        disabled = self.settings.get("disabled_modules", [])
        if choice in disabled:
            disabled.remove(choice)
            self.settings["disabled_modules"] = disabled
            self.save_settings()

        QMessageBox.information(
            self, "Uninstall Plugin",
            f"Plugin '{choice}' removed. Restart JobDocs to complete uninstall."
        )

    def show_getting_started(self):
        """Show interactive getting started tutorial."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel,
            QPushButton, QFrame, QSizePolicy,
        )
        from PyQt6.QtCore import Qt as _Qt

        folder_term = get_os_text('folder_term')

        steps = [
            (
                "Welcome to JobDocs",
                f"""<p>JobDocs manages blueprint files and customer job {folder_term}s — linking
drawings to jobs without duplicating files.</p>
<p>This tutorial walks through the four things you need to get started.
It takes about two minutes.</p>""",
                None, None,
            ),
            (
                "Step 1 — Configure your directories",
                f"""<p>Open <b>File → Settings</b> and set:</p>
<ul>
  <li><b>Blueprints Directory</b> — where your master drawing files live</li>
  <li><b>Customer Files Directory</b> — where job {folder_term}s are created</li>
</ul>
<p>Choose <b>Hard Link</b> as the link type (recommended). JobDocs will link
blueprint files into job {folder_term}s without copying them.</p>""",
                "Open Settings",
                lambda: (dlg.hide(), self.open_settings(), dlg.show()),
            ),
            (
                "Step 2 — Create your first job",
                f"""<p>Go to the <b>Job</b> tab and fill in the job details:</p>
<ul>
  <li>Customer name and job number</li>
  <li>Job description and drawing numbers</li>
</ul>
<p>Drag blueprint files onto the drop zone — or browse for them.
Click <b>Create Job</b> to build the {folder_term} structure and link the files.</p>""",
                "Go to Job tab",
                lambda: (dlg.accept(), QTimer.singleShot(0, lambda: self._tutorial_go_to_tab("Job"))),
            ),
            (
                "Step 3 — Drop emails with attachments",
                """<p>Any drop zone accepts email drag-and-drop:</p>
<ul>
  <li><b>Outlook / O365</b> — drag from the desktop app; attachments are extracted automatically</li>
  <li><b>Betterbird / Thunderbird</b> — drag from the message list; works the same way</li>
</ul>
<p>Image attachments are skipped by default. Zip files are unpacked automatically.
Both can be changed in <b>Settings</b>.</p>""",
                None, None,
            ),
            (
                "Step 4 — Search your jobs",
                """<p>The <b>Search</b> tab lets you find any job instantly by:</p>
<ul>
  <li>Customer name</li>
  <li>Job number</li>
  <li>Description or drawing number</li>
</ul>
<p>Results are indexed in the background after first launch, so searches are
near-instant even across thousands of jobs.</p>""",
                "Go to Search",
                lambda: (dlg.accept(), QTimer.singleShot(0, lambda: self._tutorial_go_to_tab("Search"))),
            ),
            (
                "You're all set",
                """<p>That covers the core workflow. A few more things worth knowing:</p>
<ul>
  <li><b>Bulk Create</b> tab — create many jobs at once from a CSV file</li>
  <li><b>Help → Run Setup Wizard</b> — re-run first-time configuration any time</li>
  <li><b>ITAR mode</b> — keep controlled documents in a separate directory</li>
</ul>
<p>If you get stuck, the setup wizard covers directory configuration step by step.</p>""",
                None, None,
            ),
        ]

        dlg = QDialog(self)
        dlg.setWindowTitle("Getting Started")
        dlg.setMinimumWidth(480)
        dlg.setMaximumWidth(560)

        outer = QVBoxLayout(dlg)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        # Header bar
        header = QFrame()
        header.setStyleSheet("background:#1565c0;")
        header.setFixedHeight(6)
        outer.addWidget(header)

        inner = QVBoxLayout()
        inner.setContentsMargins(24, 20, 24, 20)
        inner.setSpacing(12)
        outer.addLayout(inner)

        step_label = QLabel()
        step_label.setStyleSheet("color: gray; font-size: 11px;")

        title_label = QLabel()
        title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        title_label.setWordWrap(True)

        body_label = QLabel()
        body_label.setTextFormat(_Qt.TextFormat.RichText)
        body_label.setWordWrap(True)
        body_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

        action_btn = QPushButton()
        action_btn.setVisible(False)
        action_btn.setFixedHeight(32)
        action_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        action_btn.setStyleSheet(
            "QPushButton { background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9;"
            " border-radius: 4px; padding: 5px 14px; font-weight: bold; }"
            "QPushButton:hover { background: #bbdefb; }"
        )

        inner.addWidget(step_label)
        inner.addWidget(title_label)
        inner.addWidget(body_label)
        inner.addWidget(action_btn)
        inner.addStretch()

        # Nav row
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e0e0e0;")
        outer.addWidget(sep)

        nav = QHBoxLayout()
        nav.setContentsMargins(24, 12, 24, 16)
        back_btn = QPushButton("← Back")
        back_btn.setFlat(True)
        next_btn = QPushButton("Next →")
        next_btn.setStyleSheet(
            "QPushButton { background: #1565c0; color: white; border-radius: 4px;"
            " padding: 6px 18px; font-weight: bold; }"
            "QPushButton:hover { background: #1976d2; }"
        )
        nav.addWidget(back_btn)
        nav.addStretch()
        nav.addWidget(next_btn)
        outer.addLayout(nav)

        state = {'idx': 0}

        def _show(idx):
            state['idx'] = idx
            title, body, act_label, act_cb = steps[idx]
            total = len(steps)
            step_label.setText(f"Step {idx + 1} of {total}")
            title_label.setText(title)
            body_label.setText(body)
            back_btn.setVisible(idx > 0)
            next_btn.setText("Finish" if idx == total - 1 else "Next →")
            if act_label and act_cb:
                action_btn.setText(act_label)
                try:
                    action_btn.clicked.disconnect()
                except Exception:
                    pass
                action_btn.clicked.connect(act_cb)
                action_btn.setVisible(True)
            else:
                action_btn.setVisible(False)

        back_btn.clicked.connect(lambda: _show(state['idx'] - 1))
        next_btn.clicked.connect(lambda: dlg.accept() if state['idx'] == len(steps) - 1 else _show(state['idx'] + 1))

        _show(0)
        dlg.exec()

    def _tutorial_go_to_tab(self, name: str) -> None:
        """Switch to a named tab, used by the tutorial action buttons."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == name:
                self.tabs.setCurrentIndex(i)
                return

    def check_for_updates(self) -> None:
        """Manually check for updates from the Help menu."""
        existing = getattr(self, '_manual_checker', None)
        if existing is not None and existing.isRunning():
            return

        def _on_available(tag: str, url: str, asset_url: str) -> None:
            dlg = _UpdateDialog(tag, url, asset_url, self.app_context, self)
            self._manual_update_dialog = dlg  # type: ignore[attr-defined]
            dlg.finished.connect(lambda _: setattr(self, '_manual_update_dialog', None))
            dlg.show()

        def _on_up_to_date() -> None:
            QMessageBox.information(
                self, "Up to Date",
                f"You're running the latest version ({APP_VERSION}).",
            )

        checker = _UpdateChecker()
        checker.update_available.connect(_on_available)
        checker.up_to_date.connect(_on_up_to_date)
        checker.finished.connect(checker.deleteLater)
        self._manual_checker = checker  # type: ignore[attr-defined]
        checker.finished.connect(lambda: setattr(self, '_manual_checker', None))
        checker.start()

    def reenable_update_notifications(self) -> None:
        """Clear the update-notifications-disabled flag and confirm to the user."""
        self.app_context.set_setting('updates_notifications_disabled', False)
        self.app_context.save_settings()
        QMessageBox.information(
            self, "Update Notifications Enabled",
            "Update notifications have been re-enabled.\n"
            "You'll be notified on next launch if a new version is available.",
        )

    def show_about(self):
        """Show about dialog"""
        folder_term = get_os_text('folder_term')

        content = f"""
<h2>JobDocs</h2>
<p style="color: gray; margin-top: 0;">{APP_VERSION}</p>
<p>A modular tool for managing blueprint files and customer job {folder_term}s.</p>

<p><b>Features:</b></p>
<ul>
<li>Plugin-based modular architecture</li>
<li>Quote and job management</li>
<li>Blueprint file organization</li>
<li>ITAR support for controlled documents</li>
<li>Bulk job creation</li>
<li>Advanced search capabilities</li>
</ul>

<p>Built with PyQt6 and the JobDocs Plugin System</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("About JobDocs")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(content)
        msg.exec()

    def run_setup_wizard(self):
        """Launch the first-time setup wizard manually from Help menu"""
        try:
            from modules.admin.oobe_wizard import OOBEWizard
        except ImportError:
            QMessageBox.warning(self, "Setup Wizard", "Setup wizard is not available.")
            return
        wizard = OOBEWizard(self.app_context, self)
        if wizard.exec():
            # Wizard already updated app_context.settings and saved — sync main window
            self.settings = self.app_context.settings
            self.apply_ui_style()
            from shared.widgets import DropZone
            DropZone.set_skip_image_attachments(self.settings.get('skip_image_attachments', True))

    # ==================== CLI Prefill ====================

    def _apply_prefill(self, data: Dict[str, str]) -> None:
        """Prefill module form fields from CLI args and switch to the relevant tab.

        Iterates loaded modules and calls prefill_fields(data) on each. Then
        switches the active tab to Job (if j_no is present) or Quote (if q_no
        is present). Called once from __init__ when prefill data is supplied.
        """
        # prefill_fields() no-ops on any module whose widget isn't built yet
        # (its field attributes are still None). A CLI-launched prefill means
        # the user is about to interact with the app right away, so building
        # every tab now is an acceptable, one-time trade against the lazy
        # -tab-construction optimization above.
        for index in list(self._pending_tab_modules.keys()):
            self._on_tab_activated(index)

        for module in self.modules:
            module.prefill_fields(data)

        if 'j_no' in data:
            target_tab = 'Job'
        elif 'q_no' in data:
            target_tab = 'Quote'
        else:
            return

        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == target_tab:
                self.tabs.setCurrentIndex(i)
                break

    # ==================== UI Helpers ====================

    def apply_ui_style(self):
        """Apply UI style from settings"""
        style = self.settings.get('ui_style', 'Fusion')
        QApplication.setStyle(style)

    def log_message(self, message: str):
        """Log a message to console and status bar"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.statusBar().showMessage(message, 3000)  # pyright: ignore[reportOptionalMemberAccess]

    def show_error_dialog(self, title: str, message: str):
        """Show error dialog"""
        QMessageBox.critical(self, title, message)

    def show_info_dialog(self, title: str, message: str):
        """Show information dialog"""
        QMessageBox.information(self, title, message)

    # ==================== Data Helpers ====================

    def get_customer_list(self) -> List[str]:
        """Get list of customers from customer files directory"""
        customers = set()
        for dir_key in ['customer_files_dir', 'itar_customer_files_dir']:
            dir_path = self.settings.get(dir_key, '')
            if dir_path and Path(dir_path).exists():
                try:
                    for d in Path(dir_path).iterdir():
                        if d.is_dir():
                            customers.add(d.name)
                except OSError:
                    pass
        return sorted(customers)

    def add_to_history(self, entry_type: str, data: Dict[str, Any]):
        """Add an entry to history.

        Generic across entry types: recorded under history['recent_{entry_type}s']
        (e.g. 'job' -> 'recent_jobs', 'quote' -> 'recent_quotes'), matching what
        modules/_template/module.py's plugin-authoring example documents. Capped
        at the last 100 entries per type, with a timestamp and customer-history
        update.
        """
        history_key = f'recent_{entry_type}s'
        recent_entries = self.history.get(history_key, [])

        # Add timestamp
        data['date'] = datetime.now().isoformat()

        # Add to front of list
        recent_entries.insert(0, data)

        # Keep only last 100 entries
        self.history[history_key] = recent_entries[:100]

        # Update customer history
        customer = data.get('customer', '')
        if customer:
            if 'customers' not in self.history:
                self.history['customers'] = {}
            self.history['customers'][customer] = datetime.now().isoformat()

        self.save_history()

    def populate_customer_lists(self):
        """Refresh customer lists in all *already-built* modules (called after
        settings change). A module whose tab hasn't been activated yet has no
        widget to populate — it'll load fresh data (reflecting current
        settings) the first time it's actually shown, via _on_tab_activated."""
        for module in self.modules:
            if not module.is_widget_built():
                continue
            self._populate_module_customer_lists(module)

        self.log_message("Customer lists refreshed")

    def refresh_history(self):
        """Refresh history displays in all modules"""
        # Hook for modules to refresh history displays
        self.log_message("History refreshed")

    # ==================== Application Cleanup ====================

    def closeEvent(self, event):  # pyright: ignore[reportIncompatibleMethodOverride]
        """Handle window close event - ensure proper cleanup"""
        self.log_message("Application closing - cleaning up resources...")

        # Cleanup all modules
        for module in self.modules:
            try:
                module.cleanup()
            except Exception as e:
                print(f"Error cleaning up module {module.get_name()}: {e}")

        # Save any pending settings/history. On a read-only (search-only)
        # install these are no-ops (see save_settings()/save_history() above).
        try:
            self.save_settings()
            self.save_history()
        except Exception as e:
            print(f"Error saving on exit: {e}")

        # Accept the close event
        event.accept()

        # Ensure application quits
        QApplication.quit()


def main():
    """Main application entry point"""
    # Set AppUserModelID so Windows can pin this to the taskbar
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('JobDocs.DEV')
    except Exception:
        pass

    prefill, qt_argv = _parse_prefill_args(sys.argv[1:])
    app = QApplication([sys.argv[0]] + qt_argv)
    app.setApplicationName("JobDocs")
    app.setOrganizationName("JobDocs")

    # Ensure clean shutdown
    app.setQuitOnLastWindowClosed(True)

    print("=" * 60)
    print("JobDocs - Modular Plugin System")
    print("=" * 60)
    print()

    window = JobDocsMainWindow(prefill=prefill if prefill else None)
    window.show()

    def _on_update_available(tag: str, url: str, asset_url: str) -> None:
        if window.app_context.get_setting('updates_notifications_disabled', False):
            return
        if window.app_context.get_setting('updates_skipped_version', '') == tag:
            return
        dlg = _UpdateDialog(tag, url, asset_url, window.app_context, window)
        window._update_dialog = dlg  # type: ignore[attr-defined]
        dlg.finished.connect(lambda _: setattr(window, '_update_dialog', None))
        dlg.show()

    _checker = _UpdateChecker()
    _checker.update_available.connect(_on_update_available)
    _checker.finished.connect(_checker.deleteLater)
    _checker.finished.connect(lambda: setattr(window, '_update_checker', None))
    window._update_checker = _checker  # type: ignore[attr-defined]
    _checker.start()

    # Run the application
    exit_code = app.exec()

    # Join the startup update checker if it's still running
    checker = getattr(window, '_update_checker', None)
    if checker is not None and checker.isRunning():
        checker.requestInterruption()
        checker.wait(2000)

    # Ensure window is properly deleted
    window.deleteLater()

    # Process any remaining events
    app.processEvents()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())

