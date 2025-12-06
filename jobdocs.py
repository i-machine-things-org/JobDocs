"""
JobDocs - A tool for managing blueprint links and customer files
"""

import os
import sys
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Callable
import re
import csv
from io import StringIO

# Try to import tkinterdnd2 for drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("Note: tkinterdnd2 not installed. Drag and drop will use fallback mode.")
    print("Install with: pip install tkinterdnd2")


class AutocompletePopup:
    """Manages autocomplete popup windows with proper cleanup"""
    
    def __init__(self, parent: tk.Widget, entry: ttk.Entry, 
                 on_select: Callable[[str], None]):
        self.parent = parent
        self.entry = entry
        self.on_select = on_select
        self.popup: Optional[tk.Toplevel] = None
        self.listbox: Optional[tk.Listbox] = None
        
    def show(self, suggestions: List[str]) -> None:
        """Show popup with suggestions"""
        self.hide()
        
        if not suggestions:
            return
            
        try:
            if not self.entry.winfo_exists():
                return
                
            self.popup = tk.Toplevel(self.parent)
            self.popup.wm_overrideredirect(True)
            self.popup.wm_attributes('-topmost', True)
            
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            self.popup.geometry(f"+{x}+{y}")
            
            self.listbox = tk.Listbox(
                self.popup, 
                height=min(len(suggestions), 5),
                width=max(len(s) for s in suggestions) + 2
            )
            self.listbox.pack()
            
            for suggestion in suggestions:
                self.listbox.insert(tk.END, suggestion)
            
            self.listbox.bind('<<ListboxSelect>>', self._on_listbox_select)
            self.listbox.bind('<Return>', self._on_listbox_select)
            self.listbox.bind('<Escape>', lambda e: self.hide())
            
            self.entry.bind('<Down>', lambda e: self._focus_listbox())
            self.entry.bind('<Escape>', lambda e: self.hide())
            
        except tk.TclError:
            self.hide()
    
    def _focus_listbox(self) -> None:
        if self.listbox and self.popup:
            try:
                self.listbox.focus_set()
                if self.listbox.size() > 0:
                    self.listbox.selection_set(0)
            except tk.TclError:
                self.hide()
    
    def _on_listbox_select(self, event: tk.Event) -> None:
        if self.listbox:
            try:
                selection = self.listbox.curselection()
                if selection:
                    selected = self.listbox.get(selection[0])
                    self.on_select(selected)
                    self.hide()
            except tk.TclError:
                self.hide()
    
    def hide(self) -> None:
        if self.popup:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
            finally:
                self.popup = None
                self.listbox = None


class FileDropZone(tk.Frame):
    """A frame that accepts file drops"""
    
    def __init__(self, parent: tk.Widget, callback: Callable[[List[str]], None], 
                 file_label: str = "files", **kwargs):
        super().__init__(parent, **kwargs)
        self.callback = callback
        self.configure(relief=tk.SUNKEN, borderwidth=2, bg='#f0f0f0')
        
        self.label = tk.Label(
            self, 
            text=f"Drop {file_label} here\nor click to browse",
            bg='#f0f0f0', 
            fg='#666666', 
            font=('Arial', 10)
        )
        self.label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        self.label.bind('<Button-1>', self.browse_files)
        self.bind('<Button-1>', self.browse_files)
        
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_drop)
            self.label.drop_target_register(DND_FILES)
            self.label.dnd_bind('<<Drop>>', self.on_drop)
    
    def on_drop(self, event) -> None:
        if HAS_DND:
            files = self.tk.splitlist(event.data)
            self.callback(list(files))
        
    def browse_files(self, event=None) -> None:
        files = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[("All files", "*.*"), ("PDF files", "*.pdf")]
        )
        if files:
            self.callback(list(files))


class SettingsDialog(tk.Toplevel):
    """Dialog for managing application settings"""
    
    def __init__(self, parent: tk.Widget, settings: Dict[str, Any]):
        super().__init__(parent)
        self.title("Settings")
        self.settings = settings.copy()
        self.result: Optional[Dict[str, Any]] = None
        
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        self.center_window()
        
    def create_widgets(self) -> None:
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        row = 0
        
        # Blueprints directory
        ttk.Label(main_frame, text="Blueprints Directory:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.blueprints_var = tk.StringVar(value=self.settings.get('blueprints_dir', ''))
        ttk.Entry(main_frame, textvariable=self.blueprints_var, width=50).grid(
            row=row, column=1, padx=5
        )
        ttk.Button(main_frame, text="Browse", 
                  command=lambda: self._browse_dir(self.blueprints_var, "Blueprints")).grid(
            row=row, column=2
        )
        row += 1
        
        # Customer files directory
        ttk.Label(main_frame, text="Customer Files Directory:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.customer_files_var = tk.StringVar(
            value=self.settings.get('customer_files_dir', '')
        )
        ttk.Entry(main_frame, textvariable=self.customer_files_var, width=50).grid(
            row=row, column=1, padx=5
        )
        ttk.Button(main_frame, text="Browse", 
                  command=lambda: self._browse_dir(self.customer_files_var, "Customer Files")).grid(
            row=row, column=2
        )
        row += 1
        
        # ITAR section
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15
        )
        row += 1
        
        ttk.Label(main_frame, text="ITAR Directories (optional):", 
                 font=('Arial', 10, 'bold')).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2)
        )
        row += 1
        
        ttk.Label(main_frame, text="Separate directories for ITAR-controlled jobs", 
                 font=('Arial', 8), foreground='gray').grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 5)
        )
        row += 1
        
        # ITAR Blueprints
        ttk.Label(main_frame, text="ITAR Blueprints Directory:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.itar_blueprints_var = tk.StringVar(
            value=self.settings.get('itar_blueprints_dir', '')
        )
        ttk.Entry(main_frame, textvariable=self.itar_blueprints_var, width=50).grid(
            row=row, column=1, padx=5
        )
        ttk.Button(main_frame, text="Browse", 
                  command=lambda: self._browse_dir(self.itar_blueprints_var, "ITAR Blueprints")).grid(
            row=row, column=2
        )
        row += 1
        
        # ITAR Customer files
        ttk.Label(main_frame, text="ITAR Customer Files Directory:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.itar_customer_files_var = tk.StringVar(
            value=self.settings.get('itar_customer_files_dir', '')
        )
        ttk.Entry(main_frame, textvariable=self.itar_customer_files_var, width=50).grid(
            row=row, column=1, padx=5
        )
        ttk.Button(main_frame, text="Browse", 
                  command=lambda: self._browse_dir(self.itar_customer_files_var, "ITAR Customer Files")).grid(
            row=row, column=2
        )
        row += 1
        
        # Link type
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15
        )
        row += 1
        
        ttk.Label(main_frame, text="Link Type:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        self.link_type_var = tk.StringVar(value=self.settings.get('link_type', 'hard'))
        link_frame = ttk.Frame(main_frame)
        link_frame.grid(row=row, column=1, sticky=tk.W)
        ttk.Radiobutton(link_frame, text="Hard Link", variable=self.link_type_var, 
                       value='hard').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(link_frame, text="Symbolic Link", variable=self.link_type_var, 
                       value='symbolic').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(link_frame, text="Copy", variable=self.link_type_var, 
                       value='copy').pack(side=tk.LEFT, padx=5)
        row += 1
        
        # Blueprint extensions
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15
        )
        row += 1
        
        ttk.Label(main_frame, text="Blueprint File Types:", 
                 font=('Arial', 10, 'bold')).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2)
        )
        row += 1
        
        ttk.Label(main_frame, 
                 text="Files with these extensions go to blueprints folder", 
                 font=('Arial', 8), foreground='gray').grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 5)
        )
        row += 1
        
        ttk.Label(main_frame, text="File Extensions:").grid(
            row=row, column=0, sticky=tk.W, pady=5
        )
        
        current_extensions = self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
        self.extensions_var = tk.StringVar(value=', '.join(current_extensions))
        ttk.Entry(main_frame, textvariable=self.extensions_var, width=50).grid(
            row=row, column=1, padx=5
        )
        ttk.Label(main_frame, text="(comma-separated)", 
                 font=('Arial', 8), foreground='gray').grid(
            row=row, column=2, sticky=tk.W
        )
        row += 1
        
        # Duplicate jobs
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15
        )
        row += 1
        
        ttk.Label(main_frame, text="Job Number Validation:", 
                 font=('Arial', 10, 'bold')).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(5, 2)
        )
        row += 1
        
        self.allow_duplicates_var = tk.BooleanVar(
            value=self.settings.get('allow_duplicate_jobs', False)
        )
        ttk.Checkbutton(main_frame, text="Allow duplicate job numbers (not recommended)", 
                       variable=self.allow_duplicates_var).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=5
        )
        row += 1
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=20)
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
    
    def _browse_dir(self, var: tk.StringVar, title: str) -> None:
        dir_path = filedialog.askdirectory(title=f"Select {title} Directory")
        if dir_path:
            var.set(dir_path)
        
    def save(self) -> None:
        self.settings['blueprints_dir'] = self.blueprints_var.get()
        self.settings['customer_files_dir'] = self.customer_files_var.get()
        self.settings['itar_blueprints_dir'] = self.itar_blueprints_var.get()
        self.settings['itar_customer_files_dir'] = self.itar_customer_files_var.get()
        self.settings['link_type'] = self.link_type_var.get()
        
        extensions_str = self.extensions_var.get().strip()
        extensions = [ext.strip() for ext in extensions_str.split(',') if ext.strip()]
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        extensions = [ext.lower() for ext in extensions]
        self.settings['blueprint_extensions'] = extensions
        
        self.settings['allow_duplicate_jobs'] = self.allow_duplicates_var.get()
        
        self.result = self.settings
        self.destroy()
        
    def cancel(self) -> None:
        self.result = None
        self.destroy()
        
    def center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')


class FileLinkManager:
    """Main application for managing file links"""
    
    DEFAULT_SETTINGS = {
        'blueprints_dir': '',
        'customer_files_dir': '',
        'itar_blueprints_dir': '',
        'itar_customer_files_dir': '',
        'link_type': 'hard',
        'blueprint_extensions': ['.pdf', '.dwg', '.dxf'],
        'allow_duplicate_jobs': False
    }
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("JobDocs")
        self.root.geometry("950x800")
        
        self.config_dir = Path.home() / '.jobdocs'
        self.config_dir.mkdir(exist_ok=True)
        self.settings_file = self.config_dir / 'settings.json'
        self.history_file = self.config_dir / 'history.json'
        
        self.settings = self.load_settings()
        self.history = self.load_history()
        
        # Variables
        self.customer_var = tk.StringVar()
        self.job_number_var = tk.StringVar()
        self.description_var = tk.StringVar()
        self.drawing_numbers_var = tk.StringVar()
        self.itar_var = tk.BooleanVar(value=False)
        
        self.job_files: List[str] = []
        self.import_files: List[str] = []
        self.search_results: List[Dict[str, Any]] = []
        
        self.description_popup: Optional[AutocompletePopup] = None
        self.drawing_popup: Optional[AutocompletePopup] = None
        
        self.create_widgets()
        self.populate_customer_list()
        self._setup_traces()
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_traces(self) -> None:
        self.customer_var.trace_add('write', self._on_customer_change)
        self.job_number_var.trace_add('write', self._on_job_number_change)
        self.description_var.trace_add('write', self._on_description_change)
        self.drawing_numbers_var.trace_add('write', self._on_drawing_numbers_change)
    
    def _on_close(self) -> None:
        if self.description_popup:
            self.description_popup.hide()
        if self.drawing_popup:
            self.drawing_popup.hide()
        self.root.destroy()
        
    def load_settings(self) -> Dict[str, Any]:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    merged = self.DEFAULT_SETTINGS.copy()
                    merged.update(settings)
                    return merged
            except (json.JSONDecodeError, IOError):
                pass
        return self.DEFAULT_SETTINGS.copy()
        
    def save_settings(self) -> None:
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except IOError as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            
    def load_history(self) -> Dict[str, Any]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {'customers': {}, 'recent_jobs': []}
        
    def save_history(self) -> None:
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except IOError as e:
            self.log_message(f"Warning: Failed to save history: {e}", 'warning')
    
    def create_widgets(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create Job tab
        self.job_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.job_frame, text="Create Job")
        self._create_job_tab()
        
        # Add to Existing Job tab (NEW)
        self.add_to_job_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.add_to_job_frame, text="Add to Job")
        self._create_add_to_job_tab()
        
        # Bulk Create tab (NEW)
        self.bulk_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.bulk_frame, text="Bulk Create")
        self._create_bulk_tab()
        
        # Search tab
        self.search_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.search_frame, text="Search")
        self._create_search_tab()
        
        # Import tab
        self.import_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.import_frame, text="Import Blueprints")
        self._create_import_tab()
        
        # History tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History")
        self._create_history_tab()
        
        self._create_menu()
        
    def _create_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Settings", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="About", command=self.show_about)
        
    def _create_job_tab(self) -> None:
        # Input frame
        input_frame = ttk.LabelFrame(self.job_frame, text="Job Information", padding="10")
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Customer
        ttk.Label(input_frame, text="Customer Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.customer_combo = ttk.Combobox(input_frame, textvariable=self.customer_var, width=40)
        self.customer_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Job number
        ttk.Label(input_frame, text="Job Number(s):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(input_frame, textvariable=self.job_number_var, width=40).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=5
        )
        self.job_number_status_label = ttk.Label(
            input_frame, text="", font=('Arial', 8), foreground='gray'
        )
        self.job_number_status_label.grid(row=1, column=2, sticky=tk.W, padx=5)
        ttk.Label(input_frame, 
                 text="Examples: 12345 or 12345, 12346 or 12345-12350", 
                 font=('Arial', 8), foreground='gray').grid(
            row=1, column=1, sticky=tk.W, pady=(25, 0)
        )
                
        # Description
        ttk.Label(input_frame, text="Description:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.description_entry = ttk.Entry(input_frame, textvariable=self.description_var, width=40)
        self.description_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Drawing numbers
        ttk.Label(input_frame, text="Drawing Numbers:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.drawing_entry = ttk.Entry(input_frame, textvariable=self.drawing_numbers_var, width=40)
        self.drawing_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Label(input_frame, text="(comma-separated, optional)", 
                 font=('Arial', 8), foreground='gray').grid(row=3, column=2, sticky=tk.W)
        
        # ITAR
        ttk.Checkbutton(
            input_frame, 
            text="ITAR Job (uses separate directories)", 
            variable=self.itar_var
        ).grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
        
        # Initialize autocomplete
        self.description_popup = AutocompletePopup(
            self.root, self.description_entry, 
            lambda s: self.description_var.set(s)
        )
        self.drawing_popup = AutocompletePopup(
            self.root, self.drawing_entry, 
            self._on_drawing_autocomplete_select
        )
        
        input_frame.columnconfigure(1, weight=1)
        
        # Files drop zone
        files_frame = ttk.LabelFrame(self.job_frame, text="Job Files (Optional)", padding="10")
        files_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(
            files_frame, 
            text="Drop files here. Blueprint files → blueprints folder, others → job folder",
            font=('Arial', 9), foreground='#666'
        ).pack(pady=5)
        
        self.job_drop_zone = FileDropZone(
            files_frame, self.handle_job_files, 
            file_label="job files", height=100
        )
        self.job_drop_zone.pack(fill=tk.BOTH, expand=True)
        
        # File list
        list_container = ttk.Frame(files_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        list_scroll = ttk.Scrollbar(list_container)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.job_files_listbox = tk.Listbox(list_container, yscrollcommand=list_scroll.set, height=5)
        self.job_files_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        list_scroll.config(command=self.job_files_listbox.yview)
        
        ttk.Button(files_frame, text="Remove Selected", command=self.remove_job_file).pack(pady=5)
        
        # Action buttons
        button_frame = ttk.Frame(self.job_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(button_frame, text="Create Job & Link Files", 
                  command=self.create_job).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", 
                  command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Open Blueprints", 
                  command=self.open_blueprints_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Open Customer Files", 
                  command=self.open_customer_files_folder).pack(side=tk.LEFT, padx=5)
        
        # Log
        log_frame = ttk.LabelFrame(self.job_frame, text="Activity Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        log_scroll = ttk.Scrollbar(log_frame)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=8, yscrollcommand=log_scroll.set, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scroll.config(command=self.log_text.yview)
    
    def _create_add_to_job_tab(self) -> None:
        """Create the Add to Existing Job tab"""
        # Instructions
        inst_frame = ttk.Frame(self.add_to_job_frame)
        inst_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(inst_frame, 
                 text="Add documents to an existing job folder and/or blueprints",
                 font=('Arial', 10)).pack()
        
        # Main content - PanedWindow for resizable sections
        paned = ttk.PanedWindow(self.add_to_job_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left side - Job browser
        browser_frame = ttk.LabelFrame(paned, text="Select Existing Job", padding="10")
        paned.add(browser_frame, weight=1)
        
        # Customer filter
        filter_frame = ttk.Frame(browser_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Customer:").pack(side=tk.LEFT)
        self.add_customer_var = tk.StringVar()
        self.add_customer_combo = ttk.Combobox(
            filter_frame, textvariable=self.add_customer_var, width=20
        )
        self.add_customer_combo.pack(side=tk.LEFT, padx=5)
        self.add_customer_combo.bind('<<ComboboxSelected>>', self._refresh_job_tree)
        
        # ITAR filter
        self.add_itar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="ITAR", 
                       variable=self.add_itar_var,
                       command=self._refresh_job_tree).pack(side=tk.LEFT, padx=5)
        
        # Search frame
        search_frame = ttk.Frame(browser_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.add_search_var = tk.StringVar()
        self.add_search_entry = ttk.Entry(search_frame, textvariable=self.add_search_var, width=20)
        self.add_search_entry.pack(side=tk.LEFT, padx=5)
        self.add_search_entry.bind('<Return>', self._search_jobs)
        
        ttk.Button(search_frame, text="Search", 
                  command=self._search_jobs).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="Clear", 
                  command=self._clear_job_search).pack(side=tk.LEFT, padx=2)
        
        # Job tree
        tree_frame = ttk.Frame(browser_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.job_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, 
                                     selectmode='browse', show='tree headings',
                                     columns=('path',))
        self.job_tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.job_tree.yview)
        
        self.job_tree.heading('#0', text='Customer / Job')
        self.job_tree.heading('path', text='Path')
        self.job_tree.column('#0', width=250)
        self.job_tree.column('path', width=0, stretch=False)  # Hidden column for path
        
        self.job_tree.bind('<<TreeviewSelect>>', self._on_job_tree_select)
        
        # Selected job info
        self.selected_job_label = ttk.Label(browser_frame, text="No job selected", 
                                            font=('Arial', 9), foreground='gray')
        self.selected_job_label.pack(pady=5)
        
        # Right side - File adding
        add_frame = ttk.LabelFrame(paned, text="Add Files", padding="10")
        paned.add(add_frame, weight=1)
        
        # Destination options
        dest_frame = ttk.LabelFrame(add_frame, text="Destination", padding="5")
        dest_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.add_dest_var = tk.StringVar(value='both')
        ttk.Radiobutton(dest_frame, text="Blueprints + Job (linked)", 
                       variable=self.add_dest_var, value='both').pack(anchor=tk.W)
        ttk.Radiobutton(dest_frame, text="Blueprints only", 
                       variable=self.add_dest_var, value='blueprints').pack(anchor=tk.W)
        ttk.Radiobutton(dest_frame, text="Job folder only (copy)", 
                       variable=self.add_dest_var, value='job').pack(anchor=tk.W)
        
        ttk.Label(dest_frame, 
                 text="'Blueprints + Job' saves to blueprints and creates a link in the job folder",
                 font=('Arial', 8), foreground='gray').pack(anchor=tk.W, pady=(5, 0))
        
        # File drop zone
        self.add_drop_zone = FileDropZone(
            add_frame, self._handle_add_files, 
            file_label="files to add", height=80
        )
        self.add_drop_zone.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # File list
        list_frame = ttk.Frame(add_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.add_files_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set, height=6)
        self.add_files_listbox.pack(fill=tk.BOTH, expand=True)
        list_scroll.config(command=list_scroll.set)
        
        self.add_files: List[str] = []
        
        # Buttons
        btn_frame = ttk.Frame(add_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="Remove Selected", 
                  command=self._remove_add_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Clear All", 
                  command=self._clear_add_files).pack(side=tk.LEFT, padx=2)
        
        # Add button (prominent)
        ttk.Button(add_frame, text="Add Files to Selected Job", 
                  command=self._add_files_to_job).pack(fill=tk.X, pady=5)
        
        # Status/log
        self.add_status_label = ttk.Label(add_frame, text="", font=('Arial', 9))
        self.add_status_label.pack(pady=5)
        
        # Initialize the customer list and job tree
        self._populate_add_customer_list()
    
    def _search_jobs(self, event=None) -> None:
        """Search for jobs by customer name or job number"""
        search_term = self.add_search_var.get().strip().lower()
        
        if not search_term:
            self._refresh_job_tree()
            return
        
        # Clear existing items
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)
        
        # Search both regular and ITAR directories
        dirs_to_search = []
        
        # Regular directories
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir and os.path.exists(cf_dir):
            dirs_to_search.append(('', cf_dir))
        
        # ITAR directories
        itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            dirs_to_search.append(('ITAR', itar_cf_dir))
        
        if not dirs_to_search:
            self.add_status_label.config(text="No directories configured", foreground='red')
            return
        
        results_count = 0
        
        try:
            for prefix, cf_dir in dirs_to_search:
                customers = [d for d in os.listdir(cf_dir) 
                            if os.path.isdir(os.path.join(cf_dir, d))]
                
                for customer in sorted(customers):
                    customer_path = os.path.join(cf_dir, customer)
                    job_docs_path = os.path.join(customer_path, 'job documents')
                    
                    if not os.path.exists(job_docs_path):
                        continue
                    
                    # Find matching jobs
                    matching_jobs = []
                    try:
                        jobs = [d for d in os.listdir(job_docs_path) 
                               if os.path.isdir(os.path.join(job_docs_path, d))]
                        
                        for job in jobs:
                            # Match against job name or customer name
                            if (search_term in job.lower() or 
                                search_term in customer.lower()):
                                job_path = os.path.join(job_docs_path, job)
                                matching_jobs.append((job, job_path))
                    except OSError:
                        pass
                    
                    # Only show customer if they have matching jobs
                    if matching_jobs:
                        display_name = f"📁 {customer}" if not prefix else f"📁 [{prefix}] {customer}"
                        customer_node = self.job_tree.insert('', 'end', text=display_name, 
                                                             values=(customer_path,), open=True)
                        
                        for job, job_path in sorted(matching_jobs):
                            self.job_tree.insert(customer_node, 'end', text=f"📋 {job}", 
                                               values=(job_path,))
                            results_count += 1
                        
        except OSError as e:
            self.add_status_label.config(text=f"Search error: {e}", foreground='red')
            return
        
        self.selected_job_label.config(
            text=f"Found {results_count} job(s)" if results_count else "No matches found",
            foreground='gray'
        )
    
    def _clear_job_search(self) -> None:
        """Clear search and show all jobs"""
        self.add_search_var.set('')
        self._refresh_job_tree()

    def _populate_add_customer_list(self) -> None:
        """Populate customer dropdown for Add to Job tab"""
        customers = set()
        
        # Check regular directories
        bp_dir = self.settings.get('blueprints_dir', '')
        cf_dir = self.settings.get('customer_files_dir', '')
        
        for directory in [bp_dir, cf_dir]:
            if directory and os.path.exists(directory):
                try:
                    for d in os.listdir(directory):
                        if os.path.isdir(os.path.join(directory, d)):
                            customers.add(d)
                except OSError:
                    pass
        
        # Check ITAR directories too
        itar_bp = self.settings.get('itar_blueprints_dir', '')
        itar_cf = self.settings.get('itar_customer_files_dir', '')
        
        for directory in [itar_bp, itar_cf]:
            if directory and os.path.exists(directory):
                try:
                    for d in os.listdir(directory):
                        if os.path.isdir(os.path.join(directory, d)):
                            customers.add(d)
                except OSError:
                    pass
        
        self.add_customer_combo['values'] = ['(All Customers)'] + sorted(customers)
        self.add_customer_combo.set('(All Customers)')
        self._refresh_job_tree()
    
    def _refresh_job_tree(self, event=None) -> None:
        """Refresh the job tree based on filters"""
        # Clear existing items
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)
        
        # Build list of directories to search
        dirs_to_search = []
        show_itar_only = self.add_itar_var.get()
        
        if not show_itar_only:
            # Show regular directories
            cf_dir = self.settings.get('customer_files_dir', '')
            if cf_dir and os.path.exists(cf_dir):
                dirs_to_search.append(('', cf_dir, False))
        
        # Always check ITAR if checkbox is set, or include if showing all
        itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
        if itar_cf_dir and os.path.exists(itar_cf_dir):
            if show_itar_only:
                dirs_to_search.append(('ITAR', itar_cf_dir, True))
            elif not show_itar_only:
                # Include ITAR in results but mark them
                dirs_to_search.append(('ITAR', itar_cf_dir, True))
        
        if not dirs_to_search:
            return
        
        selected_customer = self.add_customer_var.get()
        show_all = selected_customer == '(All Customers)' or not selected_customer
        
        try:
            for prefix, cf_dir, is_itar in dirs_to_search:
                # Get customers to show
                if show_all:
                    customers = [d for d in os.listdir(cf_dir) 
                               if os.path.isdir(os.path.join(cf_dir, d))]
                else:
                    customers = [selected_customer] if os.path.isdir(os.path.join(cf_dir, selected_customer)) else []
                
                for customer in sorted(customers):
                    customer_path = os.path.join(cf_dir, customer)
                    job_docs_path = os.path.join(customer_path, 'job documents')
                    
                    if not os.path.exists(job_docs_path):
                        continue
                    
                    # Add customer node
                    display_name = f"📁 {customer}" if not prefix else f"📁 [{prefix}] {customer}"
                    customer_node = self.job_tree.insert('', 'end', text=display_name, 
                                                         values=(customer_path,), open=False)
                    
                    # Add job folders under customer
                    try:
                        jobs = [d for d in os.listdir(job_docs_path) 
                               if os.path.isdir(os.path.join(job_docs_path, d))]
                        
                        for job in sorted(jobs):
                            job_path = os.path.join(job_docs_path, job)
                            self.job_tree.insert(customer_node, 'end', text=f"📋 {job}", 
                                               values=(job_path,))
                    except OSError:
                        pass
                    
        except OSError as e:
            self.add_status_label.config(text=f"Error reading directories: {e}", foreground='red')
    
    def _on_job_tree_select(self, event=None) -> None:
        """Handle job selection in tree"""
        selection = self.job_tree.selection()
        if not selection:
            self.selected_job_label.config(text="No job selected", foreground='gray')
            return
        
        item = selection[0]
        item_text = self.job_tree.item(item, 'text')
        item_path = self.job_tree.item(item, 'values')[0]
        
        # Check if this is a job folder (has parent) or customer folder
        parent = self.job_tree.parent(item)
        if parent:
            # This is a job folder
            self.selected_job_label.config(
                text=f"Selected: {item_text.replace('📋 ', '')}", 
                foreground='green'
            )
        else:
            # This is a customer folder
            self.selected_job_label.config(
                text="Select a job folder, not customer", 
                foreground='orange'
            )
    
    def _handle_add_files(self, files: List[str]) -> None:
        """Handle files dropped for adding to existing job"""
        for file_path in files:
            if file_path not in self.add_files:
                self.add_files.append(file_path)
                self.add_files_listbox.insert(tk.END, os.path.basename(file_path))
    
    def _remove_add_file(self) -> None:
        """Remove selected file from add list"""
        selection = self.add_files_listbox.curselection()
        if selection:
            index = selection[0]
            self.add_files_listbox.delete(index)
            del self.add_files[index]
    
    def _clear_add_files(self) -> None:
        """Clear all files from add list"""
        self.add_files = []
        self.add_files_listbox.delete(0, tk.END)
    
    def _add_files_to_job(self) -> None:
        """Add files to the selected existing job"""
        # Validate selection
        selection = self.job_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a job folder")
            return
        
        item = selection[0]
        parent = self.job_tree.parent(item)
        
        if not parent:
            messagebox.showwarning("Invalid Selection", 
                                  "Please select a job folder, not a customer folder")
            return
        
        if not self.add_files:
            messagebox.showwarning("No Files", "Please add files to upload")
            return
        
        job_path = self.job_tree.item(item, 'values')[0]
        job_name = self.job_tree.item(item, 'text').replace('📋 ', '')
        
        # Get customer from parent
        customer_text = self.job_tree.item(parent, 'text').replace('📁 ', '')
        # Remove ITAR prefix if present
        if customer_text.startswith('[ITAR] '):
            customer = customer_text[7:]
            is_itar = True
        else:
            customer = customer_text
            # Detect ITAR by checking if path is under ITAR directory
            itar_cf_dir = self.settings.get('itar_customer_files_dir', '')
            is_itar = itar_cf_dir and job_path.startswith(itar_cf_dir)
        
        # Get correct blueprints directory
        bp_dir, _ = self._get_directories(is_itar)
        
        if not bp_dir:
            messagebox.showerror("Error", "Blueprints directory not configured")
            return
        
        customer_blueprints = Path(bp_dir) / customer
        destination = self.add_dest_var.get()
        
        added = 0
        skipped = 0
        errors = 0
        
        for file_path in self.add_files:
            file_name = os.path.basename(file_path)
            
            try:
                if destination == 'blueprints':
                    # Only add to blueprints
                    customer_blueprints.mkdir(parents=True, exist_ok=True)
                    dest = customer_blueprints / file_name
                    if not dest.exists():
                        shutil.copy2(file_path, dest)
                        added += 1
                    else:
                        skipped += 1
                        
                elif destination == 'job':
                    # Only add to job folder (copy)
                    dest = Path(job_path) / file_name
                    if not dest.exists():
                        shutil.copy2(file_path, dest)
                        added += 1
                    else:
                        skipped += 1
                        
                else:  # 'both' - blueprints + linked to job
                    customer_blueprints.mkdir(parents=True, exist_ok=True)
                    bp_dest = customer_blueprints / file_name
                    job_dest = Path(job_path) / file_name
                    
                    # Copy to blueprints if not there
                    if not bp_dest.exists():
                        shutil.copy2(file_path, bp_dest)
                    
                    # Link to job if not there
                    if not job_dest.exists():
                        self._create_link(bp_dest, job_dest)
                        added += 1
                    else:
                        skipped += 1
                        
            except Exception as e:
                errors += 1
                self.log_message(f"Error adding {file_name}: {e}", 'error')
        
        # Summary
        summary = f"Added: {added}"
        if skipped:
            summary += f", Skipped (exists): {skipped}"
        if errors:
            summary += f", Errors: {errors}"
        
        self.add_status_label.config(
            text=summary, 
            foreground='green' if errors == 0 else 'orange'
        )
        
        self.log_message(f"Added files to {job_name}: {summary}")
        
        if added > 0:
            messagebox.showinfo("Files Added", f"Successfully added {added} file(s) to:\n{job_name}")
            self._clear_add_files()

    def _create_bulk_tab(self) -> None:
        """Create the bulk job creation tab"""
        # Instructions
        inst_frame = ttk.LabelFrame(self.bulk_frame, text="Bulk Job Creation", padding="10")
        inst_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(inst_frame, 
                 text="Create multiple jobs at once. Enter data in CSV format or import from file.",
                 font=('Arial', 10)).pack(anchor=tk.W)
        ttk.Label(inst_frame, 
                 text="Format: customer, job_number, description, drawing_numbers (optional)",
                 font=('Arial', 9), foreground='gray').pack(anchor=tk.W, pady=(5, 0))
        ttk.Label(inst_frame, 
                 text='Example: Acme Corp, 12345, Widget Assembly, DWG-001, DWG-002',
                 font=('Arial', 9, 'italic'), foreground='gray').pack(anchor=tk.W)
        
        self.bulk_itar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(inst_frame, text="All jobs are ITAR", 
                       variable=self.bulk_itar_var).pack(anchor=tk.W, pady=5)
        
        # Text input
        text_frame = ttk.LabelFrame(self.bulk_frame, text="Job Data (CSV Format)", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        toolbar = ttk.Frame(text_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="Import CSV", 
                  command=self._import_bulk_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Clear", 
                  command=self._clear_bulk_text).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Validate", 
                  command=self._validate_bulk_data).pack(side=tk.LEFT, padx=2)
        
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.bulk_text = tk.Text(text_frame, height=12, yscrollcommand=text_scroll.set, 
                                 wrap=tk.NONE, font=('Courier', 10))
        self.bulk_text.pack(fill=tk.BOTH, expand=True)
        text_scroll.config(command=self.bulk_text.yview)
        
        # Placeholder
        placeholder = "# Enter jobs in CSV format (one per line)\n"
        placeholder += "# customer, job_number, description, drawing_numbers\n"
        placeholder += "# Lines starting with # are ignored\n\n"
        placeholder += "Acme Corp, 12345, Widget Assembly, DWG-001\n"
        placeholder += "Acme Corp, 12346, Gadget Housing, DWG-002, DWG-003\n"
        placeholder += "Beta Inc, 54321, Custom Part\n"
        self.bulk_text.insert('1.0', placeholder)
        
        # Preview
        preview_frame = ttk.LabelFrame(self.bulk_frame, text="Preview / Validation", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('Status', 'Customer', 'Job Number', 'Description', 'Drawings')
        self.bulk_tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=6)
        
        self.bulk_tree.heading('Status', text='Status')
        self.bulk_tree.column('Status', width=100)
        for col in columns[1:]:
            self.bulk_tree.heading(col, text=col)
            self.bulk_tree.column(col, width=120)
        
        bulk_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.bulk_tree.yview)
        self.bulk_tree.configure(yscrollcommand=bulk_scroll.set)
        
        self.bulk_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bulk_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(self.bulk_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Create All Jobs", 
                  command=self._create_bulk_jobs).pack(side=tk.LEFT, padx=5)
        
        self.bulk_status_label = ttk.Label(button_frame, text="", font=('Arial', 9))
        self.bulk_status_label.pack(side=tk.LEFT, padx=20)
        
        self.bulk_progress = ttk.Progressbar(button_frame, length=200, mode='determinate')
        self.bulk_progress.pack(side=tk.RIGHT, padx=5)
    
    def _import_bulk_csv(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.bulk_text.delete('1.0', tk.END)
                self.bulk_text.insert('1.0', content)
                self._validate_bulk_data()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to read file: {e}")
    
    def _clear_bulk_text(self) -> None:
        self.bulk_text.delete('1.0', tk.END)
        for item in self.bulk_tree.get_children():
            self.bulk_tree.delete(item)
        self.bulk_status_label.config(text="")
    
    def _parse_bulk_data(self) -> List[Dict[str, Any]]:
        content = self.bulk_text.get('1.0', tk.END).strip()
        jobs = []
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.strip()
            
            if not line or line.startswith('#'):
                continue
            
            try:
                reader = csv.reader(StringIO(line))
                parts = next(reader)
            except Exception:
                parts = [p.strip() for p in line.split(',')]
            
            if len(parts) < 3:
                jobs.append({
                    'line': line_num,
                    'valid': False,
                    'error': 'Need: customer, job_number, description',
                    'raw': line
                })
                continue
            
            customer = parts[0].strip()
            job_number = parts[1].strip()
            description = parts[2].strip()
            drawings = [d.strip() for d in parts[3:] if d.strip()]
            
            errors = []
            if not customer:
                errors.append("Missing customer")
            if not job_number:
                errors.append("Missing job number")
            if not description:
                errors.append("Missing description")
            
            jobs.append({
                'line': line_num,
                'valid': len(errors) == 0,
                'error': '; '.join(errors) if errors else None,
                'customer': customer,
                'job_number': job_number,
                'description': description,
                'drawings': drawings,
                'raw': line
            })
        
        return jobs
    
    def _validate_bulk_data(self) -> bool:
        for item in self.bulk_tree.get_children():
            self.bulk_tree.delete(item)
        
        jobs = self._parse_bulk_data()
        
        valid_count = 0
        invalid_count = 0
        
        for job in jobs:
            if job['valid']:
                status = "✓ Valid"
                valid_count += 1
                
                is_dup, _ = self.check_duplicate_job_number(
                    job['customer'], job['job_number']
                )
                if is_dup:
                    status = "⚠ Duplicate"
            else:
                status = f"✗ {job.get('error', 'Invalid')}"
                invalid_count += 1
            
            self.bulk_tree.insert('', tk.END, values=(
                status,
                job.get('customer', ''),
                job.get('job_number', ''),
                job.get('description', ''),
                ', '.join(job.get('drawings', []))
            ))
        
        self.bulk_status_label.config(
            text=f"Valid: {valid_count} | Invalid: {invalid_count}",
            foreground='green' if invalid_count == 0 else 'orange'
        )
        
        return invalid_count == 0
    
    def _create_bulk_jobs(self) -> None:
        if not self._validate_bulk_data():
            if not messagebox.askyesno(
                "Validation Warning",
                "Some jobs have errors. Create only valid jobs?"
            ):
                return
        
        jobs = [j for j in self._parse_bulk_data() if j['valid']]
        
        if not jobs:
            messagebox.showwarning("No Jobs", "No valid jobs to create")
            return
        
        is_itar = self.bulk_itar_var.get()
        bp_dir, cf_dir = self._get_directories(is_itar)
        
        if not bp_dir or not cf_dir:
            msg = "ITAR directories" if is_itar else "Directories"
            messagebox.showerror("Error", f"{msg} not configured in Settings")
            return
        
        self.bulk_progress['maximum'] = len(jobs)
        self.bulk_progress['value'] = 0
        
        created = 0
        failed = 0
        
        for i, job in enumerate(jobs):
            try:
                success = self._create_single_job(
                    customer=job['customer'],
                    job_number=job['job_number'],
                    description=job['description'],
                    drawings=job['drawings'],
                    is_itar=is_itar,
                    files=[],
                    log_to_ui=False
                )
                if success:
                    created += 1
                else:
                    failed += 1
            except Exception as e:
                self.log_message(f"Error creating job {job['job_number']}: {e}", 'error')
                failed += 1
            
            self.bulk_progress['value'] = i + 1
            self.root.update_idletasks()
        
        self.bulk_progress['value'] = 0
        
        messagebox.showinfo(
            "Bulk Creation Complete",
            f"Created: {created}\nFailed: {failed}\nTotal: {len(jobs)}"
        )
        
        self.refresh_history()
        
    def _create_search_tab(self) -> None:
        inst_frame = ttk.Frame(self.search_frame)
        inst_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(inst_frame, 
                 text="Search for jobs by customer, job number, description, or drawing",
                 font=('Arial', 10)).pack()
        
        search_frame = ttk.LabelFrame(self.search_frame, text="Search Criteria", padding="10")
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(search_frame, text="Search:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=50)
        self.search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.search_entry.bind('<Return>', lambda e: self.perform_search())
        
        checkbox_frame = ttk.Frame(search_frame)
        checkbox_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        self.search_customer_var = tk.BooleanVar(value=True)
        self.search_job_var = tk.BooleanVar(value=True)
        self.search_desc_var = tk.BooleanVar(value=True)
        self.search_drawing_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(checkbox_frame, text="Customer", 
                       variable=self.search_customer_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(checkbox_frame, text="Job #", 
                       variable=self.search_job_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(checkbox_frame, text="Description", 
                       variable=self.search_desc_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(checkbox_frame, text="Drawings", 
                       variable=self.search_drawing_var).pack(side=tk.LEFT, padx=5)
        
        search_frame.columnconfigure(1, weight=1)
        
        button_frame = ttk.Frame(search_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        
        mode_frame = ttk.LabelFrame(self.search_frame, text="Search Mode", padding="10")
        mode_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.search_mode_var = tk.StringVar(value='all')
        ttk.Radiobutton(mode_frame, text="Search All Folders", 
                       variable=self.search_mode_var, value='all').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Strict Format Only (faster)", 
                       variable=self.search_mode_var, value='strict').pack(side=tk.LEFT, padx=5)
        
        result_frame = ttk.LabelFrame(self.search_frame, text="Search Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('Date', 'Customer', 'Job Number', 'Description', 'Drawings')
        self.search_tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=12)
        
        for col in columns:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=140)
        
        search_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, 
                                      command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=search_scroll.set)
        
        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.search_tree.bind('<Double-Button-1>', lambda e: self.open_selected_job())
        
        self.search_menu = tk.Menu(self.search_tree, tearoff=0)
        self.search_menu.add_command(label="Open Job Folder", command=self.open_selected_job)
        self.search_menu.add_command(label="Open Blueprints", command=self.open_selected_blueprints)
        self.search_menu.add_separator()
        self.search_menu.add_command(label="Copy Path", command=self.copy_job_path)
        
        self.search_tree.bind('<Button-3>', self._show_search_context_menu)
        
        self.search_count_label = ttk.Label(result_frame, text="", font=('Arial', 9), foreground='gray')
        self.search_count_label.pack(pady=5)
        
        self.search_progress = ttk.Progressbar(result_frame, mode='indeterminate', length=300)
        
    def _create_import_tab(self) -> None:
        ttk.Label(self.import_frame, 
                 text="Import files to blueprints folder",
                 font=('Arial', 10)).pack(pady=10)
        
        select_frame = ttk.LabelFrame(self.import_frame, text="Customer Selection", padding="10")
        select_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(select_frame, text="Customer Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.import_customer_var = tk.StringVar()
        self.import_customer_combo = ttk.Combobox(
            select_frame, textvariable=self.import_customer_var, width=40
        )
        self.import_customer_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.populate_import_customer_list()
        
        select_frame.columnconfigure(1, weight=1)
        
        drop_frame = ttk.LabelFrame(self.import_frame, text="Files to Import", padding="10")
        drop_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.drop_zone = FileDropZone(drop_frame, self.handle_dropped_files, 
                                     file_label="files", height=150)
        self.drop_zone.pack(fill=tk.BOTH, expand=True)
        
        list_frame = ttk.Frame(drop_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        list_scroll = ttk.Scrollbar(list_frame)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.import_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set, height=6)
        self.import_listbox.pack(fill=tk.BOTH, expand=True)
        list_scroll.config(command=self.import_listbox.yview)
        
        button_frame = ttk.Frame(self.import_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Check & Import", 
                  command=self.check_and_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear List", 
                  command=self.clear_import_list).pack(side=tk.LEFT, padx=5)
        
        result_frame = ttk.LabelFrame(self.import_frame, text="Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        result_scroll = ttk.Scrollbar(result_frame)
        result_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.import_log = tk.Text(result_frame, height=6, yscrollcommand=result_scroll.set, 
                                  wrap=tk.WORD)
        self.import_log.pack(fill=tk.BOTH, expand=True)
        result_scroll.config(command=self.import_log.yview)
        
    def _create_history_tab(self) -> None:
        list_frame = ttk.LabelFrame(self.history_frame, text="Recent Jobs", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ('Date', 'Customer', 'Job Number', 'Description', 'Drawings')
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=140)
        
        history_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, 
                                       command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        button_frame = ttk.Frame(self.history_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear History", 
                  command=self.clear_history).pack(side=tk.LEFT, padx=5)
        
        self.refresh_history()
    
    # Event Handlers
    def _on_customer_change(self, *args) -> None:
        self._on_job_number_change()
    
    def _on_job_number_change(self, *args) -> None:
        customer = self.customer_var.get().strip()
        job_number = self.job_number_var.get().strip()
        
        if not customer or not job_number:
            self.job_number_status_label.config(text="", foreground='gray')
            return
        
        job_numbers = self.parse_job_numbers(job_number)
        if not job_numbers:
            self.job_number_status_label.config(text="", foreground='gray')
            return
        
        is_duplicate, _ = self.check_duplicate_job_number(customer, job_numbers[0])
        
        if is_duplicate:
            self.job_number_status_label.config(text="⚠ Exists!", foreground='red')
        else:
            self.job_number_status_label.config(text="✓ OK", foreground='green')
    
    def _on_description_change(self, *args) -> None:
        current_text = self.description_var.get().lower()
        
        if len(current_text) < 2:
            if self.description_popup:
                self.description_popup.hide()
            return
        
        descriptions = set()
        for job in self.history.get('recent_jobs', []):
            desc = job.get('description', '')
            if desc and current_text in desc.lower():
                descriptions.add(desc)
        
        if descriptions and self.description_popup:
            self.description_popup.show(sorted(descriptions)[:10])
        elif self.description_popup:
            self.description_popup.hide()
    
    def _on_drawing_numbers_change(self, *args) -> None:
        current_text = self.drawing_numbers_var.get()
        parts = current_text.split(',')
        
        if not parts:
            if self.drawing_popup:
                self.drawing_popup.hide()
            return
        
        last_part = parts[-1].strip().lower()
        
        if len(last_part) < 1:
            if self.drawing_popup:
                self.drawing_popup.hide()
            return
        
        drawing_numbers = set()
        for job in self.history.get('recent_jobs', []):
            for drawing in job.get('drawings', []):
                if drawing and last_part in drawing.lower():
                    drawing_numbers.add(drawing)
        
        if drawing_numbers and self.drawing_popup:
            self.drawing_popup.show(sorted(drawing_numbers)[:10])
        elif self.drawing_popup:
            self.drawing_popup.hide()
    
    def _on_drawing_autocomplete_select(self, selected: str) -> None:
        current = self.drawing_numbers_var.get()
        parts = current.split(',')
        parts[-1] = ' ' + selected
        self.drawing_numbers_var.set(', '.join(parts) + ', ')
        self.drawing_entry.focus_set()
    
    def _show_search_context_menu(self, event: tk.Event) -> None:
        item = self.search_tree.identify_row(event.y)
        if item:
            self.search_tree.selection_set(item)
            self.search_menu.post(event.x_root, event.y_root)
    
    # Helper Methods
    def populate_customer_list(self) -> None:
        customers = set()
        blueprints_dir = self.settings.get('blueprints_dir', '')
        
        if blueprints_dir and os.path.exists(blueprints_dir):
            try:
                for d in os.listdir(blueprints_dir):
                    if os.path.isdir(os.path.join(blueprints_dir, d)):
                        customers.add(d)
            except OSError:
                pass
        
        for customer in self.history.get('customers', {}).keys():
            customers.add(customer)
        
        self.customer_combo['values'] = sorted(customers)
        
    def populate_import_customer_list(self) -> None:
        customers = []
        blueprints_dir = self.settings.get('blueprints_dir', '')
        
        if blueprints_dir and os.path.exists(blueprints_dir):
            try:
                customers = [d for d in os.listdir(blueprints_dir) 
                           if os.path.isdir(os.path.join(blueprints_dir, d))]
            except OSError:
                pass
        
        self.import_customer_combo['values'] = sorted(customers)
    
    def log_message(self, message: str, level: str = 'info') -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
    def import_log_message(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.import_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.import_log.see(tk.END)
    
    def is_blueprint_file(self, filename: str) -> bool:
        file_ext = Path(filename).suffix.lower()
        blueprint_extensions = self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
        return file_ext in blueprint_extensions
    
    def check_duplicate_job_number(self, customer: str, job_number: str) -> Tuple[bool, Optional[str]]:
        for job in self.history.get('recent_jobs', []):
            if (job.get('customer', '').lower() == customer.lower() and
                job.get('job_number', '').lower() == job_number.lower()):
                return True, job.get('path', 'Unknown')
        
        customer_files_dir = self.settings.get('customer_files_dir', '')
        if customer_files_dir:
            job_docs_path = Path(customer_files_dir) / customer / 'job documents'
            if job_docs_path.exists():
                try:
                    for item in job_docs_path.iterdir():
                        if item.is_dir():
                            dir_parts = item.name.split('_', 1)
                            if dir_parts and dir_parts[0].lower() == job_number.lower():
                                return True, str(item)
                except OSError:
                    pass
        
        return False, None

    def parse_job_numbers(self, job_number_input: str) -> List[str]:
        job_numbers = []
        parts = [part.strip() for part in job_number_input.split(',')]
        
        for part in parts:
            if not part:
                continue
            if '-' in part:
                try:
                    range_parts = part.split('-')
                    if len(range_parts) == 2:
                        start_num = int(range_parts[0].strip())
                        end_num = int(range_parts[1].strip())
                        if start_num <= end_num:
                            for num in range(start_num, end_num + 1):
                                job_numbers.append(str(num))
                        else:
                            job_numbers.append(part)
                    else:
                        job_numbers.append(part)
                except ValueError:
                    job_numbers.append(part)
            else:
                job_numbers.append(part)
        
        return job_numbers
    
    def _get_directories(self, is_itar: bool) -> Tuple[Optional[str], Optional[str]]:
        if is_itar:
            return (
                self.settings.get('itar_blueprints_dir'),
                self.settings.get('itar_customer_files_dir')
            )
        return (
            self.settings.get('blueprints_dir'),
            self.settings.get('customer_files_dir')
        )
    
    def _create_link(self, source: Path, dest: Path) -> bool:
        link_type = self.settings.get('link_type', 'hard')
        
        try:
            if link_type == 'hard':
                os.link(source, dest)
            elif link_type == 'symbolic':
                os.symlink(source, dest)
            else:
                shutil.copy2(source, dest)
            return True
        except OSError as e:
            self.log_message(f"Link error: {e}", 'error')
            return False
    
    def open_folder(self, path: str) -> None:
        import platform
        import subprocess
        
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder: {e}")
    
    # File Handling
    def handle_job_files(self, files: List[str]) -> None:
        for file_path in files:
            if file_path not in self.job_files:
                self.job_files.append(file_path)
                self.job_files_listbox.insert(tk.END, os.path.basename(file_path))
                
    def remove_job_file(self) -> None:
        selection = self.job_files_listbox.curselection()
        if selection:
            index = selection[0]
            self.job_files_listbox.delete(index)
            del self.job_files[index]
    
    def handle_dropped_files(self, files: List[str]) -> None:
        for file_path in files:
            if file_path not in self.import_files:
                self.import_files.append(file_path)
                self.import_listbox.insert(tk.END, os.path.basename(file_path))
                
    def clear_import_list(self) -> None:
        self.import_files = []
        self.import_listbox.delete(0, tk.END)
    
    # Job Creation
    def create_job(self) -> None:
        customer = self.customer_var.get().strip()
        job_number_input = self.job_number_var.get().strip()
        description = self.description_var.get().strip()
        drawing_numbers_str = self.drawing_numbers_var.get().strip()
        is_itar = self.itar_var.get()
        
        if not all([customer, job_number_input, description]):
            messagebox.showerror("Error", "Please fill in customer, job number, and description")
            return
        
        # ITAR validation first (bug fix)
        blueprints_dir, customer_files_dir = self._get_directories(is_itar)
        
        if is_itar and (not blueprints_dir or not customer_files_dir):
            messagebox.showerror("Error", "ITAR directories not configured in Settings")
            return
        
        if not blueprints_dir or not customer_files_dir:
            messagebox.showerror("Error", "Please configure directories in Settings")
            return
        
        drawings = []
        if drawing_numbers_str:
            drawings = [d.strip() for d in drawing_numbers_str.split(',') if d.strip()]
        
        job_numbers = self.parse_job_numbers(job_number_input)
        
        if not job_numbers:
            messagebox.showerror("Error", "Invalid job number format")
            return
        
        # Check duplicates
        allow_duplicates = self.settings.get('allow_duplicate_jobs', False)
        
        for job_num in job_numbers:
            is_duplicate, existing_path = self.check_duplicate_job_number(customer, job_num)
            
            if is_duplicate and not allow_duplicates:
                response = messagebox.askyesno(
                    "Duplicate",
                    f"Job '{job_num}' exists for '{customer}'.\n\n"
                    f"Location: {existing_path}\n\nContinue anyway?",
                    icon='warning'
                )
                if not response:
                    self.log_message(f"Cancelled - duplicate: {job_num}")
                    return
        
        self.log_message("=== Job Creation Started ===")
        self.log_message(f"ITAR: {'Yes' if is_itar else 'No'}")
        self.log_message(f"Customer: {customer}")
        self.log_message(f"Job(s): {', '.join(job_numbers)}")
        
        created_count = 0
        for job_num in job_numbers:
            success = self._create_single_job(
                customer=customer,
                job_number=job_num,
                description=description,
                drawings=drawings,
                is_itar=is_itar,
                files=self.job_files,
                log_to_ui=True
            )
            if success:
                created_count += 1
        
        summary = f"\n{created_count}/{len(job_numbers)} job(s) created!"
        self.log_message(summary)
        messagebox.showinfo("Success", summary)
        
        self.refresh_history()
        
        self.job_files = []
        self.job_files_listbox.delete(0, tk.END)
    
    def _create_single_job(self, customer: str, job_number: str, description: str,
                          drawings: List[str], is_itar: bool, files: List[str],
                          log_to_ui: bool = True) -> bool:
        try:
            blueprints_dir, customer_files_dir = self._get_directories(is_itar)
            
            if not blueprints_dir or not customer_files_dir:
                return False
            
            if drawings:
                job_dir_name = f"{job_number}_{description}_{'-'.join(drawings)}"
            else:
                job_dir_name = f"{job_number}_{description}"
            
            job_dir_name = re.sub(r'[<>:"/\\|?*]', '_', job_dir_name)
            
            job_path = Path(customer_files_dir) / customer / 'job documents' / job_dir_name
            job_path.mkdir(parents=True, exist_ok=True)
            
            if log_to_ui:
                self.log_message(f"Created: {job_path}")
            
            customer_blueprints = Path(blueprints_dir) / customer
            customer_blueprints.mkdir(parents=True, exist_ok=True)
            
            for file_path in files:
                file_name = os.path.basename(file_path)
                is_blueprint = self.is_blueprint_file(file_name)
                
                if is_blueprint:
                    blueprint_path = customer_blueprints / file_name
                    
                    if not blueprint_path.exists():
                        shutil.copy2(file_path, blueprint_path)
                    
                    dest_path = job_path / file_name
                    if not dest_path.exists():
                        self._create_link(blueprint_path, dest_path)
                else:
                    dest_path = job_path / file_name
                    if not dest_path.exists():
                        shutil.copy2(file_path, dest_path)
            
            if drawings:
                blueprint_extensions = self.settings.get('blueprint_extensions', ['.pdf', '.dwg', '.dxf'])
                
                for drawing in drawings:
                    if customer_blueprints.exists():
                        for ext in blueprint_extensions:
                            for blueprint_file in customer_blueprints.glob(f"*{drawing}*{ext}"):
                                dest_path = job_path / blueprint_file.name
                                if not dest_path.exists():
                                    self._create_link(blueprint_file, dest_path)
            
            self._add_to_history(customer, job_number, description, drawings, str(job_path))
            
            return True
            
        except Exception as e:
            if log_to_ui:
                self.log_message(f"Error creating job {job_number}: {e}", 'error')
            return False
    
    def _add_to_history(self, customer: str, job_number: str, description: str,
                       drawings: List[str], path: str) -> None:
        if 'customers' not in self.history:
            self.history['customers'] = {}
        
        if customer not in self.history['customers']:
            self.history['customers'][customer] = {'jobs': []}
        
        job_record = {
            'date': datetime.now().isoformat(),
            'customer': customer,
            'job_number': job_number,
            'description': description,
            'drawings': drawings,
            'path': path
        }
        
        if 'recent_jobs' not in self.history:
            self.history['recent_jobs'] = []
        
        self.history['recent_jobs'].insert(0, job_record)
        self.history['recent_jobs'] = self.history['recent_jobs'][:100]
        
        self.save_history()
        
    def clear_form(self) -> None:
        self.customer_var.set('')
        self.job_number_var.set('')
        self.description_var.set('')
        self.drawing_numbers_var.set('')
        self.itar_var.set(False)
        self.job_files = []
        self.job_files_listbox.delete(0, tk.END)
    
    def open_blueprints_folder(self) -> None:
        blueprints_dir = self.settings.get('blueprints_dir', '')
        if blueprints_dir and os.path.exists(blueprints_dir):
            self.open_folder(blueprints_dir)
        else:
            messagebox.showwarning("Warning", "Blueprints directory not configured")
    
    def open_customer_files_folder(self) -> None:
        customer_files_dir = self.settings.get('customer_files_dir', '')
        if customer_files_dir and os.path.exists(customer_files_dir):
            self.open_folder(customer_files_dir)
        else:
            messagebox.showwarning("Warning", "Customer files directory not configured")
    
    # Import
    def check_and_import(self) -> None:
        customer = self.import_customer_var.get().strip()
        
        if not customer:
            messagebox.showerror("Error", "Please select a customer")
            return
            
        if not self.import_files:
            messagebox.showerror("Error", "Please add files to import")
            return
            
        if not self.settings.get('blueprints_dir'):
            messagebox.showerror("Error", "Configure blueprints directory in Settings")
            return
            
        try:
            blueprints_dir = Path(self.settings['blueprints_dir']) / customer
            blueprints_dir.mkdir(parents=True, exist_ok=True)
            
            self.import_log.delete(1.0, tk.END)
            
            imported = 0
            skipped = 0
            errors = 0
            
            for file_path in self.import_files:
                file_name = os.path.basename(file_path)
                dest_path = blueprints_dir / file_name
                
                if dest_path.exists():
                    self.import_log_message(f"Exists: {file_name}")
                    skipped += 1
                else:
                    try:
                        shutil.copy2(file_path, dest_path)
                        self.import_log_message(f"Imported: {file_name}")
                        imported += 1
                    except Exception as e:
                        self.import_log_message(f"Error: {file_name} - {e}")
                        errors += 1
            
            summary = f"\nDone! Imported: {imported}, Skipped: {skipped}, Errors: {errors}"
            self.import_log_message(summary)
            
            messagebox.showinfo("Import Complete", summary)
            
            self.populate_customer_list()
            self.populate_import_customer_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
    
    # Search
    def perform_search(self) -> None:
        search_term = self.search_var.get().strip().lower()
        
        if not search_term:
            messagebox.showwarning("Search", "Enter a search term")
            return
        
        customer_files_dir = self.settings.get('customer_files_dir', '')
        if not customer_files_dir or not os.path.exists(customer_files_dir):
            messagebox.showerror("Error", "Customer files directory not configured")
            return
        
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        
        self.search_results = []
        
        self.search_progress.pack(pady=5)
        self.search_progress.start(10)
        self.search_count_label.config(text="Searching...", foreground='blue')
        self.root.update_idletasks()
        
        folders_scanned = 0
        search_mode = self.search_mode_var.get()
        
        try:
            for root, dirs, files in os.walk(customer_files_dir):
                folders_scanned += len(dirs)
                
                if folders_scanned % 50 == 0:
                    self.search_count_label.config(
                        text=f"Scanning... {folders_scanned} folders",
                        foreground='blue'
                    )
                    self.root.update_idletasks()
                
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    
                    rel_path = os.path.relpath(dir_path, customer_files_dir)
                    path_parts = rel_path.split(os.sep)
                    customer_name = path_parts[0] if path_parts else "Unknown"
                    
                    if search_mode == 'strict' and not dir_name[0].isdigit():
                        continue
                    
                    match = False
                    folder_lower = dir_name.lower()
                    
                    if self.search_customer_var.get() and search_term in customer_name.lower():
                        match = True
                    if self.search_job_var.get() and search_term in folder_lower:
                        match = True
                    if self.search_desc_var.get() and search_term in folder_lower:
                        match = True
                    if self.search_drawing_var.get() and search_term in folder_lower:
                        match = True
                    
                    if not any([self.search_customer_var.get(), self.search_job_var.get(),
                               self.search_desc_var.get(), self.search_drawing_var.get()]):
                        if search_term in folder_lower or search_term in customer_name.lower():
                            match = True
                    
                    if match:
                        parts = dir_name.replace('_', ' ').split()
                        job_number = parts[0] if parts else ""
                        description = ' '.join(parts[1:]) if len(parts) > 1 else dir_name
                        
                        drawings = []
                        for part in parts:
                            if '-' in part:
                                drawings.extend([d.strip() for d in part.split('-') if d.strip()])
                        
                        try:
                            mod_time = datetime.fromtimestamp(os.path.getmtime(dir_path))
                        except OSError:
                            mod_time = datetime.now()
                        
                        self.search_results.append({
                            'date': mod_time,
                            'customer': customer_name,
                            'job_number': job_number,
                            'description': description,
                            'drawings': drawings,
                            'path': dir_path
                        })
            
            self.search_results.sort(key=lambda x: x['date'], reverse=True)
            
            # Use stable IDs (bug fix for index mismatch)
            for idx, job in enumerate(self.search_results):
                date_str = job['date'].strftime("%Y-%m-%d %H:%M")
                self.search_tree.insert('', tk.END, iid=str(idx), values=(
                    date_str,
                    job['customer'],
                    job['job_number'],
                    job['description'],
                    ', '.join(job['drawings']) if job['drawings'] else ''
                ))
            
            self.search_progress.stop()
            self.search_progress.pack_forget()
            
            mode_text = "strict" if search_mode == 'strict' else "all"
            self.search_count_label.config(
                text=f"Found {len(self.search_results)} results ({mode_text} mode)",
                foreground='green' if self.search_results else 'gray'
            )
            
        except Exception as e:
            self.search_progress.stop()
            self.search_progress.pack_forget()
            self.search_count_label.config(text="Search error", foreground='red')
            messagebox.showerror("Search Error", f"Error: {e}")
    
    def clear_search(self) -> None:
        self.search_var.set('')
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)
        self.search_count_label.config(text="")
        self.search_results = []
    
    def open_selected_job(self) -> None:
        selection = self.search_tree.selection()
        if not selection:
            return
        
        try:
            idx = int(selection[0])
            if 0 <= idx < len(self.search_results):
                job_path = self.search_results[idx]['path']
                if os.path.exists(job_path):
                    self.open_folder(job_path)
                else:
                    messagebox.showwarning("Not Found", f"Folder not found:\n{job_path}")
        except (ValueError, IndexError):
            messagebox.showwarning("Error", "Unable to locate job folder")
    
    def open_selected_blueprints(self) -> None:
        selection = self.search_tree.selection()
        if not selection:
            return
        
        try:
            idx = int(selection[0])
            if 0 <= idx < len(self.search_results):
                customer = self.search_results[idx]['customer']
                blueprints_dir = self.settings.get('blueprints_dir', '')
                if blueprints_dir:
                    customer_bp = os.path.join(blueprints_dir, customer)
                    if os.path.exists(customer_bp):
                        self.open_folder(customer_bp)
                    else:
                        messagebox.showwarning("Not Found", f"Blueprints for {customer} not found")
        except (ValueError, IndexError):
            pass
    
    def copy_job_path(self) -> None:
        selection = self.search_tree.selection()
        if not selection:
            return
        
        try:
            idx = int(selection[0])
            if 0 <= idx < len(self.search_results):
                job_path = self.search_results[idx]['path']
                self.root.clipboard_clear()
                self.root.clipboard_append(job_path)
                messagebox.showinfo("Copied", "Path copied to clipboard")
        except (ValueError, IndexError):
            messagebox.showwarning("Error", "Unable to copy path")
    
    # History
    def refresh_history(self) -> None:
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        for job in self.history.get('recent_jobs', []):
            try:
                date = datetime.fromisoformat(job['date']).strftime("%Y-%m-%d %H:%M")
            except (ValueError, KeyError):
                date = "Unknown"
            
            self.history_tree.insert('', tk.END, values=(
                date,
                job.get('customer', ''),
                job.get('job_number', ''),
                job.get('description', ''),
                ', '.join(job.get('drawings', []))
            ))
            
    def clear_history(self) -> None:
        if messagebox.askyesno("Confirm", "Clear all history?"):
            self.history = {'customers': {}, 'recent_jobs': []}
            self.save_history()
            self.refresh_history()
    
    # Settings
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.root, self.settings)
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.settings = dialog.result
            self.save_settings()
            self.populate_customer_list()
            self.populate_import_customer_list()
            messagebox.showinfo("Settings", "Settings saved")
    
    # Help
    def show_user_guide(self) -> None:
        guide_window = tk.Toplevel(self.root)
        guide_window.title("JobDocs - User Guide")
        guide_window.geometry("700x500")
        
        text = tk.Text(guide_window, wrap=tk.WORD, font=('Arial', 10), padx=20, pady=20)
        scroll = ttk.Scrollbar(guide_window, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.pack(fill=tk.BOTH, expand=True)
        
        guide = """
JOBDOCS v2.0 USER GUIDE

== GETTING STARTED ==

1. Go to File → Settings
2. Configure directories:
   - Blueprints Directory: Central drawing storage
   - Customer Files Directory: Where job folders are created
3. Choose link type (Hard Link recommended)
4. Set blueprint file extensions

== CREATE JOB TAB ==

Enter job information:
- Customer Name (auto-completes)
- Job Number(s): single, comma-separated, or range (12345-12350)
- Description
- Drawing Numbers (optional)
- ITAR checkbox for controlled jobs

Drop files or click browse to add files:
- Blueprint files → saved to blueprints, linked to job
- Other files → copied to job folder

== BULK CREATE TAB (NEW) ==

Create multiple jobs at once:
1. Enter jobs in CSV format (one per line)
2. Format: customer, job_number, description, drawings...
3. Click Validate to check for errors
4. Click Create All Jobs

Example:
Acme Corp, 12345, Widget Assembly, DWG-001
Acme Corp, 12346, Gadget Housing, DWG-002

== SEARCH TAB ==

Find jobs by customer, job number, description, or drawing.

Search Modes:
- All Folders: Searches everything (slower, finds legacy files)
- Strict: Only numbered folders (faster, new files only)

Double-click or right-click results to open folders.

== IMPORT TAB ==

Import files directly to blueprints folder:
1. Select customer
2. Drop/browse files
3. Click Check & Import

== TIPS ==

- Use hard links to save disk space
- ITAR jobs use separate directories
- Autocomplete learns from history
- Check for duplicates before creating
"""
        
        text.insert('1.0', guide)
        text.config(state=tk.DISABLED)
        
        ttk.Button(guide_window, text="Close", command=guide_window.destroy).pack(pady=10)
    
    def show_about(self) -> None:
        about = """JobDocs

A tool for managing blueprint files and customer job directories.

Features:
• Single and bulk job creation
• Add files to existing jobs
• Blueprint file linking (hard links save disk space)
• File system search
• Import tools
• ITAR directory support
• History tracking

github.com/i-machine-things/file_tools"""
        
        messagebox.showinfo("About JobDocs", about)


def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = FileLinkManager(root)
    root.mainloop()


if __name__ == '__main__':
    main()
