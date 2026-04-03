"""
OOBE (Out-Of-Box Experience) Wizard for JobDocs

First-time setup wizard to configure essential settings.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QFileDialog, QMessageBox, QStackedWidget,
    QWidget, QRadioButton, QButtonGroup, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt


class OOBEWizard(QDialog):
    """
    First-time setup wizard for JobDocs.

    Guides users through:
    1. Welcome screen
    2. Directory configuration
    3. Link type selection
    4. Network sharing setup (optional)
    5. User authentication setup (optional)
    6. Completion
    """

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.settings = app_context.settings.copy()

        self.setWindowTitle("JobDocs First-Time Setup")
        self.setModal(True)
        self.setMinimumSize(700, 500)
        self.setMaximumHeight(700)  # Prevent window from exceeding 700px

        self.current_page = 0
        self.pages = []

        self.setup_ui()

    def setup_ui(self):
        """Setup the wizard UI"""
        from PyQt6.QtWidgets import QScrollArea, QFrame

        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.title_label)

        # Scroll area for pages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Stacked widget for pages
        self.stack = QStackedWidget()

        # Create pages
        self.pages = [
            self._create_welcome_page(),
            self._create_directories_page(),
            self._create_link_type_page(),
            self._create_network_sharing_page(),
            self._create_user_auth_page(),
            self._create_completion_page()
        ]

        for page in self.pages:
            self.stack.addWidget(page)

        scroll.setWidget(self.stack)
        layout.addWidget(scroll)

        # Navigation buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.back_button = QPushButton("< Back")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setEnabled(False)
        button_layout.addWidget(self.back_button)

        self.next_button = QPushButton("Next >")
        self.next_button.clicked.connect(self.go_next)
        button_layout.addWidget(self.next_button)

        self.finish_button = QPushButton("Finish")
        self.finish_button.clicked.connect(self.finish)
        self.finish_button.setVisible(False)
        button_layout.addWidget(self.finish_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Show first page
        self.update_page()

    def _create_welcome_page(self) -> QWidget:
        """Create welcome page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Icon/Welcome
        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 64px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        welcome = QLabel(
            "<h2 style='text-align: center;'>Welcome to JobDocs!</h2>"
            "<p style='text-align: center; color: #666;'>Let's get your system set up in just a few steps</p>"
        )
        welcome.setWordWrap(True)
        welcome.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(welcome)

        # What we'll do
        info_box = QGroupBox("What We'll Set Up")
        info_layout = QVBoxLayout(info_box)

        steps = QLabel(
            "<p>This wizard will walk you through:</p>"
            "<ol style='line-height: 1.8;'>"
            "<li><b>Folder Locations</b> - Where to store blueprints and customer files</li>"
            "<li><b>File Linking</b> - How to save disk space when organizing files</li>"
            "<li><b>Team Sharing</b> - Share settings across your team (optional)</li>"
            "<li><b>User Accounts</b> - Track who's using JobDocs (optional)</li>"
            "</ol>"
        )
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(steps)

        layout.addWidget(info_box)

        # Time estimate
        time_note = QLabel("⏱️ This should take about 2-3 minutes")
        time_note.setStyleSheet("color: #666; font-style: italic; text-align: center;")
        time_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(time_note)

        # Re-run note
        rerun_note = QLabel(
            "💡 Tip: You can re-run this wizard anytime from the Setup tab"
        )
        rerun_note.setStyleSheet("color: #0078d4; font-size: 11px; margin-top: 10px;")
        rerun_note.setWordWrap(True)
        rerun_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(rerun_note)

        layout.addStretch()

        return widget

    def _create_directories_page(self) -> QWidget:
        """Create directories configuration page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        intro = QLabel(
            "<b>Choose Folder Locations</b><br>"
            "<span style='color: #666;'>Tell JobDocs where to store your files</span>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        # Auto-setup option
        auto_setup_box = QGroupBox("🚀 Quick Setup")
        auto_setup_layout = QVBoxLayout(auto_setup_box)
        auto_setup_box.setStyleSheet("QGroupBox { border: 2px solid #28a745; border-radius: 8px; padding: 10px; }")

        auto_desc = QLabel(
            "New to JobDocs? Select a root folder on your server and we'll automatically create "
            "standard subdirectories:\n"
            "  • blueprints/\n"
            "  • customer files/"
        )
        auto_desc.setWordWrap(True)
        auto_desc.setStyleSheet("color: #444; font-size: 12px; margin-bottom: 10px;")
        auto_setup_layout.addWidget(auto_desc)

        auto_btn_layout = QHBoxLayout()
        auto_btn = QPushButton("🔍 Select Root Folder & Auto-Setup")
        auto_btn.setStyleSheet(
            "QPushButton { padding: 10px; background-color: #28a745; color: white; "
            "font-weight: bold; border-radius: 5px; }"
            "QPushButton:hover { background-color: #218838; }"
        )
        auto_btn.clicked.connect(self._auto_setup_directories)
        auto_btn_layout.addWidget(auto_btn)
        auto_setup_layout.addLayout(auto_btn_layout)

        layout.addWidget(auto_setup_box)

        # Warning if already configured
        existing_bp = self.app_context.settings.get('blueprints_dir', '')
        existing_cf = self.app_context.settings.get('customer_files_dir', '')

        if existing_bp and existing_cf:
            warning_box = QGroupBox("⚠️ Important")
            warning_layout = QVBoxLayout(warning_box)
            warning_box.setStyleSheet("QGroupBox { border: 2px solid #ffc107; border-radius: 8px; padding: 10px; }")

            warning_text = QLabel(
                "These folder locations are already set. Only change them if you moved your files to a new location.\n\n"
                f"Current Blueprints: {existing_bp}\n"
                f"Current Customer Files: {existing_cf}"
            )
            warning_text.setWordWrap(True)
            warning_text.setStyleSheet("color: #444; font-size: 12px;")
            warning_layout.addWidget(warning_text)

            layout.addWidget(warning_box)

        # Blueprints directory
        bp_group = QGroupBox("📐 Blueprint Files Folder")
        bp_layout = QVBoxLayout(bp_group)

        bp_desc = QLabel(
            "This is where JobDocs will keep all your blueprint files (drawings, PDFs, DWG files, etc.)\n"
            "Think of it as your central library of drawings."
        )
        bp_desc.setWordWrap(True)
        bp_desc.setStyleSheet("color: #666; margin-bottom: 10px;")
        bp_layout.addWidget(bp_desc)

        bp_input_layout = QHBoxLayout()
        self.bp_dir_edit = QLineEdit(self.settings.get('blueprints_dir', ''))
        self.bp_dir_edit.setPlaceholderText("Click Browse to select a folder...")
        self.bp_dir_edit.setStyleSheet("padding: 8px;")
        bp_input_layout.addWidget(self.bp_dir_edit)

        bp_browse_btn = QPushButton("Browse...")
        bp_browse_btn.setStyleSheet("padding: 8px; min-width: 80px;")
        bp_browse_btn.clicked.connect(lambda: self._browse_directory(self.bp_dir_edit))
        bp_input_layout.addWidget(bp_browse_btn)

        bp_layout.addLayout(bp_input_layout)
        layout.addWidget(bp_group)

        # Customer files directory
        cf_group = QGroupBox("👥 Customer Job Folders")
        cf_layout = QVBoxLayout(cf_group)

        cf_desc = QLabel(
            "This is where JobDocs will create folders for each customer and their jobs.\n"
            "Each job will get its own folder with the files it needs."
        )
        cf_desc.setWordWrap(True)
        cf_desc.setStyleSheet("color: #666; margin-bottom: 10px;")
        cf_layout.addWidget(cf_desc)

        cf_input_layout = QHBoxLayout()
        self.cf_dir_edit = QLineEdit(self.settings.get('customer_files_dir', ''))
        self.cf_dir_edit.setPlaceholderText("Click Browse to select a folder...")
        self.cf_dir_edit.setStyleSheet("padding: 8px;")
        cf_input_layout.addWidget(self.cf_dir_edit)

        cf_browse_btn = QPushButton("Browse...")
        cf_browse_btn.setStyleSheet("padding: 8px; min-width: 80px;")
        cf_browse_btn.clicked.connect(lambda: self._browse_directory(self.cf_dir_edit))
        cf_input_layout.addWidget(cf_browse_btn)

        cf_layout.addLayout(cf_input_layout)
        layout.addWidget(cf_group)

        # Help text
        help_note = QLabel(
            "💡 Tip: These folders can be on a network drive if you want to share files with your team"
        )
        help_note.setStyleSheet("color: #0078d4; font-size: 11px; font-style: italic; margin-top: 5px;")
        help_note.setWordWrap(True)
        layout.addWidget(help_note)

        layout.addStretch()

        return widget

    def _create_link_type_page(self) -> QWidget:
        """Create link type selection page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        intro = QLabel(
            "<b>How Should Files Be Organized?</b><br>"
            "<span style='color: #666;'>Choose how JobDocs handles files when creating job folders</span>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        explanation = QLabel(
            "When you create a job, JobDocs puts the blueprint files in the job folder. "
            "You can choose whether to save disk space by linking files, or make complete copies."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #444; background-color: #f0f8ff; padding: 10px; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(explanation)

        self.link_type_group = QButtonGroup()

        # Hard link (recommended) - with visual styling
        hard_option = QGroupBox()
        hard_option.setStyleSheet("QGroupBox { border: 2px solid #0078d4; border-radius: 8px; padding: 10px; margin: 5px; }")
        hard_layout = QVBoxLayout(hard_option)

        hard_radio = QRadioButton("✓ Smart Linking (Recommended)")
        hard_radio.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.link_type_group.addButton(hard_radio, 0)
        hard_layout.addWidget(hard_radio)

        hard_desc = QLabel(
            "Saves disk space by having both locations share the same file.\n\n"
            "✓ Best choice for most users\n"
            "✓ Saves disk space (one file appears in two places)\n"
            "✓ Changes in one location show up in the other\n"
            "⚠ Both folders must be on the same drive"
        )
        hard_desc.setWordWrap(True)
        hard_desc.setStyleSheet("color: #444; margin-left: 20px; margin-top: 5px; line-height: 1.5;")
        hard_layout.addWidget(hard_desc)

        layout.addWidget(hard_option)

        # Copy - simpler option
        copy_option = QGroupBox()
        copy_option.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 8px; padding: 10px; margin: 5px; }")
        copy_layout = QVBoxLayout(copy_option)

        copy_radio = QRadioButton("Make Complete Copies")
        copy_radio.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.link_type_group.addButton(copy_radio, 2)
        copy_layout.addWidget(copy_radio)

        copy_desc = QLabel(
            "Creates a separate copy of each file.\n\n"
            "✓ Works across different drives\n"
            "✓ Files are completely independent\n"
            "⚠ Uses more disk space (files are duplicated)"
        )
        copy_desc.setWordWrap(True)
        copy_desc.setStyleSheet("color: #444; margin-left: 20px; margin-top: 5px; line-height: 1.5;")
        copy_layout.addWidget(copy_desc)

        layout.addWidget(copy_option)

        # Symbolic link - advanced option (collapsed by default)
        symbolic_option = QGroupBox()
        symbolic_option.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 8px; padding: 10px; margin: 5px; }")
        symbolic_layout = QVBoxLayout(symbolic_option)

        symbolic_radio = QRadioButton("Shortcuts (Advanced)")
        symbolic_radio.setStyleSheet("font-size: 13px;")
        self.link_type_group.addButton(symbolic_radio, 1)
        symbolic_layout.addWidget(symbolic_radio)

        symbolic_desc = QLabel(
            "Creates shortcuts/references to the original files.\n\n"
            "✓ Can work across different drives\n"
            "⚠ May require administrator rights on Windows\n"
            "⚠ If the original file is deleted, the shortcut breaks"
        )
        symbolic_desc.setWordWrap(True)
        symbolic_desc.setStyleSheet("color: #444; margin-left: 20px; margin-top: 5px; line-height: 1.5;")
        symbolic_layout.addWidget(symbolic_desc)

        layout.addWidget(symbolic_option)

        # Help text
        help_note = QLabel(
            "💡 Not sure? Choose 'Smart Linking' - it's the best option for most people"
        )
        help_note.setStyleSheet("color: #0078d4; font-size: 11px; font-style: italic; margin-top: 10px;")
        help_note.setWordWrap(True)
        layout.addWidget(help_note)

        # Set current selection
        link_type = self.settings.get('link_type', 'hard')
        if link_type == 'hard':
            hard_radio.setChecked(True)
        elif link_type == 'symbolic':
            symbolic_radio.setChecked(True)
        else:
            copy_radio.setChecked(True)

        layout.addStretch()

        return widget

    def _create_network_sharing_page(self) -> QWidget:
        """Create network sharing configuration page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        intro = QLabel(
            "<b>Team Sharing (Optional)</b><br>"
            "<span style='color: #666;'>Share settings and job history across your team</span>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        explanation = QLabel(
            "If multiple people use JobDocs, you can share settings and job history across the team. "
            "Everyone will see the same configuration and job list."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #444; background-color: #f0f8ff; padding: 10px; border-radius: 5px;")
        layout.addWidget(explanation)

        self.enable_network_check = QCheckBox("✓ Enable team sharing")
        self.enable_network_check.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.enable_network_check.setChecked(self.settings.get('network_shared_enabled', False))
        self.enable_network_check.toggled.connect(self._toggle_network_fields)
        layout.addWidget(self.enable_network_check)

        # Network paths
        network_group = QGroupBox("Shared File Locations")
        network_layout = QVBoxLayout(network_group)

        # Settings file
        settings_label = QLabel("Settings File (where team settings are stored):")
        settings_label.setWordWrap(True)
        network_layout.addWidget(settings_label)

        settings_input_layout = QHBoxLayout()
        self.network_settings_edit = QLineEdit(self.settings.get('network_settings_path', ''))
        self.network_settings_edit.setPlaceholderText(r"Example: \\server\shared\jobdocs-settings.json")
        self.network_settings_edit.setStyleSheet("padding: 8px;")
        settings_input_layout.addWidget(self.network_settings_edit)

        settings_browse_btn = QPushButton("Browse...")
        settings_browse_btn.setStyleSheet("padding: 8px; min-width: 80px;")
        settings_browse_btn.clicked.connect(lambda: self._browse_file(
            self.network_settings_edit,
            "jobdocs-settings.json"
        ))
        settings_input_layout.addWidget(settings_browse_btn)

        network_layout.addLayout(settings_input_layout)

        network_layout.addSpacing(10)

        # History file
        history_label = QLabel("History File (where job history is stored):")
        history_label.setWordWrap(True)
        network_layout.addWidget(history_label)

        history_input_layout = QHBoxLayout()
        self.network_history_edit = QLineEdit(self.settings.get('network_history_path', ''))
        self.network_history_edit.setPlaceholderText(r"Example: \\server\shared\jobdocs-history.json")
        self.network_history_edit.setStyleSheet("padding: 8px;")
        history_input_layout.addWidget(self.network_history_edit)

        history_browse_btn = QPushButton("Browse...")
        history_browse_btn.setStyleSheet("padding: 8px; min-width: 80px;")
        history_browse_btn.clicked.connect(lambda: self._browse_file(
            self.network_history_edit,
            "jobdocs-history.json"
        ))
        history_input_layout.addWidget(history_browse_btn)

        network_layout.addLayout(history_input_layout)

        layout.addWidget(network_group)
        self.network_group = network_group

        # Help notes
        note = QLabel(
            "💡 Your personal preferences (like UI theme) stay on your computer.\n"
            "💡 These files should be on a shared network drive that everyone can access."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #0078d4; font-size: 11px; font-style: italic; margin-top: 5px;")
        layout.addWidget(note)

        self._toggle_network_fields(self.enable_network_check.isChecked())

        layout.addStretch()

        return widget

    def _create_user_auth_page(self) -> QWidget:
        """Create user authentication setup page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        intro = QLabel(
            "<b>User Accounts (Optional)</b><br>"
            "<span style='color: #666;'>Track who is using JobDocs</span>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(intro)

        explanation = QLabel(
            "User accounts let you control who can use JobDocs and keep track of who's doing what. "
            "This is useful for teams who want to monitor usage."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #444; background-color: #f0f8ff; padding: 10px; border-radius: 5px;")
        layout.addWidget(explanation)

        # Check if user_auth module is available
        user_auth_available = self._check_user_auth_available()

        if not user_auth_available:
            warning_box = QGroupBox("⚠️ Feature Not Available")
            warning_layout = QVBoxLayout(warning_box)
            warning_box.setStyleSheet("QGroupBox { border: 2px solid #ffc107; border-radius: 8px; padding: 10px; }")

            warning = QLabel(
                "The user accounts feature is not currently available on your system.\n\n"
                "This is an advanced feature that needs to be enabled manually."
            )
            warning.setWordWrap(True)
            warning_layout.addWidget(warning)

            tech_note = QLabel(
                "<b>For technical users:</b><br>"
                "To enable this feature, rename the folder 'modules/_user_auth' to 'modules/user_auth' "
                "and restart JobDocs."
            )
            tech_note.setTextFormat(Qt.TextFormat.RichText)
            tech_note.setWordWrap(True)
            tech_note.setStyleSheet("color: #666; font-size: 11px; margin-top: 10px; padding: 8px; background-color: #f5f5f5;")
            warning_layout.addWidget(tech_note)

            layout.addWidget(warning_box)

            self.enable_user_auth_check = QCheckBox("Enable user accounts (not available)")
            self.enable_user_auth_check.setEnabled(False)
            self.enable_user_auth_check.setChecked(False)
            self.enable_user_auth_check.setStyleSheet("color: #999;")
            layout.addWidget(self.enable_user_auth_check)
        else:
            self.enable_user_auth_check = QCheckBox("✓ Enable user accounts")
            self.enable_user_auth_check.setStyleSheet("font-weight: bold; font-size: 13px;")
            self.enable_user_auth_check.setChecked(self.settings.get('user_auth_enabled', False))
            layout.addWidget(self.enable_user_auth_check)

            # Network users file section
            network_users_box = QGroupBox("Shared User Accounts (For Teams)")
            network_users_layout = QVBoxLayout(network_users_box)

            network_users_desc = QLabel(
                "For multi-machine setups, you can share user accounts across the team. "
                "This allows admins to create accounts on one machine that work on all machines."
            )
            network_users_desc.setWordWrap(True)
            network_users_desc.setStyleSheet("color: #444; margin-bottom: 8px;")
            network_users_layout.addWidget(network_users_desc)

            # Auto-search button
            search_layout = QHBoxLayout()
            search_btn = QPushButton("🔍 Auto-Search for Shared Users File")
            search_btn.setStyleSheet("padding: 8px; background-color: #0078d4; color: white; font-weight: bold;")
            search_btn.clicked.connect(self._auto_search_users_file)
            search_layout.addWidget(search_btn)
            search_layout.addStretch()
            network_users_layout.addLayout(search_layout)

            # Manual path input
            users_path_label = QLabel("Or manually specify path:")
            users_path_label.setStyleSheet("margin-top: 10px; color: #666;")
            network_users_layout.addWidget(users_path_label)

            users_path_layout = QHBoxLayout()
            self.network_users_edit = QLineEdit(self.settings.get('network_users_path', ''))
            self.network_users_edit.setPlaceholderText(r"Example: \\server\shared\jobdocs-users.json")
            self.network_users_edit.setStyleSheet("padding: 8px;")
            users_path_layout.addWidget(self.network_users_edit)

            users_browse_btn = QPushButton("Browse...")
            users_browse_btn.setStyleSheet("padding: 8px; min-width: 80px;")
            users_browse_btn.clicked.connect(lambda: self._browse_file(
                self.network_users_edit,
                "jobdocs-users.json"
            ))
            users_path_layout.addWidget(users_browse_btn)
            network_users_layout.addLayout(users_path_layout)

            layout.addWidget(network_users_box)

            benefits_box = QGroupBox("What You Get")
            benefits_layout = QVBoxLayout(benefits_box)

            info = QLabel(
                "✓ Users must log in with a username and password\n"
                "✓ Track who is using the system\n"
                "✓ Manage user accounts from the Admin tab\n"
                "✓ Optional: audit user actions"
            )
            info.setWordWrap(True)
            info.setStyleSheet("color: #444; line-height: 1.6;")
            benefits_layout.addWidget(info)

            layout.addWidget(benefits_box)

        # Help note
        help_note = QLabel(
            "💡 You can skip this for now and enable it later if needed"
        )
        help_note.setStyleSheet("color: #0078d4; font-size: 11px; font-style: italic; margin-top: 10px;")
        help_note.setWordWrap(True)
        layout.addWidget(help_note)

        layout.addStretch()

        return widget

    def _create_completion_page(self) -> QWidget:
        """Create completion page"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        # Success icon
        icon = QLabel("✓")
        icon.setStyleSheet("font-size: 72px; color: #107c10;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # Title
        title = QLabel("<h2 style='text-align: center;'>All Set!</h2>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("JobDocs is configured and ready to use")
        subtitle.setStyleSheet("color: #666; text-align: center;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Next steps
        next_steps_box = QGroupBox("What You Can Do Now")
        next_steps_layout = QVBoxLayout(next_steps_box)

        steps = QLabel(
            "<ol style='line-height: 2.0;'>"
            "<li><b>Create Jobs</b> - Use the 'Create Job' tab to start organizing your work</li>"
            "<li><b>Import Blueprints</b> - Add drawings to your blueprint library</li>"
            "<li><b>Search</b> - Find jobs and files quickly using the Search tab</li>"
            "<li><b>Manage Settings</b> - Adjust settings anytime from File → Settings</li>"
            "</ol>"
        )
        steps.setTextFormat(Qt.TextFormat.RichText)
        steps.setWordWrap(True)
        next_steps_layout.addWidget(steps)

        layout.addWidget(next_steps_box)

        # Help note
        help_box = QGroupBox("Need Help?")
        help_layout = QVBoxLayout(help_box)

        help_text = QLabel(
            "• Check the <b>Help</b> menu for getting started guides\n"
            "• Re-run this wizard anytime from the <b>Admin</b> tab\n"
            "• Change any setting from <b>File → Settings</b>"
        )
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #444; line-height: 1.8;")
        help_layout.addWidget(help_text)

        layout.addWidget(help_box)

        # Final note
        final_note = QLabel(
            "Click 'Finish' to start using JobDocs!"
        )
        final_note.setStyleSheet("color: #0078d4; font-weight: bold; font-size: 13px; text-align: center; margin-top: 10px;")
        final_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(final_note)

        layout.addStretch()

        return widget

    # ==================== NAVIGATION ====================

    def update_page(self):
        """Update the current page display"""
        self.stack.setCurrentIndex(self.current_page)

        # Update title
        titles = [
            "Welcome",
            "Directory Configuration",
            "Link Type Selection",
            "Network Sharing",
            "User Authentication",
            "Setup Complete"
        ]
        self.title_label.setText(f"Step {self.current_page + 1} of {len(self.pages)}: {titles[self.current_page]}")

        # Update buttons
        self.back_button.setEnabled(self.current_page > 0)

        is_last_page = self.current_page == len(self.pages) - 1
        self.next_button.setVisible(not is_last_page)
        self.finish_button.setVisible(is_last_page)

    def go_next(self):
        """Go to next page"""
        # Validate current page
        if not self._validate_page():
            return

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_page()

    def go_back(self):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_page()

    def _validate_page(self) -> bool:
        """Validate current page before proceeding"""
        if self.current_page == 1:  # Directories page
            bp_dir = self.bp_dir_edit.text().strip()
            cf_dir = self.cf_dir_edit.text().strip()

            if not bp_dir or not cf_dir:
                QMessageBox.warning(
                    self,
                    "Required Fields",
                    "Please configure both Blueprints and Customer Files directories."
                )
                return False

            # Check if this is a modification of existing settings
            existing_bp = self.app_context.settings.get('blueprints_dir', '')
            existing_cf = self.app_context.settings.get('customer_files_dir', '')

            if existing_bp and existing_cf:
                # Settings already exist - warn about changes
                if bp_dir != existing_bp or cf_dir != existing_cf:
                    reply = QMessageBox.warning(
                        self,
                        "⚠️ Warning: Changing Folder Locations",
                        "You are about to change the folder locations.\n\n"
                        "This is a critical change that affects how JobDocs finds files.\n\n"
                        "Current locations:\n"
                        f"  Blueprints: {existing_bp}\n"
                        f"  Customer Files: {existing_cf}\n\n"
                        "New locations:\n"
                        f"  Blueprints: {bp_dir}\n"
                        f"  Customer Files: {cf_dir}\n\n"
                        "⚠️ Only change these if:\n"
                        "  • You moved your files to a new location\n"
                        "  • You know what you're doing\n"
                        "  • You understand this may affect existing jobs\n\n"
                        "Are you sure you want to make this change?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )

                    if reply == QMessageBox.StandardButton.No:
                        return False

            # Save to settings
            self.settings['blueprints_dir'] = bp_dir
            self.settings['customer_files_dir'] = cf_dir

        elif self.current_page == 2:  # Link type page
            selected = self.link_type_group.checkedId()
            if selected == 0:
                self.settings['link_type'] = 'hard'
            elif selected == 1:
                self.settings['link_type'] = 'symbolic'
            else:
                self.settings['link_type'] = 'copy'

        elif self.current_page == 3:  # Network sharing page
            self.settings['network_shared_enabled'] = self.enable_network_check.isChecked()
            if self.enable_network_check.isChecked():
                self.settings['network_settings_path'] = self.network_settings_edit.text().strip()
                self.settings['network_history_path'] = self.network_history_edit.text().strip()

        elif self.current_page == 4:  # User auth page
            self.settings['user_auth_enabled'] = self.enable_user_auth_check.isChecked()

            # Save network users path if configured
            if hasattr(self, 'network_users_edit'):
                network_users_path = self.network_users_edit.text().strip()
                self.settings['network_users_path'] = network_users_path

        return True

    def finish(self):
        """Finish the wizard"""
        if not self._validate_page():
            return

        # Save all settings
        self.app_context.settings.update(self.settings)
        self.app_context.save_settings()

        # Mark OOBE as completed
        self.settings['oobe_completed'] = True
        self.app_context.settings['oobe_completed'] = True
        self.app_context.save_settings()

        self.accept()

    # ==================== HELPERS ====================

    def _browse_directory(self, line_edit: QLineEdit):
        """Browse for a directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            line_edit.setText(dir_path)

    def _auto_setup_directories(self):
        """Auto-setup standard directory structure from root folder"""
        from pathlib import Path
        from PyQt6.QtWidgets import QMessageBox, QInputDialog
        import platform
        import json

        # Ask user to select root folder
        root_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Root Folder (JobDocs will create subdirectories here)",
            "",
            QFileDialog.Option.ShowDirsOnly
        )

        if not root_dir:
            return  # User cancelled

        root_path = Path(root_dir)

        # Define standard subdirectories
        blueprints_path = root_path / "blueprints"
        customer_files_path = root_path / "customer files"

        # Define hidden network settings folder
        # Use .jobdocs on Unix/Mac, jobdocs on Windows (will be hidden via attribute)
        if platform.system() == 'Windows':
            network_folder = root_path / "jobdocs"
        else:
            network_folder = root_path / ".jobdocs"

        network_settings_path = network_folder / "shared_settings.json"
        network_history_path = network_folder / "shared_history.json"
        network_users_path = network_folder / "shared_users.json"

        # Show confirmation
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Auto-Setup")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"JobDocs will create the following structure:\n\n"
            f"📐 Blueprints: {blueprints_path}\n"
            f"👥 Customer Files: {customer_files_path}\n"
            f"🔧 Network Settings (hidden): {network_folder}\n\n"
            f"This will also:\n"
            f"  ✓ Enable team sharing\n"
            f"  ✓ Enable user accounts\n"
            f"  ✓ Create initial admin user\n\n"
            f"Continue?"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        if msg.exec() != QMessageBox.StandardButton.Yes:
            return

        # Prompt for admin username and password
        username, ok = QInputDialog.getText(
            self,
            "Create Admin Account",
            "Enter admin username:",
            text="admin"
        )

        if not ok or not username.strip():
            QMessageBox.warning(self, "Cancelled", "Auto-setup cancelled. Admin account is required.")
            return

        username = username.strip().lower()

        password, ok = QInputDialog.getText(
            self,
            "Create Admin Account",
            f"Enter password for '{username}':",
            QLineEdit.EchoMode.Password
        )

        if not ok or not password:
            QMessageBox.warning(self, "Cancelled", "Auto-setup cancelled. Password is required.")
            return

        # Create directories
        try:
            blueprints_path.mkdir(parents=True, exist_ok=True)
            customer_files_path.mkdir(parents=True, exist_ok=True)
            network_folder.mkdir(parents=True, exist_ok=True)

            # On Windows, set hidden attribute on network folder
            if platform.system() == 'Windows':
                import subprocess
                try:
                    subprocess.run(['attrib', '+H', str(network_folder)], check=False)
                except:
                    pass  # Not critical if this fails

            # Create initial admin user in network users file
            from modules.user_auth.user_auth import UserAuth
            import hashlib
            import secrets

            # Generate salt and hash password
            salt = secrets.token_hex(32)
            password_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                bytes.fromhex(salt),
                100000
            ).hex()

            # Create users.json with admin user
            users_data = {
                username: {
                    "password_hash": password_hash,
                    "salt": salt,
                    "full_name": "",
                    "is_admin": True,
                    "created": None,
                    "last_login": None
                }
            }

            with open(network_users_path, 'w') as f:
                json.dump(users_data, f, indent=2)

            # Create empty network settings and history files
            with open(network_settings_path, 'w') as f:
                json.dump({}, f, indent=2)

            with open(network_history_path, 'w') as f:
                json.dump({"recent_jobs": [], "customers": []}, f, indent=2)

            # Update the directory UI fields
            self.bp_dir_edit.setText(str(blueprints_path))
            self.cf_dir_edit.setText(str(customer_files_path))

            # Update the network settings UI fields (if they exist)
            if hasattr(self, 'network_settings_edit'):
                self.network_settings_edit.setText(str(network_settings_path))
            if hasattr(self, 'network_history_edit'):
                self.network_history_edit.setText(str(network_history_path))
            if hasattr(self, 'network_users_edit'):
                self.network_users_edit.setText(str(network_users_path))

            # Enable network sharing checkbox
            if hasattr(self, 'enable_network_check'):
                self.enable_network_check.setChecked(True)

            # Enable user auth checkbox
            if hasattr(self, 'enable_user_auth_check'):
                self.enable_user_auth_check.setChecked(True)

            # Apply all recommended settings directly to self.settings
            # Directory paths
            self.settings['blueprints_dir'] = str(blueprints_path)
            self.settings['customer_files_dir'] = str(customer_files_path)
            self.settings['itar_blueprints_dir'] = ''  # ITAR optional
            self.settings['itar_customer_files_dir'] = ''  # ITAR optional

            # File handling defaults
            self.settings['link_type'] = 'hard'  # Recommended for reliability
            self.settings['blueprint_extensions'] = ['.pdf', '.dwg', '.dxf']
            self.settings['allow_duplicate_jobs'] = False

            # Folder structure defaults
            self.settings['job_folder_structure'] = '{customer}/job documents/{job_folder}'
            self.settings['quote_folder_path'] = 'Quotes'
            self.settings['legacy_mode'] = True

            # Network sharing (enabled for team use)
            self.settings['network_shared_enabled'] = True
            self.settings['network_settings_path'] = str(network_settings_path)
            self.settings['network_history_path'] = str(network_history_path)

            # User authentication (enabled for team use)
            self.settings['user_auth_enabled'] = True
            self.settings['network_users_path'] = str(network_users_path)

            # Mark OOBE as completed
            self.settings['oobe_completed'] = True

            # Save all settings immediately
            self.app_context.settings.update(self.settings)
            self.app_context.save_settings()

            # Show success message and close wizard
            QMessageBox.information(
                self,
                "Auto-Setup Complete!",
                f"✓ JobDocs has been configured for team use!\n\n"
                f"📐 Blueprints: {blueprints_path}\n"
                f"👥 Customer Files: {customer_files_path}\n"
                f"🔧 Network Settings: {network_folder}\n"
                f"👤 Admin User: {username}\n\n"
                f"Configuration saved. JobDocs will now restart.\n"
                f"Log in with your admin credentials to get started."
            )

            # Accept the wizard (close and mark as completed)
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create auto-setup:\n{e}\n\n"
                f"Please check permissions and try again, or set up manually."
            )

    def _browse_file(self, line_edit: QLineEdit, default_filename: str = ""):
        """
        Browse for a file with optional default filename.

        Args:
            line_edit: The line edit to populate with the selected path
            default_filename: Default filename to suggest (e.g., "jobdocs-settings.json")
        """
        # Get current value from line edit or use default filename
        current_value = line_edit.text().strip()

        # If there's a current value, use its directory
        # Otherwise, suggest the default filename
        if current_value:
            initial_path = current_value
        elif default_filename:
            initial_path = default_filename
        else:
            initial_path = ""

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select File Location",
            initial_path,
            "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            # Ensure .json extension
            if not file_path.endswith('.json'):
                file_path += '.json'
            line_edit.setText(file_path)

    def _toggle_network_fields(self, enabled: bool):
        """Enable/disable network path fields"""
        self.network_group.setEnabled(enabled)

    def _check_user_auth_available(self) -> bool:
        """Check if user_auth module is available"""
        try:
            from modules.user_auth.user_auth import UserAuth
            return True
        except ImportError:
            return False

    def _auto_search_users_file(self):
        """Automatically search for network users file in common locations"""
        import os

        search_locations = []

        # If network settings are configured, search near those files
        network_settings_path = self.settings.get('network_settings_path', '')
        network_history_path = self.settings.get('network_history_path', '')

        if network_settings_path:
            # Search in same directory as network settings
            settings_dir = Path(network_settings_path).parent
            search_locations.append(settings_dir / 'jobdocs-users.json')
            search_locations.append(settings_dir / 'users.json')
            search_locations.append(settings_dir / '.jobdocs-users.json')

        if network_history_path:
            # Search in same directory as network history
            history_dir = Path(network_history_path).parent
            search_locations.append(history_dir / 'jobdocs-users.json')
            search_locations.append(history_dir / 'users.json')
            search_locations.append(history_dir / '.jobdocs-users.json')

        # Search in customer files directory (team might put it there)
        cf_dir = self.settings.get('customer_files_dir', '')
        if cf_dir:
            cf_path = Path(cf_dir).parent
            search_locations.append(cf_path / 'jobdocs-users.json')
            search_locations.append(cf_path / '.jobdocs-users.json')

        # Search common network share patterns on Windows
        if os.name == 'nt':
            # Check for mapped drives
            for drive in 'GHIJKLMNOPQRSTUVWXYZ':
                drive_path = Path(f'{drive}:/')
                if drive_path.exists():
                    search_locations.append(drive_path / 'jobdocs' / 'jobdocs-users.json')
                    search_locations.append(drive_path / 'shared' / 'jobdocs-users.json')

        # Remove duplicates while preserving order
        seen = set()
        unique_locations = []
        for loc in search_locations:
            if str(loc) not in seen:
                seen.add(str(loc))
                unique_locations.append(loc)

        # Search for existing files
        found_files = []
        for location in unique_locations:
            if location.exists():
                found_files.append(location)

        if not found_files:
            QMessageBox.information(
                self,
                "No Users File Found",
                "Could not find a shared users file in common locations.\n\n"
                "Searched in:\n" + "\n".join(f"  • {loc}" for loc in unique_locations[:5]) +
                ("\n  • ..." if len(unique_locations) > 5 else "") + "\n\n"
                "You can:\n"
                "  • Create users on this machine (they'll be local only)\n"
                "  • Manually specify the network users file path below\n"
                "  • Have your admin set up the users file on the network"
            )
            return

        # Found one or more files
        if len(found_files) == 1:
            # Only one file found - use it
            self.network_users_edit.setText(str(found_files[0]))
            QMessageBox.information(
                self,
                "Found Shared Users File!",
                f"Found and selected:\n{found_files[0]}\n\n"
                "You can now use user accounts managed by your admin."
            )
        else:
            # Multiple files found - let user choose
            from PyQt6.QtWidgets import QInputDialog
            file_names = [str(f) for f in found_files]
            choice, ok = QInputDialog.getItem(
                self,
                "Multiple Users Files Found",
                "Select the correct users file:",
                file_names,
                0,
                False
            )
            if ok and choice:
                self.network_users_edit.setText(choice)
                QMessageBox.information(
                    self,
                    "Users File Selected",
                    f"Selected:\n{choice}"
                )
