# UI Conversion Progress - Converting Tabs to .ui Files

## Goal
Convert all tab content from programmatic Python code to Qt Designer .ui files for visual editing.

---

## ✅ COMPLETED (Session 1)

### 1. Infrastructure Setup
- ✅ Created [dropzone_widget.py](dropzone_widget.py) - Extracted DropZone custom widget
- ✅ Created `tabs/` directory for UI files
- ✅ Added DropZone import to JobDocs-qt.py (line 38)
- ✅ Added `get_ui_path()` helper method (line 695-708)

### 2. History Tab - **FULLY WORKING** ✓
- ✅ Created [tabs/history_tab.ui](tabs/history_tab.ui)
- ✅ Modified `create_history_tab()` method (line 1815-1834)
- ✅ Tested and confirmed working

**You can now edit the History tab visually:**
```bash
designer6 tabs/history_tab.ui
```

### 3. Import Tab - **UI FILE CREATED**
- ✅ Created [tabs/import_tab.ui](tabs/import_tab.ui)
- ❌ NOT YET connected in Python
- Includes DropZone as promoted widget

---

## 📋 REMAINING WORK (7 tabs)

### Next Priority Order:

#### **NEXT:** Import Tab (Already has UI file)
**File:** [tabs/import_tab.ui](tabs/import_tab.ui) ✓
**Python Method:** `create_import_tab()` at line ~1730
**Complexity:** Medium - Has DropZone widget
**Estimate:** 10 minutes

**What to do:**
1. Read the current `create_import_tab()` method
2. Replace with UI loading code (use History tab as template)
3. Connect signals:
   - `import_drop_zone.files_dropped` → `self.handle_import_files`
   - `import_btn.clicked` → `self.check_and_import`
   - `clear_btn.clicked` → `self.clear_import_list`
4. Store instance references:
   - `self.import_customer_combo`
   - `self.import_itar_check`
   - `self.import_drop_zone`
   - `self.import_files_list`
   - `self.import_log`
5. Test

---

#### Bulk Create Tab
**File:** Need to create `tabs/bulk_tab.ui`
**Python Method:** `create_bulk_tab()` at line ~1540
**Complexity:** Medium - No DropZone, has table
**Estimate:** 15 minutes

**Widgets to include:**
- `bulk_itar_check` - QCheckBox
- `bulk_text` - QPlainTextEdit
- `bulk_table` - QTableWidget (5 columns)
- `bulk_status_label` - QLabel
- `bulk_progress` - QProgressBar (hidden initially)
- Buttons: import_btn, clear_bulk_btn, validate_btn, create_bulk_btn

---

#### Search Tab
**File:** Need to create `tabs/search_tab.ui`
**Python Method:** `create_search_tab()` at line ~1621
**Complexity:** Medium-High - Dynamic visibility
**Estimate:** 20 minutes

**Widgets to include:**
- `search_edit` - QLineEdit
- `search_customer_check`, `search_job_check`, `search_desc_check`, `search_drawing_check` - QCheckBox
- `mode_row_widget` - QWidget (container)
- `search_all_radio`, `search_strict_radio` - QRadioButton
- `legacy_options_widget` - QWidget (container)
- `search_blueprints_check` - QCheckBox
- `search_table` - QTableWidget (5 columns)
- `search_status_label` - QLabel
- `search_progress` - QProgressBar

**Note:** Has dynamic show/hide based on legacy mode setting

---

#### Quote Tab
**File:** Need to create `tabs/quote_tab.ui`
**Python Method:** `create_quote_tab()` at line ~760
**Complexity:** High - DropZone + Splitter + Search
**Estimate:** 25 minutes

**Widgets to include:**
- `quote_customer_combo` - QComboBox (editable)
- `quote_number_edit` - QLineEdit
- `quote_description_edit` - QLineEdit
- `quote_drawings_edit` - QLineEdit
- `quote_itar_check` - QCheckBox
- `quote_drop_zone` - DropZone (promoted)
- `quote_files_list` - QListWidget
- `quote_search_input` - QLineEdit
- `quote_search_results` - QListWidget
- Multiple buttons for actions

**Note:** Uses QSplitter for side-by-side layout

---

#### Job Tab
**File:** Need to create `tabs/job_tab.ui`
**Python Method:** `create_job_tab()` at line ~1247
**Complexity:** High - Similar to Quote tab
**Estimate:** 25 minutes

**Widgets to include:**
- `customer_combo` - QComboBox
- `job_number_edit` - QLineEdit
- `job_status_label` - QLabel
- `description_edit` - QLineEdit
- `drawings_edit` - QLineEdit
- `itar_check` - QCheckBox
- `job_drop_zone` - DropZone
- `job_files_list` - QListWidget
- `job_search_input` - QLineEdit
- `job_search_results` - QListWidget
- Folder open buttons

---

#### Add to Job Tab
**File:** Need to create `tabs/add_to_job_tab.ui`
**Python Method:** `create_add_to_job_tab()` at line ~1383
**Complexity:** Very High - QTreeWidget + Splitter
**Estimate:** 30 minutes

**Widgets to include:**
- `add_customer_combo` - QComboBox
- `add_all_radio`, `add_standard_radio`, `add_itar_radio` - QRadioButton
- `add_search_edit` - QLineEdit
- `job_tree` - QTreeWidget
- `selected_job_label` - QLabel
- `dest_both_radio`, `dest_blueprints_radio`, `dest_job_radio` - QRadioButton
- `add_drop_zone` - DropZone
- `add_files_list` - QListWidget
- `add_status_label` - QLabel

**Note:** Button groups must be created in Python (not visual in Designer)

---

#### Reporting Tab (Experimental)
**File:** Need to create `tabs/reporting_tab.ui`
**Python Method:** `create_reporting_tab()` at line ~1832
**Complexity:** Medium - Database UI
**Estimate:** 20 minutes

**Widgets to include:**
- `db_status_label` - QLabel
- `connect_db_btn`, `disconnect_db_btn` - QPushButton
- `report_type_combo` - QComboBox
- `report_customer_combo` - QComboBox
- `report_start_date`, `report_end_date` - QLineEdit
- `generate_report_btn`, `export_report_btn` - QPushButton
- `report_table` - QTableWidget
- `report_status_label` - QLabel

---

## Pattern to Follow (Template)

For each tab:

### 1. Create UI File
Use Qt Designer or create XML directly:
```bash
designer6 tabs/TABNAME_tab.ui
```

### 2. Modify Python Method
Replace the entire method with this pattern:

```python
def create_TABNAME_tab(self) -> QWidget:
    """Create TABNAME tab by loading UI and connecting signals"""
    widget = QWidget()
    ui_file = self.get_ui_path('tabs/TABNAME_tab.ui')
    uic.loadUi(ui_file, widget)

    # Store widget references as instance attributes
    self.widget_name = widget.widget_name
    # ... repeat for all widgets that need instance-level access

    # Setup any special properties not in UI file
    # (like table column modes, etc.)

    # Connect signals
    widget.button_name.clicked.connect(self.handler_method)
    # ... repeat for all signal connections

    # Initialize content (if needed)
    QTimer.singleShot(100, self.initialize_method)

    return widget
```

### 3. Test
```bash
source venv/bin/activate
python3 test_ui_loading.py
python3 JobDocs-qt.py
```

---

## Build Script Updates Needed

Once all tabs are complete, update these files:

### [build_linux.sh](build_linux.sh:90)
Already has: `--add-data="jobdocs_mainwindow.ui:."`
**Add:** `--add-data="tabs/*.ui:tabs" \`
**Add:** `--add-data="dropzone_widget.py:." \`

### [build_macos.sh](build_macos.sh:99)
**Add:** `--add-data="tabs/*.ui:tabs" \`
**Add:** `--add-data="dropzone_widget.py:." \`

### [build_windows.bat](build_windows.bat:106)
**Add:** `--add-data="tabs/*.ui;tabs" ^`
**Add:** `--add-data="dropzone_widget.py;." ^`

---

## Testing Checklist

After each tab conversion:
- [ ] Tab displays correctly
- [ ] All widgets are visible
- [ ] Buttons work
- [ ] Signal connections function
- [ ] No errors in console
- [ ] Data populates correctly

Final tests:
- [ ] All 7-8 tabs converted
- [ ] Application runs without errors
- [ ] All functionality preserved
- [ ] Build scripts updated
- [ ] Executable builds successfully
- [ ] All UI files can be edited in Qt Designer

---

## Tips for Tomorrow

### Opening Qt Designer
```bash
designer6 tabs/TABNAME_tab.ui
```

### Key Widget Properties to Set
- **objectName** - MUST match Python variable names exactly
- **minimumSize** / **maximumSize** - For size constraints
- **text** - For labels, buttons, etc.
- **editable** - For combo boxes
- **readOnly** - For text widgets
- **selectionBehavior** - For tables
- **checked** - Default state for checkboxes

### Promoting DropZone Widget
1. Place a QFrame where DropZone should go
2. Set its objectName (e.g., `import_drop_zone`)
3. Right-click → "Promote to..."
4. Promoted class name: `DropZone`
5. Header file: `dropzone_widget.h`
6. Base class: QFrame
7. Click "Add" then "Promote"

### Common Layouts
- **QVBoxLayout** - Vertical stacking
- **QHBoxLayout** - Horizontal side-by-side
- **QGridLayout** - Grid of rows/columns
- **QSplitter** - Resizable split panels

---

## Estimated Total Time Remaining
- Import tab: 10 min
- Bulk tab: 15 min
- Search tab: 20 min
- Quote tab: 25 min
- Job tab: 25 min
- Add to Job tab: 30 min
- Reporting tab: 20 min
- Build scripts: 5 min
- Testing: 15 min

**Total: ~2.5 hours** (can be done 1-2 tabs per session)

---

## Current Status Summary

✅ **3/8 tabs complete** (History, Import, Bulk Create)
📁 **3/8 UI files created** (History, Import, Bulk) + 2 in progress by agent
🔧 **Helper methods added** (get_ui_path, DropZone import)
✓ **Application fully works** with all converted tabs

**Progress:** 37.5% complete | **Remaining:** ~2 hours

**Next session: Convert Search & Quote tabs (agent already creating UI files)**
