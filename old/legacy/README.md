# Legacy Code Archive

This directory contains the original monolithic version of JobDocs.

## JobDocs-qt.py

This is the original 2897-line monolithic implementation of JobDocs that was used before the modular refactor.

**Status**: ⚠️ **NON-FUNCTIONAL**

This file cannot run because it depends on modules that were refactored during the migration to the modular architecture:
- `dropzone_widget` → moved to `shared/widgets.py`
- Other internal dependencies reorganized

**Why It's Here**:
- Historical reference
- Code comparison for understanding the migration
- Git history preservation
- Shows the evolution of the project

**Do Not Use**:
- Use `main.py` instead (in the root directory)
- The modular version has all features plus improvements

**Migration Details**:
See [../../MIGRATION_COMPLETE.md](../../MIGRATION_COMPLETE.md) for the full story of how this was refactored into the modular plugin architecture.

---

For the working application, use:
```bash
cd ../..
python main.py
```
