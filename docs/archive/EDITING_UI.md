# Editing the JobDocs UI

This guide explains how to edit the JobDocs user interface.

## Quick Start

The main window structure is now defined in `jobdocs_mainwindow.ui`, which can be edited with Qt Designer or any text editor.

## Using Qt Designer

### Installing Qt Designer

**Linux:**
```bash
sudo apt install qttools5-dev-tools  # For Qt5
# or
pip install pyqt6-tools
```

**macOS:**
```bash
brew install qt
# or
pip install pyqt6-tools
```

**Windows:**
```bash
pip install pyqt6-tools
```

### Opening the UI File

```bash
# If installed system-wide
designer jobdocs_mainwindow.ui

# If installed via pip
python3 -m PyQt6.uic.pyuic6 --preview jobdocs_mainwindow.ui
```

## What Can Be Edited in the UI File

### Window Properties
- Window title
- Window size (minimum, maximum, default)
- Window icon (if added)

### Menu Structure
- Menu bar layout
- Menu items
- Menu separators
- Menu actions (names and properties)

### Main Layout
- Scroll area properties
- Tab widget properties
- Overall layout margins and spacing

### Actions
The following actions are defined and can be edited:
- `actionSettings` - Opens the settings dialog
- `actionExit` - Exits the application
- `actionAbout` - Shows the about dialog
- `actionGettingStarted` - Shows the getting started guide

## What Cannot Be Edited in the UI File

The following are still defined in Python code:

### Tab Content
All tab content is created programmatically:
- Create Quote tab
- Create Job tab
- Add to Job tab
- Bulk Create tab
- Search tab
- Import Blueprints tab
- History tab
- Reports tab (experimental)

**Why?** These tabs contain:
- Custom widgets (DropZone)
- Dynamic content
- Complex layouts
- Business logic integration

### Custom Widgets
- `DropZone` - Drag and drop file widget
- `ScrollableMessageDialog` - Custom dialog
- `SettingsDialog` - Settings window

## Common Editing Tasks

### Adding a New Menu Item

1. Open `jobdocs_mainwindow.ui` in Qt Designer or text editor
2. Add a new `<action>` in the actions section:
```xml
<action name="actionNewFeature">
 <property name="text">
  <string>New Feature</string>
 </property>
</action>
```
3. Add it to a menu:
```xml
<widget class="QMenu" name="menuFile">
 <addaction name="actionSettings"/>
 <addaction name="actionNewFeature"/>  <!-- New item -->
 <addaction name="separator"/>
 <addaction name="actionExit"/>
</widget>
```
4. Connect it in `setup_menu()` method in `JobDocs-qt.py`:
```python
def setup_menu(self):
    self.actionSettings.triggered.connect(self.open_settings)
    self.actionNewFeature.triggered.connect(self.handle_new_feature)  # Add this
    self.actionExit.triggered.connect(self.close)
    ...
```

### Changing Window Size

Edit the `minimumSize` property in the UI file:
```xml
<property name="minimumSize">
 <size>
  <width>1024</width>  <!-- Changed from 900 -->
  <height>768</height> <!-- Changed from 700 -->
 </size>
</property>
```

### Changing Window Title

Edit the `windowTitle` property:
```xml
<property name="windowTitle">
 <string>JobDocs - Professional Edition</string>
</property>
```

### Adding a New Menu

In the menubar section:
```xml
<widget class="QMenuBar" name="menubar">
 <widget class="QMenu" name="menuFile">
  <property name="title">
   <string>File</string>
  </property>
 </widget>
 <widget class="QMenu" name="menuHelp">
  <property name="title">
   <string>Help</string>
  </property>
 </widget>
 <widget class="QMenu" name="menuTools">  <!-- New menu -->
  <property name="title">
   <string>Tools</string>
  </property>
  <addaction name="actionNewTool"/>
 </widget>
 <addaction name="menuFile"/>
 <addaction name="menuHelp"/>
 <addaction name="menuTools"/>  <!-- Add to menubar -->
</widget>
```

## Manual Editing (Text Editor)

The `.ui` file is XML and can be edited directly:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>MainWindow</class>
 <widget class="QMainWindow" name="MainWindow">
  <!-- Window properties here -->
 </widget>
</ui>
```

### Tips for Manual Editing
- Use proper XML formatting
- Maintain consistent indentation
- Close all tags properly
- Validate XML syntax after editing

## Testing Your Changes

After editing the UI file:

```bash
# Test that the UI loads
python3 test_ui_loading.py

# Run the application
python3 JobDocs-qt.py
```

## Important Notes

### Action Naming Convention
- Action names should start with `action` (e.g., `actionSettings`)
- This makes them easily identifiable in the Python code
- Must match the name used in Python signal connections

### Object Names
The following object names are used in Python code and must not be changed:
- `tabs` - The main QTabWidget
- `actionSettings` - Settings menu action
- `actionExit` - Exit menu action
- `actionAbout` - About menu action
- `actionGettingStarted` - Getting started menu action

### After Making Changes

1. **Test immediately**: Run `test_ui_loading.py`
2. **Check for errors**: Look for XML parsing errors
3. **Verify functionality**: Test the affected menus/actions
4. **Update documentation**: If adding features, update relevant docs

## Advanced: Converting More Components to UI Files

If you want to convert tab content or dialogs to `.ui` files:

1. **Create the UI file** in Qt Designer
2. **Save with descriptive name** (e.g., `quote_tab.ui`)
3. **Load in Python**:
```python
def create_quote_tab(self) -> QWidget:
    widget = QWidget()
    uic.loadUi('quote_tab.ui', widget)
    # Connect signals
    widget.quote_customer_combo.currentTextChanged.connect(...)
    return widget
```
4. **Update build scripts** to include the new `.ui` file

## Resources

- [Qt Designer Manual](https://doc.qt.io/qt-6/qtdesigner-manual.html)
- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt UI File Format](https://doc.qt.io/qt-6/designer-ui-file-format.html)

## Troubleshooting

### UI File Not Found
```
FileNotFoundError: UI file not found: /path/to/jobdocs_mainwindow.ui
```
**Solution**: Ensure the `.ui` file is in the same directory as `JobDocs-qt.py`

### Action Not Found
```
AttributeError: 'JobDocs' object has no attribute 'actionNewFeature'
```
**Solution**:
1. Check that the action is defined in the `.ui` file
2. Verify the action name matches exactly (case-sensitive)
3. Ensure `uic.loadUi()` completed successfully

### Broken Layout
If the UI looks wrong after editing:
1. Check XML syntax validity
2. Verify all tags are properly closed
3. Compare with a backup of the working `.ui` file
4. Use Qt Designer to validate and fix the layout

## Best Practices

1. **Always backup** the `.ui` file before editing
2. **Test after each change** - don't make multiple changes at once
3. **Use Qt Designer** for complex layout changes
4. **Use text editor** for simple property changes
5. **Keep Python and UI in sync** - if you rename an action, update Python code
6. **Document custom actions** in comments
7. **Version control** - commit `.ui` file changes with clear messages

## Example Workflow

1. Identify what you want to change
2. Open `jobdocs_mainwindow.ui` in Qt Designer
3. Make the changes visually
4. Save the file
5. Run `python3 test_ui_loading.py`
6. If adding new actions, edit `setup_menu()` in Python
7. Test the full application
8. Commit changes to version control
