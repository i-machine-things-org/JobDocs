"""
JobDocs DEV Launcher
Compiled to JobDocsDEV.exe - launches main.py with a debug console window
that stays in the taskbar (pinnable).
"""
import subprocess
import sys
import os
import ctypes
import threading
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime


APP_ID = 'JobDocs.DEV'


def find_python():
    """Find python executable on this system."""
    candidates = []
    # Prefer python.exe over pythonw.exe so we can capture stdout
    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    for d in path_dirs:
        for name in ('python.exe', 'pythonw.exe'):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                candidates.append(p)

    local = os.environ.get('LOCALAPPDATA', '')
    if local:
        for base in [
            os.path.join(local, 'Programs', 'Python'),
            os.path.join(local, 'Python'),
        ]:
            if os.path.isdir(base):
                for entry in sorted(os.listdir(base), reverse=True):
                    for name in ('python.exe', 'pythonw.exe'):
                        p = os.path.join(base, entry, name)
                        if os.path.isfile(p):
                            candidates.append(p)
    return candidates[0] if candidates else None


class LauncherWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JobDocs DEV")
        self.root.geometry("700x400")
        self.root.minsize(400, 200)

        # Set icon
        self._set_icon()

        # Log area
        self.log_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=("Consolas", 9),
            bg="#1e1e1e", fg="#cccccc", insertbackground="#cccccc"
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.log_area.config(state=tk.DISABLED)

        # Bottom bar
        bottom = tk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=4, pady=(0, 4))

        self.status_label = tk.Label(bottom, text="Starting...", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.hide_btn = tk.Button(bottom, text="Hide", command=self._hide)
        self.hide_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.process = None
        self.app_running = False

    def _set_icon(self):
        """Set window icon from ico file."""
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        ico_path = os.path.join(app_dir, 'windows', 'icon.ico')
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

    def log(self, msg):
        """Add a message to the log area (thread-safe)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"

        def _append():
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, line)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)

        self.root.after(0, _append)

    def _hide(self):
        """Minimize to taskbar."""
        self.root.iconify()

    def _on_close(self):
        """Handle window close - ask to kill app or just hide."""
        if self.app_running:
            self.root.iconify()
        else:
            self.root.destroy()

    def start_app(self):
        """Find python and launch main.py in a background thread."""
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))

        main_py = os.path.join(app_dir, 'main.py')

        self.log(f"App dir: {app_dir}")
        self.log(f"main.py exists: {os.path.exists(main_py)}")

        if not os.path.exists(main_py):
            self.log("ERROR: main.py not found!")
            self.status_label.config(text="Error: main.py not found")
            return

        # Find python
        if getattr(sys, 'frozen', False):
            python_exe = find_python()
        else:
            python_exe = sys.executable

        self.log(f"Python: {python_exe}")

        if not python_exe:
            self.log("ERROR: Could not find Python!")
            self.status_label.config(text="Error: Python not found")
            return

        # Launch in background thread
        thread = threading.Thread(
            target=self._run_app, args=(python_exe, main_py, app_dir),
            daemon=True
        )
        thread.start()

    def _run_app(self, python_exe, main_py, app_dir):
        """Run the app and pipe output to the log window."""
        try:
            self.log(f"Launching: {python_exe} {main_py}")
            self.app_running = True
            self.root.after(0, lambda: self.status_label.config(text="JobDocs is running"))
            self.root.after(0, lambda: self.root.iconify())  # Auto-minimize

            self.process = subprocess.Popen(
                [python_exe, main_py],
                cwd=app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Read output line by line
            for line in self.process.stdout:
                self.log(line.rstrip())

            exit_code = self.process.wait()
            self.log(f"JobDocs exited with code {exit_code}")
            self.app_running = False
            self.root.after(0, lambda: self.status_label.config(
                text=f"JobDocs exited (code {exit_code})"
            ))

            # Close launcher after app exits
            self.root.after(1000, self.root.destroy)

        except Exception as e:
            self.log(f"ERROR: {e}")
            self.app_running = False
            self.root.after(0, lambda: self.status_label.config(text=f"Error: {e}"))

    def run(self):
        # Start the app after the window is shown
        self.root.after(100, self.start_app)
        self.root.mainloop()


def main():
    # Set AppUserModelID for taskbar pinning
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    app = LauncherWindow()
    app.run()


if __name__ == '__main__':
    main()
