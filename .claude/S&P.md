# Standards & Practices — CodeRabbit Review Log

This file records CodeRabbit recommendations so they can be applied to future changes.
Review this file before making changes to the codebase.

---

## 2026-04-06 — `modules/search/module.py` (hidden file filter)

**Review:** FILTER HIDDEN ENTRIES FROM FOLDER-CONTENTS PANEL
**Result:** No issues detected. 3 nitpicks.

### Nitpicks (all resolved in `fix/coderabbit-hidden-file-nitpicks`)

1. **Hoist helper functions out of inner scopes**
   - Do not define helper functions (e.g. `_is_hidden`) inside a method — they are recreated on every call.
   - Move them to module level or class level.

2. **Sort directories before files**
   - `key=lambda n: (os.path.isdir(...), n.lower())` sorts files before dirs (`False < True`).
   - Use `not os.path.isdir(...)` to put directories first, consistent with OS file browser conventions.

3. **Avoid broad `except Exception`**
   - Catch specific exceptions instead (e.g. `AttributeError`, `OSError`).
   - Broad catches can silently mask unexpected errors.

---

## 2026-04-07 — Full codebase review (PR #5 — review/full-codebase)

**Review:** CodeRabbit full codebase snapshot review — 16 findings across 10 files.
**Result:** All 16 fixes applied on `fix/coderabbit-full-review`.

### Findings

1. **Unquoted `S&P.md` path in workflow YAML** — `.github/workflows/log-coderabbit-review.yml`
   - `&` in unquoted shell path acts as background operator, breaking append and git add
   - Fix: quote the path as `".claude/S&P.md"` in both places

2. **`rm -rf` with unvalidated variables** — `build_scripts/build_linux.sh`
   - Empty `BUILD_PATH` or `DIST_PATH` would expand to `rm -rf /`
   - Fix: use `${VAR:?message}` bash parameter expansion (SC2115)

3. **No error check after exe copy** — `build_scripts/build_windows.bat`
   - Script could report success with an incomplete package if copy fails
   - Fix: add `if errorlevel 1` check immediately after `copy` command

4. **PSM-only modules bundled into stable build** — `build_scripts/JobDocs.spec`
   - `modules/reporting`, `pandas`, `openpyxl` included unconditionally (violates Rule 3)
   - Fix: exclude `reporting` from UI file collection; remove PSM deps from `hiddenimports`

5. **`find_job_folders()` misses `{po_number}` template paths** — `core/app_context.py`
   - `{po_number}` in path template was treated as a literal directory name
   - Fix: detect `{po_number}` in prefix and enumerate actual PO subdirectories

6. **Insecure default credentials** — `experimental/db_integration.py`
   - `os.environ.get("JOBBOSS_USER", "user")` normalizes weak secret handling
   - Fix: require env vars explicitly; raise `RuntimeError` if missing

7. **Dead code stub with wrong signature** — `main.py`
   - `create_single_job` on `JobDocsMainWindow` was never called; Bulk calls it on `JobModule`
   - Also missing `po_number` param — would `TypeError` if ever invoked
   - Fix: delete the method entirely

8. **`shutil.copy2` silently overwrites files** — `modules/job/module.py`
   - `FileExistsError` handlers were dead code — `copy2` never raises it
   - Fix: explicit `if not dest.exists()` check before every `copy2` call

9. **`search_jobs` ignores customer and ITAR filters** — `modules/job/module.py`
   - Always searched all dirs; customer combo and radio buttons had no effect during search
   - Fix: mirror `refresh_job_tree` filter logic in `search_jobs`

10. **`open_blueprints_folder` ignores ITAR context** — `modules/job/module.py`
    - Always used `blueprints_dir`; ITAR jobs opened the wrong directory
    - Fix: detect `[ITAR]` prefix on tree item display names; use `itar_blueprints_dir`

11. **`shutil.copy2` silently overwrites files** — `modules/quote/module.py`
    - Same pattern as finding 8
    - Fix: same existence-check approach

12. **`search_quotes` ignores customer and ITAR filters** — `modules/quote/module.py`
    - Same pattern as finding 9
    - Fix: mirror `refresh_quote_tree` filter logic in `search_quotes`

13. **`open_blueprints_folder` ignores ITAR context** — `modules/quote/module.py`
    - Same pattern as finding 10
    - Fix: detect `[ITAR]` prefix; use `quote_itar_check` for Create New tab fallback

14. **`[ITAR-BP]` not treated as ITAR** — `modules/search/module.py`
    - `is_itar` check only matched `[ITAR]`; blueprint results from ITAR-BP search used wrong dir
    - Fix: `customer_label.startswith(('[ITAR] ', '[ITAR-BP] '))`

15. **Wrong legacy file path in test script** — `old/test-scripts/test_ui_loading.py`
    - Path pointed to `old/test-scripts/JobDocs-qt.py`; file is at `old/legacy/JobDocs-qt.py`
    - Note: `old/` is gitignored — fix applied locally but not committed
    - Fix: `Path(__file__).resolve().parents[1] / "legacy" / "JobDocs-qt.py"`

16. **Invalid `//` comments in `pyrightconfig.json`**
    - Comments are not valid JSON; file failed strict JSON parsing
    - Context: suppressions are global because PyQt6/uic.loadUi injects ~300+ widget
      attributes at runtime that Pyright cannot see statically
    - Fix: remove comment block; explanation preserved here in S&P.md
