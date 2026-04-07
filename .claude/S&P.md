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

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review`

**Actionable comments posted: 4**

> [!CAUTION]
> Some comments are outside the diff and can’t be posted inline due to platform limitations.
> 
> 
> 
> <details>
> <summary>⚠️ Outside diff range comments (1)</summary><blockquote>
> 
> <details>
> <summary>modules/job/module.py (1)</summary><blockquote>
> 
> `645-666`: _⚠️ Potential issue_ | _🟠 Major_
> 
> **Cancel the active tree worker before running a synchronous search.**
> 
> If `refresh_job_tree()` is still loading, its queued `customer_loaded` emissions can repopulate `self.job_tree` after Line 653 clears it, so the search view ends up mixed with stale browse results. Reuse the cancel/wait block from Lines 597-600 before the synchronous search starts.
> 
> <details>
> <summary>Suggested fix</summary>
> 
> ```diff
>      def search_jobs(self):
>          """Search for jobs matching the search term"""
>          search_term = self.add_search_edit.text().strip().lower()
>  
>          if not search_term:
>              self.refresh_job_tree()
>              return
>  
> +        if self._worker and self._worker.isRunning():
> +            self._worker.cancel()
> +            self._worker.wait()
> +
>          self.job_tree.clear()
> ```
> </details>
> 
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
> 
> ```
> Verify each finding against the current code and only fix it if needed.
> 
> In `@modules/job/module.py` around lines 645 - 666, Before clearing and performing
> the synchronous search in search_jobs, cancel and wait for any active tree
> worker using the same cancel/wait logic used elsewhere (the block that cancels
> the running tree worker and waits for it to finish) so queued customer_loaded
> emissions can't repopulate self.job_tree; integrate that cancel/wait call at the
> start of search_jobs (before self.job_tree.clear()) to ensure refresh_job_tree
> or any running worker is stopped prior to the synchronous search.
> ```
> 
> </details>
> 
> </blockquote></details>
> 
> </blockquote></details>

<details>
<summary>🧹 Nitpick comments (2)</summary><blockquote>

<details>
<summary>core/app_context.py (1)</summary><blockquote>

`311-318`: **Remove extraneous `f` prefixes from strings without placeholders.**

Static analysis correctly identifies these f-strings have no interpolation:

```diff
-                                        print(f"[find_job_folders]     ✗ Path doesn't exist", flush=True)
+                                        print("[find_job_folders]     ✗ Path doesn't exist", flush=True)
```

```diff
-                        print(f"[find_job_folders] Prefix path doesn't exist!", flush=True)
+                        print("[find_job_folders] Prefix path doesn't exist!", flush=True)
```

Note: Line 268's f-string with `{{po_number}}` is intentional (escaped braces display the literal).

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@core/app_context.py` around lines 311 - 318, The print statements inside
find_job_folders use unnecessary f-string prefixes for messages with no
interpolation; remove the leading f from the string literals in the calls that
print "[find_job_folders]     ✗ Path doesn't exist", "[find_job_folders]   Found
job (no suffix): {item}" only if {item} is actually not being interpolated
(otherwise keep interpolation), "[find_job_folders] OSError: {e}" only if you
will format the exception (otherwise remove f), and "[find_job_folders] Prefix
path doesn't exist!" so that plain string literals are used or proper
.format/f-string interpolation is applied consistently; update the print calls
(in the function find_job_folders) to either drop the f or perform correct
interpolation using the variables referenced (item, e) as appropriate.
```

</details>

</blockquote></details>
<details>
<summary>modules/quote/module.py (1)</summary><blockquote>

`837-848`: **Align ITAR prefix detection to match search module pattern for consistency.**

The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also replaces both `[ITAR] ` and `[ITAR]` patterns, suggesting both formats should be handled consistently.

Update line 839:

```diff
-            is_itar = display_name.startswith('[ITAR]')
+            is_itar = display_name.startswith(('[ITAR] ', '[ITAR-BP] '))
```

This aligns with the search module's pattern and improves clarity about expected prefix formats.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@modules/quote/module.py` around lines 837 - 848, The ITAR prefix detection in
the quote module is inconsistent: update the logic around display_name and
is_itar to mirror the search module pattern by checking
display_name.startswith(('[ITAR] ', '[ITAR-BP] ')) and adjust downstream
customer extraction to remove the matching prefix(s) (e.g., strip the bracketed
prefix plus trailing space) before building bp_dir/customer_bp; make this change
in the block that defines display_name, is_itar, customer and bp_dir so folder
resolution uses the consistent prefix detection used elsewhere.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Around line 31-32: The summary claim "All 16 fixes applied" contradicts the
note that the change to old/test-scripts/test_ui_loading.py (finding 15) was
only local and not committed; update the document so the applied-count and
finding status match: either remove the filename from the applied list and
change "All 16 fixes applied" to "15 fixes applied" or mark finding 15 as
unresolved/not applied and keep the count at 16 but clearly label that file as
local-only; reference the finding identifier "finding 15" and the file name
"old/test-scripts/test_ui_loading.py" when making the edit.

In `@build_scripts/JobDocs.spec`:
- Around line 59-60: The frozen/stable build is still attempting to load the
PSM-only module 'reporting'; update the module discovery/loading logic to skip
any module in PSM_ONLY_MODULES when running in frozen mode. Specifically modify
core/module_loader.py (the load_all_modules function and the module discovery
path used at lines ~52-64) to check the PSM_ONLY_MODULES set and skip importing
modules whose names (e.g., 'reporting' / modules.reporting) are present, using
the existing frozen-mode indicator (or is_frozen flag) so frozen builds do not
attempt to import excluded modules or their UI assets.

In `@modules/job/module.py`:
- Around line 408-418: The code currently logs PermissionError after a failed
shutil.copy2 but still proceeds to call create_file_link with bp_dest that may
not exist; update the block in the routine where is_blueprint_file(...) is
handled so that after catching PermissionError (or any copy failure) you do not
call create_file_link(job_dest, bp_dest, link_type) — i.e., only call
create_file_link when bp_dest.exists() (or when the copy succeeded); use the
existing bp_dest/job_dest variables and the PermissionError handling path in
this function to short-circuit or continue so links are never created from a
missing bp_dest.
- Around line 876-910: The fallback to the base blueprints directory ignores
whether the user is ITAR and always uses 'blueprints_dir', causing ITAR users to
land in the wrong folder; ensure the same is_itar decision is used for the
fallback by initializing is_itar (e.g., False) before the selection logic,
updating it when you inspect the tree item or customer_combo, and then when
computing the final bp_dir for the fallback call to self.app_context.get_setting
use 'itar_blueprints_dir' if is_itar else 'blueprints_dir' (the symbols to look
for are folder_to_open, is_itar, bp_dir, customer_bp,
self.app_context.get_setting and show_error).

---

Outside diff comments:
In `@modules/job/module.py`:
- Around line 645-666: Before clearing and performing the synchronous search in
search_jobs, cancel and wait for any active tree worker using the same
cancel/wait logic used elsewhere (the block that cancels the running tree worker
and waits for it to finish) so queued customer_loaded emissions can't repopulate
self.job_tree; integrate that cancel/wait call at the start of search_jobs
(before self.job_tree.clear()) to ensure refresh_job_tree or any running worker
is stopped prior to the synchronous search.

---

Nitpick comments:
In `@core/app_context.py`:
- Around line 311-318: The print statements inside find_job_folders use
unnecessary f-string prefixes for messages with no interpolation; remove the
leading f from the string literals in the calls that print "[find_job_folders]  
✗ Path doesn't exist", "[find_job_folders]   Found job (no suffix): {item}" only
if {item} is actually not being interpolated (otherwise keep interpolation),
"[find_job_folders] OSError: {e}" only if you will format the exception
(otherwise remove f), and "[find_job_folders] Prefix path doesn't exist!" so
that plain string literals are used or proper .format/f-string interpolation is
applied consistently; update the print calls (in the function find_job_folders)
to either drop the f or perform correct interpolation using the variables
referenced (item, e) as appropriate.

In `@modules/quote/module.py`:
- Around line 837-848: The ITAR prefix detection in the quote module is
inconsistent: update the logic around display_name and is_itar to mirror the
search module pattern by checking display_name.startswith(('[ITAR] ', '[ITAR-BP]
')) and adjust downstream customer extraction to remove the matching prefix(s)
(e.g., strip the bracketed prefix plus trailing space) before building
bp_dir/customer_bp; make this change in the block that defines display_name,
is_itar, customer and bp_dir so folder resolution uses the consistent prefix
detection used elsewhere.
```

</details>

<details>
<summary>🪄 Autofix (Beta)</summary>

Fix all unresolved CodeRabbit comments on this PR:

- [ ] <!-- {"checkboxId": "4b0d0e0a-96d7-4f10-b296-3a18ea78f0b9"} --> Push a commit to this branch (recommended)
- [ ] <!-- {"checkboxId": "ff5b1114-7d8c-49e6-8ac1-43f82af23a33"} --> Create a new PR with the fixes

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: defaults

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `2685cbd7-82e2-419c-aeb4-56c9a85227fb`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 98817da82ab297be07537bcb77a67062e0545ad7 and 25c795501f4654ebc73fe1e87a1c727a06404e50.

</details>

<details>
<summary>📒 Files selected for processing (13)</summary>

* `.claude/S&P.md`
* `.github/workflows/log-coderabbit-review.yml`
* `build_scripts/JobDocs.spec`
* `build_scripts/build_linux.sh`
* `build_scripts/build_windows.bat`
* `core/app_context.py`
* `experimental/db_integration.py`
* `main.py`
* `modules/job/module.py`
* `modules/quote/module.py`
* `modules/search/module.py`
* `old/test-scripts/test_ui_loading.py`
* `pyrightconfig.json`

</details>

<details>
<summary>💤 Files with no reviewable changes (2)</summary>

* pyrightconfig.json
* main.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review`

**Actionable comments posted: 2**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 150: Markdownlint MD040 flags four fenced code blocks in .claude/S&P.md
that lack language identifiers; update each opening fence reported (the four
occurrences flagged) to include a language token (e.g., change ``` to ```text)
so each fenced block has a language specifier, ensuring you apply the same
change to all four openings.
- Line 217: Remove the extra spaces inside the inline code span around the ITAR
token (e.g., change ` [ITAR] ` to `[ITAR]`) to satisfy MD038; while here, make
the detection and replacement consistent with the search module by using the
same pattern checks and replacements (use startswith(('[ITAR] ', '[ITAR-BP] '))
where the code currently uses startswith('[ITAR]') and ensure both '[ITAR] ' and
'[ITAR]' variants are handled in the string replacement logic so behavior
matches the other module).
````

</details>

<details>
<summary>🪄 Autofix (Beta)</summary>

Fix all unresolved CodeRabbit comments on this PR:

- [ ] <!-- {"checkboxId": "4b0d0e0a-96d7-4f10-b296-3a18ea78f0b9"} --> Push a commit to this branch (recommended)
- [ ] <!-- {"checkboxId": "ff5b1114-7d8c-49e6-8ac1-43f82af23a33"} --> Create a new PR with the fixes

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: defaults

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `b1a39c2d-dd5c-4ae6-b35c-b6434ad71515`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 25c795501f4654ebc73fe1e87a1c727a06404e50 and 910cb708457d66c0f9255a29821330b18a3e3f20.

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `.claude/S&P.md`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->
