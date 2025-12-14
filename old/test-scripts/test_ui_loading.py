#!/usr/bin/env python3
"""
Test script to verify the UI file loads correctly
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

try:
    # Import the main application
    import importlib.util
    spec = importlib.util.spec_from_file_location("jobdocs", Path(__file__).parent / "JobDocs-qt.py")
    jobdocs_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jobdocs_module)
    JobDocs = jobdocs_module.JobDocs

    # Create the application
    app = QApplication(sys.argv)

    # Create the main window
    window = JobDocs()

    # Check that the UI was loaded
    assert hasattr(window, 'tabs'), "tabs widget not found"
    assert hasattr(window, 'actionSettings'), "actionSettings not found"
    assert hasattr(window, 'actionExit'), "actionExit not found"
    assert hasattr(window, 'actionAbout'), "actionAbout not found"
    assert hasattr(window, 'actionGettingStarted'), "actionGettingStarted not found"

    # Check that tabs were created
    tab_count = window.tabs.count()
    print(f"✓ UI loaded successfully!")
    print(f"✓ Found {tab_count} tabs")
    print(f"✓ Window title: {window.windowTitle()}")
    print(f"✓ Window minimum size: {window.minimumSize().width()}x{window.minimumSize().height()}")

    # List all tabs
    for i in range(tab_count):
        tab_name = window.tabs.tabText(i)
        print(f"  - Tab {i}: {tab_name}")

    print("\n✓ All checks passed! The UI file is loading correctly.")
    sys.exit(0)

except Exception as e:
    print(f"✗ Error loading UI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
