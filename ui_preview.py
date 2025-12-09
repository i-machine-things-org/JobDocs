"""
JobDocs UI Preview
Run this file to preview and test UI layouts without the full application logic
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox, QTabWidget,
    QGroupBox, QListWidget, QSplitter, QTreeWidget, QTableWidget,
    QPlainTextEdit, QRadioButton, QButtonGroup, QHeaderView,
    QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


class DropZone(QFrame):
    """Simple drop zone widget for preview"""
    files_dropped = pyqtSignal(list)

    def __init__(self, text="Drop files here"):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # Visual styling
        self.setStyleSheet("""
            DropZone {
                background-color: #f0f0f0;
                border: 2px dashed #999;
                border-radius: 5px;
            }
            DropZone:hover {
                background-color: #e8e8e8;
            }
        """)


class UIPreviewWindow(QMainWindow):
    """Preview window for JobDocs UI"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JobDocs UI Preview")
        self.setMinimumSize(1000, 700)

        # Initialize data storage (dummy)
        self.quote_files = []
        self.job_files = []
        self.add_files = []
        self.import_files = []

        # Create main widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Create tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Add all tabs
        self.tabs.addTab(self.create_quote_tab(), "Create Quote")
        self.tabs.addTab(self.create_job_tab(), "Create Job")
        self.tabs.addTab(self.create_add_to_job_tab(), "Add to Job")
        self.tabs.addTab(self.create_import_blueprints_tab(), "Import Blueprints")
        self.tabs.addTab(self.create_search_tab(), "Search")
        self.tabs.addTab(self.create_bulk_jobs_tab(), "Bulk Jobs")
        self.tabs.addTab(self.create_history_tab(), "History")

        # Add info label at bottom
        info = QLabel("UI Preview Mode - No functionality, visual layout only")
        info.setStyleSheet("background-color: #ffffcc; padding: 5px;")
        layout.addWidget(info)

    # ==================== Dummy Methods (for UI connections) ====================

    def add_quote_files(self, files): pass
    def remove_quote_file(self): pass
    def search_for_quote_copy(self): pass
    def copy_quote_to_form(self): pass
    def link_files_from_quote(self): pass
    def create_quote(self): pass
    def convert_current_quote_to_job(self): pass
    def clear_quote_form(self): pass

    def handle_job_files(self, files): pass
    def remove_job_file(self): pass
    def search_for_job_copy(self): pass
    def copy_job_to_form(self): pass
    def link_files_from_job(self): pass
    def create_job(self): pass
    def clear_job_form(self): pass
    def open_blueprints_folder(self): pass
    def open_customer_files_folder(self): pass

    def refresh_job_tree(self): pass
    def on_job_selected(self): pass
    def handle_add_files_dropped(self, files): pass
    def browse_add_files(self): pass
    def clear_add_files(self): pass
    def link_files_to_job(self): pass

    def handle_import_files_dropped(self, files): pass
    def browse_import_files(self): pass
    def clear_import_files(self): pass
    def import_blueprints(self): pass

    def perform_search(self): pass
    def open_search_result(self): pass
    def export_search_results(self): pass

    def create_bulk_jobs(self): pass

    def load_history(self): pass
    def clear_history(self): pass

    # ==================== UI Creation Methods ====================

    def create_quote_tab(self) -> QWidget:
        """Create the Quote tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Quote info group
        info_group = QGroupBox("Quote Information")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(5, 5, 5, 5)

        # Customer
        info_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.quote_customer_combo = QComboBox()
        self.quote_customer_combo.setEditable(True)
        self.quote_customer_combo.setMinimumWidth(250)
        info_layout.addWidget(self.quote_customer_combo, 0, 1)

        # Quote number
        info_layout.addWidget(QLabel("Quote #:"), 1, 0)
        self.quote_number_edit = QLineEdit()
        self.quote_number_edit.setPlaceholderText("e.g., Q12345 or Q12345-Q12350")
        info_layout.addWidget(self.quote_number_edit, 1, 1)

        # Description
        info_layout.addWidget(QLabel("Description:"), 2, 0)
        self.quote_description_edit = QLineEdit()
        info_layout.addWidget(self.quote_description_edit, 2, 1)

        # Drawings
        info_layout.addWidget(QLabel("Drawings:"), 3, 0)
        self.quote_drawings_edit = QLineEdit()
        self.quote_drawings_edit.setPlaceholderText("comma-separated")
        info_layout.addWidget(self.quote_drawings_edit, 3, 1)

        # ITAR
        self.quote_itar_check = QCheckBox("ITAR Quote (uses separate directories)")
        info_layout.addWidget(self.quote_itar_check, 4, 1)

        layout.addWidget(info_group)

        # Splitter for Files and Search sections
        files_search_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Files group (left)
        files_group = QGroupBox("Quote Files (Optional)")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(3)
        files_layout.setContentsMargins(5, 5, 5, 5)

        files_layout.addWidget(QLabel("Blueprints → blueprints folder, others → quote folder"))

        self.quote_drop_zone = DropZone("Drop files")
        self.quote_drop_zone.files_dropped.connect(self.add_quote_files)
        self.quote_drop_zone.setMinimumHeight(60)
        files_layout.addWidget(self.quote_drop_zone)

        self.quote_files_list = QListWidget()
        self.quote_files_list.setMaximumHeight(70)
        files_layout.addWidget(self.quote_files_list)

        files_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_quote_file)
        files_btn_layout.addWidget(remove_btn)
        files_btn_layout.addStretch()
        files_layout.addLayout(files_btn_layout)

        files_search_splitter.addWidget(files_group)

        # Search and copy section (right)
        search_group = QGroupBox("Search & Copy")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(3)
        search_layout.setContentsMargins(5, 5, 5, 5)

        search_layout.addWidget(QLabel("Search existing jobs/quotes to copy info:"))

        self.quote_search_input = QLineEdit()
        self.quote_search_input.setPlaceholderText("Search by customer, job#, description...")
        self.quote_search_input.textChanged.connect(self.search_for_quote_copy)
        search_layout.addWidget(self.quote_search_input)

        self.quote_search_results = QListWidget()
        self.quote_search_results.setMaximumHeight(70)
        self.quote_search_results.itemDoubleClicked.connect(self.copy_quote_to_form)
        search_layout.addWidget(self.quote_search_results)

        search_btn_layout = QHBoxLayout()
        copy_info_btn = QPushButton("Copy Info")
        copy_info_btn.setToolTip("Copy selected job/quote info to form")
        copy_info_btn.clicked.connect(self.copy_quote_to_form)
        search_btn_layout.addWidget(copy_info_btn)

        link_files_btn = QPushButton("Link Files")
        link_files_btn.setToolTip("Link files from selected job/quote")
        link_files_btn.clicked.connect(self.link_files_from_quote)
        search_btn_layout.addWidget(link_files_btn)

        search_btn_layout.addStretch()
        search_layout.addLayout(search_btn_layout)

        files_search_splitter.addWidget(search_group)
        files_search_splitter.setSizes([450, 450])

        layout.addWidget(files_search_splitter)

        # Action buttons
        btn_layout = QHBoxLayout()

        create_btn = QPushButton("Create Quote && Link Files")
        create_btn.clicked.connect(self.create_quote)
        btn_layout.addWidget(create_btn)

        convert_btn = QPushButton("Convert to Job")
        convert_btn.setToolTip("Copy current quote info to Create Job tab")
        convert_btn.clicked.connect(self.convert_current_quote_to_job)
        btn_layout.addWidget(convert_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_quote_form)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def create_job_tab(self) -> QWidget:
        """Create the Job tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Job info group
        info_group = QGroupBox("Job Information")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(5, 5, 5, 5)

        # Customer
        info_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setEditable(True)
        self.customer_combo.setMinimumWidth(250)
        info_layout.addWidget(self.customer_combo, 0, 1)

        # Job number
        info_layout.addWidget(QLabel("Job #:"), 1, 0)
        self.job_number_edit = QLineEdit()
        self.job_number_edit.setPlaceholderText("e.g., 12345 or 12345-12350")
        info_layout.addWidget(self.job_number_edit, 1, 1)
        self.job_status_label = QLabel("")
        info_layout.addWidget(self.job_status_label, 1, 2)

        # Description
        info_layout.addWidget(QLabel("Description:"), 2, 0)
        self.description_edit = QLineEdit()
        info_layout.addWidget(self.description_edit, 2, 1)

        # Drawings
        info_layout.addWidget(QLabel("Drawings:"), 3, 0)
        self.drawings_edit = QLineEdit()
        self.drawings_edit.setPlaceholderText("comma-separated")
        info_layout.addWidget(self.drawings_edit, 3, 1)

        # ITAR
        self.itar_check = QCheckBox("ITAR Job (uses separate directories)")
        info_layout.addWidget(self.itar_check, 4, 1)

        layout.addWidget(info_group)

        # Splitter for Files and Search sections
        files_search_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Files group (left)
        files_group = QGroupBox("Job Files (Optional)")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(3)
        files_layout.setContentsMargins(5, 5, 5, 5)

        files_layout.addWidget(QLabel("Blueprints → blueprints folder, others → job folder"))

        self.job_drop_zone = DropZone("Drop files")
        self.job_drop_zone.files_dropped.connect(self.handle_job_files)
        self.job_drop_zone.setMinimumHeight(60)
        files_layout.addWidget(self.job_drop_zone)

        self.job_files_list = QListWidget()
        self.job_files_list.setMaximumHeight(70)
        files_layout.addWidget(self.job_files_list)

        files_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_job_file)
        files_btn_layout.addWidget(remove_btn)
        files_btn_layout.addStretch()
        files_layout.addLayout(files_btn_layout)

        files_search_splitter.addWidget(files_group)

        # Search and copy section (right)
        search_group = QGroupBox("Search & Copy")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(3)
        search_layout.setContentsMargins(5, 5, 5, 5)

        search_layout.addWidget(QLabel("Search existing jobs/quotes to copy info:"))

        self.job_search_input = QLineEdit()
        self.job_search_input.setPlaceholderText("Search by customer, job#, description...")
        self.job_search_input.textChanged.connect(self.search_for_job_copy)
        search_layout.addWidget(self.job_search_input)

        self.job_search_results = QListWidget()
        self.job_search_results.setMaximumHeight(70)
        self.job_search_results.itemDoubleClicked.connect(self.copy_job_to_form)
        search_layout.addWidget(self.job_search_results)

        search_btn_layout = QHBoxLayout()
        copy_info_btn = QPushButton("Copy Info")
        copy_info_btn.setToolTip("Copy selected job/quote info to form")
        copy_info_btn.clicked.connect(self.copy_job_to_form)
        search_btn_layout.addWidget(copy_info_btn)

        link_files_btn = QPushButton("Link Files")
        link_files_btn.setToolTip("Link files from selected job/quote")
        link_files_btn.clicked.connect(self.link_files_from_job)
        search_btn_layout.addWidget(link_files_btn)

        search_btn_layout.addStretch()
        search_layout.addLayout(search_btn_layout)

        files_search_splitter.addWidget(search_group)
        files_search_splitter.setSizes([450, 450])

        layout.addWidget(files_search_splitter)

        # Action buttons
        btn_layout = QHBoxLayout()

        create_btn = QPushButton("Create Job && Link Files")
        create_btn.clicked.connect(self.create_job)
        btn_layout.addWidget(create_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_job_form)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        open_bp_btn = QPushButton("Open Blueprints")
        open_bp_btn.clicked.connect(self.open_blueprints_folder)
        btn_layout.addWidget(open_bp_btn)

        open_cf_btn = QPushButton("Open Customer Files")
        open_cf_btn.clicked.connect(self.open_customer_files_folder)
        btn_layout.addWidget(open_cf_btn)

        layout.addLayout(btn_layout)

        return widget

    def create_add_to_job_tab(self) -> QWidget:
        """Create the Add to Job tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        layout.addWidget(QLabel("Add documents to existing job"))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left - Browser
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 3, 0)
        left_layout.setSpacing(3)

        browser_group = QGroupBox("Select Job")
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.setSpacing(3)
        browser_layout.setContentsMargins(5, 5, 5, 5)

        self.add_customer_combo = QComboBox()
        self.add_customer_combo.currentTextChanged.connect(self.refresh_job_tree)
        browser_layout.addWidget(QLabel("Customer:"))
        browser_layout.addWidget(self.add_customer_combo)

        self.add_itar_check = QCheckBox("Show ITAR jobs only")
        self.add_itar_check.stateChanged.connect(self.refresh_job_tree)
        browser_layout.addWidget(self.add_itar_check)

        self.job_tree = QTreeWidget()
        self.job_tree.setHeaderLabels(["Job Folders"])
        self.job_tree.itemSelectionChanged.connect(self.on_job_selected)
        browser_layout.addWidget(self.job_tree)

        left_layout.addWidget(browser_group, 1)
        splitter.addWidget(left_widget)

        # Right - Add files
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(3, 0, 0, 0)
        right_layout.setSpacing(3)

        add_group = QGroupBox("Add Files to Selected Job")
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(3)
        add_layout.setContentsMargins(5, 5, 5, 5)

        self.selected_job_label = QLabel("No job selected")
        self.selected_job_label.setStyleSheet("font-weight: bold;")
        add_layout.addWidget(self.selected_job_label)

        self.add_drop_zone = DropZone("Drop files here")
        self.add_drop_zone.files_dropped.connect(self.handle_add_files_dropped)
        self.add_drop_zone.setMinimumHeight(100)
        add_layout.addWidget(self.add_drop_zone)

        self.add_files_list = QListWidget()
        self.add_files_list.setMaximumHeight(100)
        add_layout.addWidget(self.add_files_list)

        add_btn_layout = QHBoxLayout()

        browse_add_btn = QPushButton("Browse Files...")
        browse_add_btn.clicked.connect(self.browse_add_files)
        add_btn_layout.addWidget(browse_add_btn)

        clear_add_btn = QPushButton("Clear Files")
        clear_add_btn.clicked.connect(self.clear_add_files)
        add_btn_layout.addWidget(clear_add_btn)

        add_btn_layout.addStretch()
        add_layout.addLayout(add_btn_layout)

        link_add_btn = QPushButton("Link Files to Job")
        link_add_btn.clicked.connect(self.link_files_to_job)
        add_layout.addWidget(link_add_btn)

        right_layout.addWidget(add_group, 1)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        return widget

    def create_import_blueprints_tab(self) -> QWidget:
        """Create the Import Blueprints tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Customer selection
        select_group = QGroupBox("Customer")
        select_layout = QVBoxLayout(select_group)
        select_layout.setSpacing(3)
        select_layout.setContentsMargins(5, 5, 5, 5)

        self.import_customer_combo = QComboBox()
        self.import_customer_combo.setEditable(True)
        select_layout.addWidget(QLabel("Select or type customer name:"))
        select_layout.addWidget(self.import_customer_combo)

        self.import_itar_check = QCheckBox("ITAR (uses ITAR blueprints directory)")
        select_layout.addWidget(self.import_itar_check)

        layout.addWidget(select_group)

        # Files section
        files_group = QGroupBox("Blueprint Files")
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(3)
        files_layout.setContentsMargins(5, 5, 5, 5)

        self.import_drop_zone = DropZone("Drop blueprint files here")
        self.import_drop_zone.files_dropped.connect(self.handle_import_files_dropped)
        self.import_drop_zone.setMinimumHeight(100)
        files_layout.addWidget(self.import_drop_zone)

        self.import_files_list = QListWidget()
        files_layout.addWidget(self.import_files_list)

        import_btn_layout = QHBoxLayout()

        browse_import_btn = QPushButton("Browse Files...")
        browse_import_btn.clicked.connect(self.browse_import_files)
        import_btn_layout.addWidget(browse_import_btn)

        clear_import_btn = QPushButton("Clear Files")
        clear_import_btn.clicked.connect(self.clear_import_files)
        import_btn_layout.addWidget(clear_import_btn)

        import_btn_layout.addStretch()
        files_layout.addLayout(import_btn_layout)

        layout.addWidget(files_group)

        # Import button
        import_bp_btn = QPushButton("Import Blueprints")
        import_bp_btn.clicked.connect(self.import_blueprints)
        layout.addWidget(import_bp_btn)

        layout.addStretch()

        return widget

    def create_search_tab(self) -> QWidget:
        """Create the Search tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Search mode
        mode_group = QGroupBox("Search Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(3)
        mode_layout.setContentsMargins(5, 5, 5, 5)

        self.search_mode_group = QButtonGroup()

        self.strict_radio = QRadioButton("Strict (structured folder names)")
        self.strict_radio.setChecked(True)
        self.search_mode_group.addButton(self.strict_radio)
        mode_layout.addWidget(self.strict_radio)

        self.legacy_radio = QRadioButton("Legacy (search all customer files)")
        self.search_mode_group.addButton(self.legacy_radio)
        mode_layout.addWidget(self.legacy_radio)

        self.search_blueprints_check = QCheckBox("Also search blueprints directories (legacy mode only)")
        mode_layout.addWidget(self.search_blueprints_check)

        layout.addWidget(mode_group)

        # Filters
        filter_group = QGroupBox("Filters")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setSpacing(3)
        filter_layout.setContentsMargins(5, 5, 5, 5)

        filter_layout.addWidget(QLabel("Customer:"), 0, 0)
        self.search_customer_combo = QComboBox()
        self.search_customer_combo.addItem("All")
        self.search_customer_combo.setEditable(True)
        filter_layout.addWidget(self.search_customer_combo, 0, 1)

        filter_layout.addWidget(QLabel("Job #:"), 1, 0)
        self.search_job_edit = QLineEdit()
        filter_layout.addWidget(self.search_job_edit, 1, 1)

        filter_layout.addWidget(QLabel("Description:"), 2, 0)
        self.search_desc_edit = QLineEdit()
        filter_layout.addWidget(self.search_desc_edit, 2, 1)

        filter_layout.addWidget(QLabel("Drawing:"), 3, 0)
        self.search_drawing_edit = QLineEdit()
        filter_layout.addWidget(self.search_drawing_edit, 3, 1)

        self.search_itar_check = QCheckBox("ITAR only")
        filter_layout.addWidget(self.search_itar_check, 4, 1)

        layout.addWidget(filter_group)

        # Search button
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        layout.addWidget(search_btn)

        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(3)
        results_layout.setContentsMargins(5, 5, 5, 5)

        self.search_results_table = QTableWidget()
        self.search_results_table.setColumnCount(5)
        self.search_results_table.setHorizontalHeaderLabels(["Customer", "Job #", "Description", "Drawing", "Path"])
        self.search_results_table.horizontalHeader().setStretchLastSection(True)
        self.search_results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_results_table.itemDoubleClicked.connect(self.open_search_result)
        results_layout.addWidget(self.search_results_table)

        result_btn_layout = QHBoxLayout()

        open_result_btn = QPushButton("Open Folder")
        open_result_btn.clicked.connect(self.open_search_result)
        result_btn_layout.addWidget(open_result_btn)

        export_btn = QPushButton("Export Results")
        export_btn.clicked.connect(self.export_search_results)
        result_btn_layout.addWidget(export_btn)

        result_btn_layout.addStretch()
        results_layout.addLayout(result_btn_layout)

        layout.addWidget(results_group)

        return widget

    def create_bulk_jobs_tab(self) -> QWidget:
        """Create the Bulk Jobs tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        info_label = QLabel("Paste CSV data (Customer, Job#, Description, Drawings)")
        layout.addWidget(info_label)

        self.bulk_text = QPlainTextEdit()
        self.bulk_text.setPlaceholderText("CustomerName,12345,Job Description,DWG-001\nCustomerName,12346,Another Job,DWG-002")
        layout.addWidget(self.bulk_text)

        self.bulk_itar_check = QCheckBox("ITAR jobs (uses separate directories)")
        layout.addWidget(self.bulk_itar_check)

        btn_layout = QHBoxLayout()

        create_bulk_btn = QPushButton("Create Jobs")
        create_bulk_btn.clicked.connect(self.create_bulk_jobs)
        btn_layout.addWidget(create_bulk_btn)

        clear_bulk_btn = QPushButton("Clear")
        clear_bulk_btn.clicked.connect(self.bulk_text.clear)
        btn_layout.addWidget(clear_bulk_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget

    def create_history_tab(self) -> QWidget:
        """Create the History tab UI"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Action", "Details", "Status"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.history_table)

        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_history)
        btn_layout.addWidget(refresh_btn)

        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_history)
        btn_layout.addWidget(clear_history_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return widget


def main():
    app = QApplication(sys.argv)
    window = UIPreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
