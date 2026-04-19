#!/usr/bin/env python3
"""
JobDocs - Modular Blueprint and Job Management System

Main application entry point using the modular plugin architecture.
"""

import io
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
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QMessageBox, QDialog,
    QInputDialog, QLineEdit, QProgressDialog
)

from core.module_loader import ModuleLoader
from core.app_context import AppContext
from shared.utils import get_config_dir, get_os_text
from shared.remote_sync import RemoteSyncManager


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
        """Install plugin requirements into the embedded Python's site-packages.

        Uses sys.executable (the embedded runtime\\python.exe in a release build,
        or the dev Python when running from source). Returns a non-empty warning
        string on failure, or '' on success / no requirements.txt present.
        """
        req_file = plugin_dir / 'requirements.txt'
        if not req_file.exists():
            return ''

        # On Flatpak, /app is read-only at runtime; pip installs will always fail.
        # Manual install via sys.executable is also unsupported (same read-only runtime).
        if os.getenv('FLATPAK_ID'):
            return (
                "\n\nDependency installation is not supported inside a Flatpak build.\n"
                "Install the plugin's dependencies on the host system before use."
            )

        try:
            self.status.emit("Installing dependencies...")
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            proc = subprocess.Popen(
                [sys.executable, '-m', 'pip', 'install',
                 '--no-warn-script-location', '-r', str(req_file)],
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
                    f"Run manually: \"{sys.executable}\" -m pip install -r \"{req_file}\"\n\nError: {err}")
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

    def __init__(self):
        super().__init__()

        # Configuration
        self.config_dir = get_config_dir()
        self.settings_file = self.config_dir / 'settings.json'
        self.history_file = self.config_dir / 'history.json'

        # Load settings first (needed for remote sync setup)
        self.settings = self.load_settings()

        # Initialize remote sync manager
        remote_path = self.settings.get('remote_server_path', '')
        self.remote_sync = RemoteSyncManager(remote_path)

        self.history = self.load_history()
        self.modules = []  # Store loaded modules

        # Setup UI
        self.setWindowTitle("JobDocs")
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
            main_window=self
        )

        # Load modules
        self.load_modules()

        # Setup menu
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

        self.statusBar().showMessage("Ready")  # pyright: ignore[reportOptionalMemberAccess]

    # ==================== Settings & History ====================

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
                # Save to local to keep in sync
                try:
                    with open(self.settings_file, 'w') as f:
                        json.dump(merged, f, indent=2)
                except IOError:
                    pass
                return merged

        # Fall back to local settings
        if local_settings:
            merged = self.DEFAULT_SETTINGS.copy()
            merged.update(local_settings)
            return merged

        return self.DEFAULT_SETTINGS.copy()

    def _partial_save_settings(self, partial: Dict[str, Any]):
        """Merge partial settings dict and persist to disk (used by mid-dialog callbacks)."""
        self.settings.update(partial)
        self.save_settings()

    def save_settings(self):
        """Save settings to file and sync to remote server if configured"""
        try:
            # Save locally first
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)

            # Sync to remote if configured
            if self.remote_sync.is_enabled():
                self.remote_sync.save_json_to_remote('settings.json', self.settings)

        except IOError as e:
            self.show_error_dialog("Error", f"Failed to save settings: {e}")

    def load_history(self) -> Dict[str, Any]:
        """Load history from file, trying remote server first if configured"""
        # Try loading from remote first (remote is source of truth)
        if self.remote_sync.is_enabled():
            remote_history = self.remote_sync.load_json_from_remote('history.json')
            if remote_history:
                # Save to local to keep in sync
                try:
                    with open(self.history_file, 'w') as f:
                        json.dump(remote_history, f, indent=2)
                except IOError:
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
        try:
            # Save locally first
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)

            # Sync to remote if configured
            if self.remote_sync.is_enabled():
                self.remote_sync.save_json_to_remote('history.json', self.history)

        except IOError as e:
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
                break

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
            disabled_modules = self.settings.get('disabled_modules', [])
            self.modules = loader.load_all_modules(self.app_context, experimental_enabled, disabled_modules)

            if not self.modules:
                QMessageBox.warning(
                    self,
                    "No Modules",
                    "No modules were loaded. Check the modules/ directory."
                )
                return

            # Add each module as a tab (skip non-tab modules)
            for module in self.modules:
                if not module.is_tab_module():
                    continue
                try:
                    widget = module.get_widget()
                    name = module.get_name()
                    self.tabs.addTab(widget, name)
                    self.log_message(f"Loaded module: {name}")
                except Exception as e:
                    self.log_message(f"ERROR: Failed to load module {module.__class__.__name__}: {e}")
                    import traceback
                    traceback.print_exc()

            self.statusBar().showMessage(  # pyright: ignore[reportOptionalMemberAccess]
                f"Loaded {len(self.modules)} module(s)"
            )

            # Populate customer lists in all modules
            self.populate_customer_lists()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Module Load Error",
                f"Failed to load modules:\n\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

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

        file_menu.addSeparator()  # pyright: ignore[reportOptionalMemberAccess]

        exit_action = file_menu.addAction("E&xit")  # pyright: ignore[reportOptionalMemberAccess]
        exit_action.triggered.connect(self.close)  # pyright: ignore[reportOptionalMemberAccess]

        # Help menu
        help_menu = menubar.addMenu("&Help")  # pyright: ignore[reportOptionalMemberAccess]

        getting_started_action = help_menu.addAction("&Getting Started")  # pyright: ignore[reportOptionalMemberAccess]
        getting_started_action.triggered.connect(  # pyright: ignore[reportOptionalMemberAccess]
            self.show_getting_started
        )

        readme_action = help_menu.addAction("&User Guide (README)")  # pyright: ignore[reportOptionalMemberAccess]
        readme_action.triggered.connect(self.show_readme)  # pyright: ignore[reportOptionalMemberAccess]

        setup_wizard_action = help_menu.addAction("&Run Setup Wizard...")  # pyright: ignore[reportOptionalMemberAccess]
        setup_wizard_action.triggered.connect(self.run_setup_wizard)  # pyright: ignore[reportOptionalMemberAccess]

        help_menu.addSeparator()  # pyright: ignore[reportOptionalMemberAccess]

        about_action = help_menu.addAction("&About")  # pyright: ignore[reportOptionalMemberAccess]
        about_action.triggered.connect(self.show_about)  # pyright: ignore[reportOptionalMemberAccess]

    def open_settings(self):
        """Open settings dialog"""
        # Import here to avoid circular dependency
        from core.settings_dialog import SettingsDialog

        # Discover all available modules for the settings dialog
        modules_dir = Path(__file__).parent / 'modules'
        loader = ModuleLoader(modules_dir, plugins_dir=self._get_plugins_dir())
        available_module_names = loader.discover_modules()

        # Create list of (module_name, display_name) tuples
        available_modules = []
        for module_name in available_module_names:
            try:
                # Try to load the module class to get its display name
                module_class = loader.load_module(module_name)
                instance = module_class()
                display_name = instance.get_name()
                available_modules.append((module_name, display_name))
            except Exception:
                # If we can't load it, just use the module name
                available_modules.append((module_name, module_name))

        dialog = SettingsDialog(
            self.settings, self, available_modules,
            save_callback=self._partial_save_settings,
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

    def show_getting_started(self):
        """Show getting started guide"""
        folder_term = get_os_text('folder_term')

        content = f"""
<h2>GETTING STARTED</h2>

<p><b>1. Go to File → Settings</b><br>
<b>2. Configure directories:</b><br>
&nbsp;&nbsp;- Blueprints Directory: Central drawing storage<br>
&nbsp;&nbsp;- Customer Files Directory: Where job {folder_term}s are created<br>
<b>3. Choose link type (Hard Link recommended)</b><br>
<b>4. Set blueprint file extensions</b></p>

<p><b>CREATE JOB TAB</b><br>
Enter job information and drop files to create job {folder_term}s.</p>

<p><b>BULK CREATE TAB</b><br>
Create multiple jobs at once using CSV format.</p>

<p><b>SEARCH TAB</b><br>
Search across all customers and jobs.</p>
        """

        msg = QMessageBox(self)
        msg.setWindowTitle("Getting Started")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(content)
        msg.exec()

    def show_about(self):
        """Show about dialog"""
        folder_term = get_os_text('folder_term')

        content = f"""
<h2>JobDocs</h2>
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

    def show_readme(self):
        """Show README.md in a scrollable dialog"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox

        readme_path = Path(__file__).parent / 'README.md'
        try:
            content = readme_path.read_text(encoding='utf-8')
        except Exception as e:
            QMessageBox.warning(self, "User Guide", f"README.md could not be opened:\n{e}")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("JobDocs — User Guide")
        dialog.resize(820, 640)

        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(content)
        text.setFontFamily("Courier New")
        text.setFontPointSize(9)
        layout.addWidget(text)

        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn.rejected.connect(dialog.close)
        layout.addWidget(btn)

        dialog.exec()

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
        """Add an entry to history"""
        if entry_type == 'job':
            recent_jobs = self.history.get('recent_jobs', [])

            # Add timestamp
            data['date'] = datetime.now().isoformat()

            # Add to front of list
            recent_jobs.insert(0, data)

            # Keep only last 100 entries
            self.history['recent_jobs'] = recent_jobs[:100]

            # Update customer history
            customer = data.get('customer', '')
            if customer:
                if 'customers' not in self.history:
                    self.history['customers'] = {}
                self.history['customers'][customer] = datetime.now().isoformat()

            self.save_history()

    def populate_customer_lists(self):
        """Refresh customer lists in all modules (called after settings change)"""
        # Call populate methods on all loaded modules that have them
        for module in self.modules:
            # Check for populate_*_customer_list methods
            for method_name in dir(module):
                if method_name.startswith('populate_') and method_name.endswith('_customer_list'):
                    method = getattr(module, method_name, None)
                    if callable(method):
                        try:
                            method()
                        except Exception as e:
                            self.log_message(f"Error refreshing {module.get_name()} customer list: {e}")

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

        # Save any pending settings/history
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

    app = QApplication(sys.argv)
    app.setApplicationName("JobDocs")
    app.setOrganizationName("JobDocs")

    # Ensure clean shutdown
    app.setQuitOnLastWindowClosed(True)

    print("=" * 60)
    print("JobDocs - Modular Plugin System")
    print("=" * 60)
    print()

    window = JobDocsMainWindow()
    window.show()

    # Run the application
    exit_code = app.exec()

    # Ensure window is properly deleted
    window.deleteLater()

    # Process any remaining events
    app.processEvents()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())

