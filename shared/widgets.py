"""
Shared custom widgets for JobDocs

Common UI widgets used across multiple modules.
"""

from PyQt6.QtWidgets import (
    QFrame, QDialog, QVBoxLayout, QScrollArea, QLabel, QDialogButtonBox,
    QPushButton, QFileDialog, QLineEdit, QListWidget, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from pathlib import Path
import os


class DropZone(QFrame):
    """A widget that accepts file drops"""
    files_dropped = pyqtSignal(list)

    def __init__(self, label: str = "Drop files here", parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(60)
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

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
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
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        print(f"[DropZone] dropEvent: {len(files)} files dropped", flush=True)
        for f in files:
            print(f"  - {f}", flush=True)
        self.files_dropped.emit(files)

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
    """Dialog for searching and linking existing drawings and inspection reports by drawing number"""

    def __init__(self, parent, app_context):
        super().__init__(parent)
        self.app_context = app_context
        self.selected_files = []

        self.setWindowTitle("Link Drawings & Inspection Reports")
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
        """Search for drawings and inspection reports matching the drawing number"""
        search_term = self.search_input.text().strip().lower()
        self.results_tree.clear()

        if len(search_term) < 2:
            self.status_label.setText("Enter at least 2 characters...")
            return

        # Get directories to search
        blueprints_dir = self.app_context.get_setting('blueprints_dir', '')
        itar_blueprints_dir = self.app_context.get_setting('itar_blueprints_dir', '')
        inspection_dir = self.app_context.get_setting('inspection_report_dir', '')

        results = []

        # Search blueprints directories
        for base_dir, location_prefix in [
            (blueprints_dir, 'Blueprints'),
            (itar_blueprints_dir, 'ITAR Blueprints'),
            (inspection_dir, 'Inspection Reports')
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
