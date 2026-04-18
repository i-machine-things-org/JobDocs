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
**Result:** 15 fixes applied on `fix/coderabbit-full-review`. Finding 15 (`old/test-scripts/test_ui_loading.py`) not committed — `old/` is gitignored.

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
**⚠️ Outside diff range comments (1)**
>
**modules/job/module.py (1)**
>
> `645-666`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Cancel the active tree worker before running a synchronous search.**
>
> If `refresh_job_tree()` is still loading, its queued `customer_loaded` emissions can repopulate `self.job_tree` after Line 653 clears it, so the search view ends up mixed with stale browse results. Reuse the cancel/wait block from Lines 597-600 before the synchronous search starts.
>
**Suggested fix**
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
> ```text
>
>
>

**🧹 Nitpick comments (2)**

**core/app_context.py (1)**

`311-318`: **Remove extraneous `f` prefixes from strings without placeholders.**

Static analysis correctly identifies these f-strings have no interpolation:

```diff
-                                        print(f"[find_job_folders]     ✗ Path doesn't exist", flush=True)
+                                        print("[find_job_folders]     ✗ Path doesn't exist", flush=True)
```text

```diff
-                        print(f"[find_job_folders] Prefix path doesn't exist!", flush=True)
+                        print("[find_job_folders] Prefix path doesn't exist!", flush=True)
```

Note: Line 268's f-string with `{{po_number}}` is intentional (escaped braces display the literal).

**modules/quote/module.py (1)**

`837-848`: **Align ITAR prefix detection to match search module pattern for consistency.**

The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.

Update line 839:

```diff
-            is_itar = display_name.startswith('[ITAR]')
+            is_itar = display_name.startswith(('[ITAR] ', '[ITAR-BP] '))
```

This aligns with the search module's pattern and improves clarity about expected prefix formats.

---

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 2

**Actionable comments posted: 2**

---

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 3

**Actionable comments posted: 1**

**♻️ Duplicate comments (3)**

**.claude/S&P.md (3)**

`217-217`: _⚠️ Potential issue_ | _🟡 Minor_

**Remove spaces inside inline code span.**

Line 217 has spaces inside the backticks around the ITAR token, triggering MD038. Change `` ` [ITAR] ` `` to `` `[ITAR]` ``.

**📝 Suggested fix**

```diff
-The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
+The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also replaces both `[ITAR]` and `[ITAR]` patterns, suggesting both formats should be handled consistently.
```text

---

`31-96`: _⚠️ Potential issue_ | _🟡 Minor_

**Resolve the contradiction about finding 15's commit status.**

Line 32 states "All 16 fixes applied" but lines 93-96 explicitly note that the change to `old/test-scripts/test_ui_loading.py` (finding 15) was "applied locally but not committed." Either update line 32 to "15 fixes applied" or rephrase to clarify that finding 15 was addressed locally but excluded from the commit.

**📝 Suggested fix**

```diff
-**Result:** All 16 fixes applied on `fix/coderabbit-full-review`.
+**Result:** 15 fixes applied on `fix/coderabbit-full-review`. Finding 15 applied locally only (file gitignored).
```text

---

`150-150`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to fenced code blocks.**

Multiple fenced code blocks lack language identifiers (lines 150, 193, 231, 253, 413), triggering MD040 warnings. Add `text` or an appropriate language identifier after each opening fence.

**📝 Suggested fix**

```diff
-```
+```text
 Verify each finding against the current code and only fix it if needed.
```text

Apply this change to all five occurrences.

Also applies to: 193-193, 231-231, 253-253, 413-413

---

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 4

**Actionable comments posted: 1**

> [!CAUTION]
> Some comments are outside the diff and can’t be posted inline due to platform limitations.
>
>
>
**⚠️ Outside diff range comments (3)**
>
**core/module_loader.py (1)**
>
> `52-64`: _⚠️ Potential issue_ | _🟡 Minor_
>
> **Frozen module list correctly matches spec file; clarify undefined "Rule 3" reference.**
>
> Verification confirms the hardcoded module list aligns with `hiddenimports` in JobDocs.spec—all seven modules are present with their full module paths. The filtering logic correctly handles deprecated modules.
>
> However, the comment on line 54 references "Rule 3" without any definition or documentation in the codebase. Expand this reference inline to clarify what "Rule 3" means, or add a link to external documentation where it is defined. This will help future maintainers understand the rationale for excluding PSM-only modules.
>
> The implicit maintenance coupling between this file and the spec file's `hiddenimports` is unavoidable but acceptable—just ensure any future changes to module lists are coordinated between both locations.
>
>
**modules/quote/module.py (1)**
>
> `802-815`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Link creation not gated by `bp_dest` existence in the "both" destination path.**
>
> Same issue as in `modules/job/module.py`: if the copy to `bp_dest` fails due to `PermissionError`, `bp_dest` won't exist but line 812 still attempts to create a link from it.
>
**Suggested fix**
>
> ```diff
>                  else:  # both
>                      bp_dest = customer_bp / file_name
> +                    bp_ready = bp_dest.exists()
> -                    if not bp_dest.exists():
> +                    if not bp_ready:
>                          try:
>                              shutil.copy2(file_path, bp_dest)
> +                            bp_ready = True
>                          except PermissionError:
>                              self.log_message(f"Warning: Could not copy {file_name} (file in use)")
>
>                      quote_dest = Path(quote_path) / file_name
> -                    if not quote_dest.exists():
> +                    if bp_ready and not quote_dest.exists():
>                          create_file_link(bp_dest, quote_dest, link_type)
>                          added += 1
>                      else:
>                          skipped += 1
> ```text
>
>
**modules/job/module.py (1)**
>
> `849-862`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Link creation not gated by `bp_dest` existence in the "both" destination path.**
>
> If the copy to `bp_dest` fails due to `PermissionError`, `bp_dest` won't exist but line 859 still attempts to create a link from it. This will fail or produce undefined behavior.
>
**Suggested fix**
>
> ```diff
>                  else:  # both
>                      bp_dest = customer_bp / file_name
> +                    bp_ready = bp_dest.exists()
> -                    if not bp_dest.exists():
> +                    if not bp_ready:
>                          try:
>                              shutil.copy2(file_path, bp_dest)
> +                            bp_ready = True
>                          except PermissionError:
>                              self.log_message(f"Warning: Could not copy {file_name} (file in use)")
>
>                      job_dest = Path(job_path) / file_name
> -                    if not job_dest.exists():
> +                    if bp_ready and not job_dest.exists():
>                          create_file_link(bp_dest, job_dest, link_type)
>                          added += 1
>                      else:
>                          skipped += 1
> ```text
>
>
>

**♻️ Duplicate comments (3)**

**.claude/S&P.md (3)**

`406-406`: _⚠️ Potential issue_ | _🟡 Minor_

**Make repeated PR `#6` H2 headings unique.**

Line 406 and Line 482 repeat the same H2 text (already duplicated with Line 106), which keeps triggering MD024.

 

**Suggested edit**

```diff
-## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review`
+## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review` — review run 2

...

-## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review`
+## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review` — review run 3
```text

Also applies to: 482-482

---

`413-413`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to newly added fenced blocks.**

Line 413, Line 514, Line 551, Line 599, and Line 621 still open fenced blocks without a language, so MD040 persists in the new sections.

 

**Suggested edit**

```diff
-````
+```text
 Verify each finding against the current code and only fix it if needed.
 ...
-````
+```
```text

Also applies to: 514-514, 551-551, 599-599, 621-621

---

`217-217`: _⚠️ Potential issue_ | _🟡 Minor_

**Remove internal spacing in inline code span.**

Line 217 still contains a spaced code span variant (`[ITAR]`), which triggers MD038.

 

**Suggested edit**

```diff
-The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
+The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
```text

**🧹 Nitpick comments (1)**

**core/app_context.py (1)**

`268-268`: **Remove extraneous `f` prefix from string literal.**

This f-string has no placeholders—the double braces `{{po_number}}` produce a literal `{po_number}`. Remove the `f` prefix.

```diff
-                    print(f"[find_job_folders] Detected {{po_number}} in prefix, enumerating PO dirs", flush=True)
+                    print("[find_job_folders] Detected {po_number} in prefix, enumerating PO dirs", flush=True)
```text

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 5

**Review:** CodeRabbit re-review after fixes from runs 2-4. Run ID: `025e0b68-45ef-480e-8831-db9dbd3c3d71`
**Result:** 5 fixes applied on `fix/coderabbit-full-review`. Markdown lint issues in S&P.md resolved; code fixes in job/quote/module_loader/app_context applied.

### Findings

1. **Duplicate H2 headings in S&P.md (MD024)** - `.claude/S&P.md`
   - Repeated `## 2026-04-07 -- PR #6...` heading caused MD024 violations
   - Fix: suffix run 2, 3, 4 headings with `-- review run N`

2. **Trailing space inside inline code span (MD038)** - `.claude/S&P.md`
   - Bare backtick-wrapped `[ITAR]` with trailing space triggered MD038
   - Fix: reworded to remove space, applied to all three occurrences

3. **Missing language identifiers on fenced blocks (MD040)** - `.claude/S&P.md`
   - Bare ``` and ```` openers throughout CR review logs lacked language tags
   - Fix: added `text` tag to all opener fences

4. **Link creation not gated by bp_dest existence -- "both" branch** - `modules/job/module.py`, `modules/quote/module.py`
   - If shutil.copy2 raised PermissionError, bp_dest would not exist but create_file_link was still called
   - Fix: introduced bp_ready flag; link only created when copy succeeded or file pre-existed

5. **ITAR fallback in open_blueprints_folder ignored is_itar** - `modules/quote/module.py`
   - Fallback get_setting always used 'blueprints_dir'; ITAR users reached wrong base directory
   - Fix: initialize is_itar=False before selection logic; fallback uses 'itar_blueprints_dir' if is_itar

6. **Ambiguous Rule 3 comment in module_loader.py** - `core/module_loader.py`
   - Comment referenced "Rule 3" without naming the policy doc or noting spec coupling
   - Fix: expanded comment to reference .claude/CLAUDE.md Rule 3 and build_scripts/JobDocs.spec

7. **Unused f-prefix on {{po_number}} print** - `core/app_context.py`
   - Double braces produce literal; f-prefix was redundant
   - Fix: removed f-prefix

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 6

> [!CAUTION]
> Some comments are outside the diff and can’t be posted inline due to platform limitations.
>
>
>
**⚠️ Outside diff range comments (1)**
>
**modules/quote/module.py (1)**
>
> `602-610`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Missing worker cancellation before synchronous search.**
>
> Unlike `search_jobs` in the job module (which now cancels any running worker at lines 653-655), `search_quotes` does not cancel `self._worker` before clearing the tree and performing a synchronous search. If `refresh_quote_tree()` is still loading, its queued `customer_loaded` emissions can repopulate `self.quote_tree` after line 610 clears it, mixing stale browse results with search results.
>
>
**Suggested fix**
>
> ```diff
>      def search_quotes(self):
>          """Search for quotes matching the search term"""
>          search_term = self.add_search_edit.text().strip().lower()
>
>          if not search_term:
>              self.refresh_quote_tree()
>              return
>
> +        if self._worker and self._worker.isRunning():
> +            self._worker.cancel()
> +            self._worker.wait()
> +
>          self.quote_tree.clear()
> ```
>
>
>

**🧹 Nitpick comments (2)**

**.claude/S&P.md (2)**

`1200-1202`: **Minor grammar nit: hyphenate "f-prefix".**

Static analysis flags line 1202. The phrase "removed f prefix" should be "removed f-prefix" (compound modifier).

```diff
-   - Fix: removed f prefix
+   - Fix: removed f-prefix
```

---

`960-992`: **MD038 warning is in a quoted duplicate-comment log entry.**

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 7

**Actionable comments posted: 3**

**♻️ Duplicate comments (1)**

**modules/job/module.py (1)**

`900-916`: _⚠️ Potential issue_ | _🟠 Major_

**Preserve the active ITAR context through the fallback path.**

Line 900 still enters the Create-tab branch whenever no customer-specific folder was found, even if a tree selection already established the context, and Line 903 only updates `is_itar` when `customer` is non-empty. That means an empty customer + checked ITAR box still falls back to `blueprints_dir`, and a missing tree folder can be replaced by stale Create-tab state instead of the selected ITAR base.

 

**Suggested fix**

```diff
-        if not folder_to_open and self.customer_combo:
+        elif self.customer_combo:
+            is_itar = self.itar_check.isChecked() if self.itar_check else False
             customer = self.customer_combo.currentText().strip()
             if customer:
-                is_itar = self.itar_check.isChecked() if self.itar_check else False
                 bp_dir = self.app_context.get_setting(
                     'itar_blueprints_dir' if is_itar else 'blueprints_dir', ''
                 )
```

**🧹 Nitpick comments (1)**

**modules/job/module.py (1)**

`659-682`: **Extract the add-tab filter selection into one helper.**

`search_jobs()` now has a second copy of the same radio/customer filtering logic from `refresh_job_tree()`/`JobTreeWorker.run()`. Since this PR is explicitly keeping search and refresh aligned, pulling that branching into one helper will keep the next filter change from drifting again.

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 8

**Actionable comments posted: 2**

**♻️ Duplicate comments (1)**

**.claude/S&P.md (1)**

`1252-1252`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifier to fenced code block.**

This fenced code block lacks a language identifier, triggering MD040. This same issue was flagged in a previous review but remains unresolved.

**📝 Suggested fix**

```diff
-```
+```text
 Verify each finding against the current code and only fix it if needed.
```text

Also applies to: 1289-1289

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 9

**♻️ Duplicate comments (2)**

**.claude/S&P.md (2)**

`1252-1252`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to all remaining fenced code openings (MD040).**

These fences are still opened without a language token. Update each opener to include one (typically `text`; preserve triple vs quadruple backtick style as needed).

**📝 Suggested patch pattern**

```diff
-```
+```text
 Verify each finding against the current code and only fix it if needed.
 ```

-````
+````text
 Verify each finding against the current code and only fix it if needed.
 ````
```

 

Also applies to: 1289-1289, 1465-1465, 1500-1500, 1525-1525, 1688-1688, 1708-1708

---

`1428-1428`: _⚠️ Potential issue_ | _🟡 Minor_

**Make repeated H2 headings unique to resolve MD024.**

Line 1428 and Line 1653 use the same H2 text, which keeps `no-duplicate-heading` failing. Please append a distinct suffix (for example run ID / “review run N”) to one of them.

 

Also applies to: 1653-1653

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 10

**Actionable comments posted: 5**

**♻️ Duplicate comments (1)**

**.claude/S&P.md (1)**

`1897-1897`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifier to fenced code block.**

The quadruple-backtick fence at line 1897 lacks a language identifier, triggering MD040.

**📝 Suggested fix**

```diff
-`````
+`````text
 Verify each finding against the current code and only fix it if needed.
 `````
```text

**🧹 Nitpick comments (1)**

**.claude/S&P.md (1)**

`26-1935`: **Consider running the sanitization script comprehensively on the entire document.**

The PR description mentions `.github/scripts/sanitize_review.py` was created to automatically fix MD040 and MD024 violations. However, multiple review runs continue to flag the same types of violations in newly appended content. The script may not be processing the entire document or handling all fence variants (triple vs quadruple backticks, nested sections).

Consider either:
1. Running the sanitization script on the complete S&P.md file after each append operation
2. Enhancing the script to handle all backtick fence variants and nested prompt sections
3. Adding a pre-commit hook or CI check to prevent these violations from being committed

This would prevent the feedback loop where each review run adds more content that triggers the same lint violations.

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 11

**Actionable comments posted: 1**

---

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 12

**♻️ Duplicate comments (2)**

**.claude/S&P.md (2)**

`1971-1979`: _⚠️ Potential issue_ | _🟡 Minor_

**Add a language identifier to the six-backtick fenced block.**

Line 1971 opens a fenced block with `````` but no language tag, which keeps MD040 active in this section.

 

**🛠️ Suggested fix**

```diff
-``````
+``````text
 Verify each finding against the current code and only fix it if needed.
 ...
 ``````
```

---

`1976-1977`: _⚠️ Potential issue_ | _🟡 Minor_

**Avoid ambiguous inline backtick spans in prompt prose.**

Line 1976 and Line 1977 still use backtick-heavy inline literals that trigger MD038. Prefer plain wording (e.g., “five-backtick opener + text”) instead of raw fence literals.

 

**🛠️ Suggested fix**

```diff
-block is properly classified (e.g., change the opening fence to `````text or
-`````bash); update only the opening fence near the existing ````` to include the
+block is properly classified (e.g., change the opening fence to five-backtick + `text` or `bash`);
+update only the opening fence near the existing five-backtick marker to include the
```

---

---

## 2026-04-08 — `PR #7: fix: remove inspection reports feature` — review run 1

**🧹 Nitpick comments (2)**

**modules/quote/module.py (1)**

`497-510`: **Remove stale “report(s)” wording from link log message.**

Line 510 still mentions reports, which contradicts the drawings-only behavior and this PR’s objective.

**Proposed text fix**

```diff
-                    self.log_message(f"Linked {files_added} drawing(s)/report(s)")
+                    self.log_message(f"Linked {files_added} drawing(s)")
```

**modules/job/module.py (1)**

`531-544`: **Update link log message to match drawings-only behavior.**

Line 544 still contains “report(s)”, which is inconsistent with the updated dialog purpose.

**Proposed text fix**

```diff
-                    self.log_message(f"Linked {files_added} drawing(s)/report(s)")
+                    self.log_message(f"Linked {files_added} drawing(s)")
```

---

---

## 2026-04-09 — `PR #9: ci: add build-release workflow for signed Windows exe` — review run 1

**Actionable comments posted: 4**

**🧹 Nitpick comments (1)**

**.github/workflows/build-release.yml (1)**

`16-16`: **Pin GitHub Actions to commit SHAs.**

Floating major version tags (`@v4`, `@v5`, `@v2`) weaken supply-chain guarantees. Pin to full commit SHAs for `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and `softprops/action-gh-release`.

---

---

## 2026-04-09 — `.github/workflows/build-release.yml` (PR #9: build-release workflow — review run 1)

**Review:** CODERABBIT FINDINGS ON INITIAL BUILD-RELEASE WORKFLOW
**Result:** All 4 actionable findings fixed; 1 nitpick (SHA pinning) deferred

### Findings

1. **MD040 — Missing language identifier on code fence in CLAUDE.md**
   - Code fence for `git tag` commands lacked a language identifier
   - Fix: added `bash` to opening fence

2. **No stable-ancestry guard on tag trigger**
   - Workflow could fire on tags pushed from any branch, including PSM-stable
   - Fix: added `verify-stable-ancestry` job that runs `git merge-base --is-ancestor origin/stable $GITHUB_SHA` before build

3. **Dependency version mismatch — PyMuPDF pinned loosely in workflow**
   - Workflow used `PyMuPDF>=1.23.0`; `requirements.txt` pins `pymupdf>=1.24.0,<1.25.0`
   - Fix: changed install step to `pip install -r requirements.txt` to match tested baseline

4. **SignPath step ordering — unsigned artifact must upload before signing**
   - SignPath action reads from an uploaded artifact; release should use signed output
   - Fix: moved `upload-artifact` before the SignPath block; added commented `download-artifact` scaffold for when signing is enabled

5. **Nitpick — Pin GitHub Actions to commit SHAs (deferred)**
   - Floating major version tags (`@v4`, `@v5`, `@v2`) weaken supply-chain guarantees
   - Deferred: acceptable risk for now; revisit when SHA pinning tooling is in place

---

## 2026-04-12 — `PR #12: ci: add Linux Flatpak build to release workflow` — review run 1

**Actionable comments posted: 3**

> [!CAUTION]
> Some comments are outside the diff and can’t be posted inline due to platform limitations.
> 
> 
> 
**⚠️ Outside diff range comments (1)**
> 
**.github/workflows/build-release.yml (1)**
> 
> `29-33`: _⚠️ Potential issue_ | _🟠 Major_
> 
> **Drop repository write scope from the build jobs.**
> 
> These jobs only read the repo and upload artifacts; neither operation requires `contents: write`. Keeping this scope on them increases blast radius if any build step, action, or dependency is compromised. Only `create-release` needs it to publish the GitHub Release.
> 
> 
> 
**Suggested change**
> 
> ```diff
>    build-windows:
>      needs: verify-stable-ancestry
>      runs-on: windows-latest
>      permissions:
> -      contents: write
> +      contents: read
> @@
>    build-flatpak:
>      needs: verify-stable-ancestry
>      runs-on: ubuntu-latest
>      permissions:
> -      contents: write
> +      contents: read
> ```
> 
> Also applies to: 92-96
> 
> 
> 

**🧹 Nitpick comments (1)**

**.github/workflows/build-release.yml (1)**

`61-66`: **Avoid uploading the same EXE twice while signing is disabled.**

`JobDocs-unsigned` and `JobDocs-windows` currently contain the same `build_dist/JobDocs.exe`. Keeping one artifact until SignPath is enabled will simplify the release flow and cut redundant upload/storage cost.

**Possible cleanup**

```diff
-      - name: Upload unsigned artifact
-        uses: actions/upload-artifact@v4
-        with:
-          name: JobDocs-unsigned
-          path: build_dist/JobDocs.exe
-
       # -----------------------------------------------------------------------
       # SignPath code signing — uncomment once SignPath Foundation is approved
       # Apply at: https://signpath.io/product/open-source
       # After enabling: update the create-release step to use JobDocs-signed
       # -----------------------------------------------------------------------
```

Also applies to: 83-87

---

## 2026-04-12 — `.github/workflows/build-release.yml` + `linux/flatpak/` (Flatpak build additions)

**Review:** PR #12 — ci: add Linux Flatpak build to release workflow
**Result:** 4 findings (1 critical, 3 major). Critical and two majors fixed; one major acknowledged with documented TODO.

### Findings

1. **Critical — `metainfo-license-missing` (appstreamcli validation failure)**
   - AppStream metainfo requires both `<metadata_license>` and `<project_license>` or `flatpak-builder` aborts during `appstreamcli compose`.
   - Fix: added `<metadata_license>CC0-1.0</metadata_license>` and `<project_license>MIT</project_license>` to `io.github.i_machine_things.JobDocs.metainfo.xml`.
   - Confirmed: local `appstreamcli compose` passes after fix.

2. **Major — glibc ABI mismatch between runner and Flatpak runtime**
   - PyInstaller binary built on `ubuntu-latest` bundles host system libs (e.g. `libsystemd.so.0`) requiring a newer `GLIBC` version than the pinned Flatpak runtime provides.
   - CR suggested building inside the Flatpak SDK; fix applied instead: upgraded manifest and CI cache key from `org.freedesktop.Platform//23.08` to `//24.08` (glibc 2.40), which covers the runner's requirements.
   - Confirmed: app launches cleanly under the 24.08 sandbox locally.

3. **Major — `--filesystem=home` grants unrestricted home access in Flatpak sandbox**
   - Overly broad permission exposes unrelated files; Flathub would reject this.
   - Root cause: `core/settings_dialog.py` uses `QFileDialog` directly without the XDG FileChooser portal, so the app must be able to access any user-selected directory.
   - Acknowledged: `--filesystem=home` kept for now with an inline TODO comment. Portal-based dir picker should replace it in a future refactor.

4. **Major (outside diff) — `contents: write` on build-only jobs**
   - `build-windows` and `build-flatpak` only checkout code and upload artifacts; neither needs write access to repository contents.
   - Fix: narrowed both jobs to `permissions: contents: read`. Only `create-release` retains `contents: write`.

---

## 2026-04-13 — `PR #14: build: convert to onedir and add Inno Setup Windows installer` — review run 1

**Actionable comments posted: 1**

**🧹 Nitpick comments (1)**

**.github/workflows/build-release.yml (1)**

`77-81`: **Provision or at least assert `iscc` before invoking it.**

Line 80 invokes `iscc build_scripts\JobDocs.iss` without installing or validating Inno Setup. This makes the Windows release job depend on the hosted runner image's toolset rather than a declared build dependency, which risks pipeline failures if the image configuration changes.

**♻️ Minimal guard**

```diff
+      - name: Verify Inno Setup is available
+        run: |
+          if (!(Get-Command iscc -ErrorAction SilentlyContinue)) {
+            Write-Error "iscc not found on PATH"
+            exit 1
+          }
+        shell: pwsh
+
       - name: Build Windows installer
         run: |
           $env:RELEASE_VERSION = "${{ github.ref_name }}"
           iscc build_scripts\JobDocs.iss
         shell: pwsh
```

---

---

## 2026-04-13 — `.github/workflows/build-release.yml` (onedir build + Inno Setup, PR #14)

**Review:** Two findings from CodeRabbit on PR #14.
**Result:** Both fixed before merge.

### Findings

1. **iscc invoked without asserting Inno Setup is on PATH**
   - `iscc` called directly in the Build Windows installer step with no guard
   - Added a prior step: `Get-Command iscc -ErrorAction SilentlyContinue` — installs via choco if missing
   - Pattern: always guard external tools not installed by `pip install` or `apt-get`

2. **Flatpak staging copied only the PyInstaller launcher, not the onedir runtime tree**
   - `cp dist/JobDocs/JobDocs linux/flatpak/JobDocs` staged only the binary; onedir requires all `.so` files and data
   - Fixed staging to `cp -r dist/JobDocs linux/flatpak/JobDocs_dir`
   - Updated manifest source from `type: file` to `type: dir, path: JobDocs_dir`
   - Updated build-commands: `cp -r . /app/lib/JobDocs/` + `ln -s /app/lib/JobDocs/JobDocs /app/bin/JobDocs`
   - Pattern: when switching PyInstaller from onefile to onedir, update every downstream consumer of the binary path (Flatpak staging, manifest, verify steps)

---

## 2026-04-13 — `PR #16: feat: plugins directory with GitHub install support` — review run 1

**Actionable comments posted: 4**

---

---

## 2026-04-13 — `core/module_loader.py`, `core/settings_dialog.py` (PR #16 CR resolutions)

**Review:** 4 actionable findings from CodeRabbit on PR #16 (plugins directory feature)
**Result:** All 4 findings fixed in commits `fd8b1fa` and `e4b8e2e`

### Findings

1. **Wrap plugin dir scans in OSError/PermissionError handlers** (`module_loader.py`)
   - Both frozen and dev-mode `iterdir()` loops must catch `OSError`/`PermissionError` per item and per directory
   - Log with context via `logger.warning(...)` and continue — never abort built-in module discovery
   - Add `import logging` and `logger = logging.getLogger(__name__)` at module level

2. **Register parent package before exec_module for relative imports** (`module_loader.py`)
   - External plugins that use `from .helpers import ...` fail because no parent package is in `sys.modules`
   - Before creating the spec, register `plugins.<module_name>` as a `types.ModuleType` with `__path__` set to the plugin dir
   - Pass `submodule_search_locations=[str(module_path.parent)]` to `spec_from_file_location`
   - Add `import types` at module level

3. **Persist plugins_dir before install, not only on Save** (`settings_dialog.py`)
   - `_install_github_plugin` reads `plugins_dir_edit.text()` but never writes to `self.settings`
   - Add `self.settings['plugins_dir'] = plugins_dir_str` immediately after validation so the value survives dialog close without Save

4. **Move download/extract to background QThread** (`settings_dialog.py`)
   - `urllib.request.urlopen`, `resp.read()`, `zipfile.ZipFile`, `shutil.copytree` all ran on the GUI thread — freezes the UI
   - Extract into `_PluginInstallWorker(QThread)` with `success = pyqtSignal(str, str)` and `error = pyqtSignal(str)`
   - GUI handler disables the Install button, starts the worker, reconnects signals to `_on_plugin_install_success` / `_on_plugin_install_error` which re-enable the button and show dialogs
   - Add `import urllib.error` (explicit) and `from PyQt6.QtCore import QThread, pyqtSignal`

---

## 2026-04-13 — `PR #16: feat: plugins directory with GitHub install support` — review run 2

**Actionable comments posted: 1**

**♻️ Duplicate comments (1)**

**core/settings_dialog.py (1)**

`420-421`: _⚠️ Potential issue_ | _🟠 Major_

**Persist `plugins_dir` through the real settings store here.**

`self.settings` is only the dialog-local copy created in `__init__`, so this assignment is still lost if the user installs successfully and then closes with Cancel. The success path says “restart” even though next startup will still read the old persisted `plugins_dir`.

---

---

## 2026-04-14 — `PR #16: feat: plugins directory with GitHub install support` — review run 1

**Actionable comments posted: 3**

---

---

## 2026-04-14 — `PR #16: feat: plugins directory with GitHub install support` — review run 2

**♻️ Duplicate comments (2)**

**core/settings_dialog.py (2)**

`97-99`: _⚠️ Potential issue_ | _🟠 Major_

**Preserve the current plugin until the final swap succeeds.**

Line 98 deletes the live plugin before Line 99 is guaranteed to succeed. If rename fails, users lose the working plugin.

  

**Proposed safer swap (with rollback)**

```diff
                         tmp_dest = dest.with_name(dest.name + '.tmp')
+                        backup_dest = dest.with_name(dest.name + '.bak')
                         try:
                             if tmp_dest.exists():
                                 shutil.rmtree(tmp_dest)
+                            if backup_dest.exists():
+                                shutil.rmtree(backup_dest, ignore_errors=True)
                             shutil.copytree(src, tmp_dest)
                             if dest.exists():
-                                shutil.rmtree(dest)
+                                dest.rename(backup_dest)
                             tmp_dest.rename(dest)
+                            if backup_dest.exists():
+                                shutil.rmtree(backup_dest, ignore_errors=True)
                         except Exception:
+                            if tmp_dest.exists():
+                                shutil.rmtree(tmp_dest, ignore_errors=True)
+                            if backup_dest.exists() and not dest.exists():
+                                backup_dest.rename(dest)
-                            if tmp_dest.exists():
-                                shutil.rmtree(tmp_dest, ignore_errors=True)
                             raise
```

```shell
#!/bin/bash
# Verify current non-rollback swap flow in worker
sed -n '90,110p' core/settings_dialog.py
```

---

`438-443`: _⚠️ Potential issue_ | _🟠 Major_

**Block dialog edits/close while plugin install worker is running.**

Only the Install button is disabled. Users can still Save/Cancel/close, which can race worker callbacks against disposed UI state.

  

**Proposed guard for in-flight install lifecycle**

```diff
 class SettingsDialog(QDialog):
@@
     def __init__(self, settings: Dict[str, Any], parent=None, available_modules: List[tuple] = None,
                  save_callback=None, plugins_dir: Path = None):
@@
         self._plugins_dir = plugins_dir
+        self._install_in_progress = False
@@
-        button_box = QDialogButtonBox(
+        self.button_box = QDialogButtonBox(
             QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
         )
-        button_box.accepted.connect(self.save)
-        button_box.rejected.connect(self.reject)
-        main_layout.addWidget(button_box)
+        self.button_box.accepted.connect(self.save)
+        self.button_box.rejected.connect(self.reject)
+        main_layout.addWidget(self.button_box)
@@
         self.github_install_btn.setEnabled(False)
+        self._install_in_progress = True
+        self.github_repo_edit.setEnabled(False)
+        self.button_box.setEnabled(False)
         worker = _PluginInstallWorker(owner, repo, self._plugins_dir)
@@
         self.github_install_btn.setEnabled(True)
+        self._install_in_progress = False
+        self.github_repo_edit.setEnabled(True)
+        self.button_box.setEnabled(True)
@@
         self.github_install_btn.setEnabled(True)
+        self._install_in_progress = False
+        self.github_repo_edit.setEnabled(True)
+        self.button_box.setEnabled(True)
         QMessageBox.critical(self, "Install Plugin", message)
         worker.deleteLater()
+
+    def reject(self):
+        if self._install_in_progress:
+            QMessageBox.information(self, "Install Plugin", "Please wait for install to finish.")
+            return
+        super().reject()
```

```shell
#!/bin/bash
# Verify install-state handling and whether Save/Cancel/close are guarded
rg -n -C2 "github_install_btn.setEnabled|button_box|def reject|_install_in_progress|worker.start" core/settings_dialog.py
```

Also applies to: 445-459

---

---

## 2026-04-14 — `PR #17: fix: add difflib to hiddenimports for plugin compatibility` — review run 1

**Actionable comments posted: 1**

---

---

## 2026-04-14 — `PR #18: fix: bundle pandas/openpyxl for plugins and restore plugin installer` — review run 1

**Actionable comments posted: 4**

---

---

## 2026-04-14 — `PR #19: fix: isolate plugin deps into plugin-local deps/ directory` — review run 1

**Actionable comments posted: 4**

---

---

## 2026-04-14 — `main.py` (plugin dep installer — PR #19 findings)

**Review:** CodeRabbit flagged three actionable issues in `_install_deps`.
**Result:** All three fixed in commit `dad24fb`.

### Findings

1. **Atomic install via temp directory**
   - Pip into `deps.tmp/` first, then backup-then-swap into `deps/` on success.
   - Prevents stale/partial packages if install fails mid-way.
   - Fix applied: backup-then-swap pattern identical to plugin install in `run()`.

2. **Manual recovery command missing `--target`**
   - Error message said `pip install -r req_file`, which installs globally.
   - Fix applied: changed to `pip install --target "{deps_dir}" -r "{req_file}"`.

3. **Frozen mode: try bundled pip before system Python**
   - System Python may have a different ABI than the bundled Python, causing binary wheels to be incompatible.
   - Fix applied: in frozen mode, attempt `pip._internal.cli.main` first; fall back to `python`/`py` on PATH only after that fails.

---

## 2026-04-14 — `PR #20: build: replace PyInstaller with embedded Python for Windows` — review run 1

**Actionable comments posted: 4**

**🧹 Nitpick comments (3)**

**.gitignore (1)**

`54-54`: **Consider anchoring `AddonPackages/` to repo root.**

If this is only meant for the root-level dev symlink, use `/AddonPackages/` to avoid unintentionally ignoring same-named nested directories.  

**Diff suggestion**

```diff
-AddonPackages/
+/AddonPackages/
```

**build_scripts/JobDocs.spec (1)**

`156-166`: **Refresh this note to match the current plugin install model.**

This block still describes the removed `deps/` + `sys.path` flow, but `main.py` now shells out to `python -m pip install -r ...` into the active environment. Leaving the old description here will send the next person debugging packaging down the wrong path.

**launcher/launcher.rc (1)**

`11-12`: **Drive the EXE version metadata from the build, not a literal.**

The installer version already comes from `RELEASE_VERSION`, but the launcher resource is pinned to `0.6.0.0`. The next tag will ship an EXE whose file properties disagree with the installer and release asset name unless this is updated by hand. 

Also applies to: 25-30

---

## 2026-04-15 — multiple files (PR #20 — embedded Python build findings)

**Review:** CodeRabbit flagged 4 actionable issues and 3 nitpicks across the embedded-Python build PR.
**Result:** All 7 fixed in this session.

### Findings

1. **No hash verification on downloaded Python embeddable**
   - `build-release.yml` downloaded `python-$PY_VER-embed-amd64.zip` without verifying integrity.
   - Fix applied: pinned `PY_EMBED_SHA256` env var (from python.org sigstore); added `Get-FileHash` check before `Expand-Archive`; fails fast on mismatch.

2. **get-pip.py fetched from network without verification**
   - Downloading `get-pip.py` from `bootstrap.pypa.io` at build time is an unverified external fetch.
   - Fix applied: replaced with `python -m pip install --target runtime\Lib\site-packages pip` using the system Python already installed on `windows-latest`, eliminating the external download entirely.

3. **README.md missing from staged app source tree**
   - `show_readme()` resolves `README.md` relative to `__file__`; it was absent from the `$src_items` copy list so Help → User Guide would fail in packaged builds.
   - Fix applied: added `'README.md'` to `$src_items` in the Stage app source tree step.

4. **`CreateProcessW` return value not checked in launcher.c**
   - Failures were silently swallowed; `CloseHandle` was called unconditionally on possibly-invalid handles.
   - Fix applied: captured BOOL return; on failure calls `GetLastError()`, shows `MessageBoxW` with Python path, script path, and error code, then returns 1. `CloseHandle` is now only reached on success.

5. **Flatpak `/app` is read-only at runtime — `_install_deps` would always fail**
   - `_install_deps` calls `pip install` using `sys.executable`, which on Flatpak points to a location under read-only `/app`.
   - Fix applied: added `os.getenv('FLATPAK_ID')` check; returns a clear skip message with manual install command instead of invoking pip.

6. **`AddonPackages/` in .gitignore not anchored to repo root**
   - Unanchored pattern would silently ignore same-named nested directories.
   - Fix applied: changed to `/AddonPackages/`.

7. **`launcher.rc` version hardcoded to `0.6.0.0`**
   - EXE file properties would disagree with the installer/release tag after a version bump.
   - Fix applied: added preprocessor macros (`VERSION_MAJOR/MINOR/PATCH/BUILD`) with fallback defaults; updated `FILEVERSION`, `PRODUCTVERSION`, and string values to use `VER_STRING` macro; `build-release.yml` Compile Launcher step now parses `github.ref_name` and passes `-D VERSION_*` to windres.

8. **Stale comment in `JobDocs.spec` described removed `deps/`+`sys.path` plugin model**
   - Comment referenced the old `pip install --target deps/` flow that no longer exists.
   - Fix applied: reworded to describe current model (pip install into running Python environment).

---

## 2026-04-15 — `PR #20: build: replace PyInstaller with embedded Python for Windows` — review run 1

**♻️ Duplicate comments (2)**

**main.py (1)**

`399-414`: _⚠️ Potential issue_ | _🟠 Major_

**Flatpak still resolves plugins into the bundled app tree.**

This only distinguishes the embedded-Windows layout from source layout. The Linux release is still a Flatpak, so `_get_plugins_dir()` will resolve next to the frozen bundle, and `_PluginInstallWorker` then tries to create/copy plugin files there before `_install_deps()` runs. In Flatpak, the app bundle under `/app` is read-only, while per-user data belongs under `$XDG_DATA_HOME` / `~/.var/app/$FLATPAK_ID/data`, so plugin install remains broken on Linux. Return a per-user writable path when `FLATPAK_ID` is set, or disable plugin installation in that mode. ([docs.flatpak.org](https://docs.flatpak.org/zh-cn/latest/sandbox-permissions.html?utm_source=openai))

**.github/workflows/build-release.yml (1)**

`35-76`: _⚠️ Potential issue_ | _🟠 Major_

**Pin the pip bootstrap input.**

`python -m pip install --target ... pip` still pulls whatever stable `pip` release PyPI serves on build day, and the `python` binary itself comes from the mutable `windows-latest` image. That makes the Windows installer drift over time even when the repo hasn’t changed. Please bootstrap from a pinned wheel or at least a pinned `pip==...` plus hash, and use a specific runner/interpreter for that download step. GitHub notes that `-latest` images migrate over time and recommends `actions/setup-python` for consistent behavior; pip installs stable releases by default when no version is specified. ([github.com](https://github.com/actions/runner-images?utm_source=openai))

---

---

## 2026-04-15 — `main.py` + `build-release.yml` (PR #20 duplicate findings — Flatpak plugins dir & pip pinning)

**Review:** CodeRabbit flagged 2 issues as duplicate comments (carried forward from first review pass, not fully resolved by `1c57a11`).
**Result:** Both fixed.

### Findings

1. **`_get_plugins_dir()` resolves into read-only Flatpak bundle**
   - On Flatpak, `__file__` is under `/app` which is read-only at runtime.
   - `_get_plugins_dir()` would return `/app/plugins`, causing plugin install to fail silently.
   - Fix applied: check `FLATPAK_ID` env var; if set, return `$XDG_DATA_HOME/plugins` (or `~/.var/app/{FLATPAK_ID}/data/plugins` as fallback).

2. **pip bootstrap in `build-release.yml` uses unpinned version with mutable system Python**
   - `python -m pip install ... pip` pulls whatever pip PyPI serves on build day.
   - System `python` comes from the mutable `windows-latest` image.
   - Fix applied: added `actions/setup-python@v5` step (pinned to `python-version: '3.12'`); pinned pip to `pip==24.3.1` in the install command.

---

## 2026-04-15 — `PR #20: build: replace PyInstaller with embedded Python for Windows` — review run 2

**Actionable comments posted: 2**

---

---

## 2026-04-15 — `main.py` (PR #20 review run 2 — pip instructions & dep-warning message)

**Review:** CodeRabbit flagged 2 actionable issues in `_install_deps` and `_on_plugin_install_success`.
**Result:** Both fixed.

### Findings

1. **Manual pip recovery commands use bare `pip` instead of `sys.executable`**
   - Both the Flatpak skip message and the subprocess failure message advised `pip install -r ...`, which resolves to whatever `pip` is first on PATH and may target the wrong interpreter/venv.
   - Fix applied: changed to `{sys.executable} -m pip install -r "{req_file}"` in both strings.

2. **`_on_plugin_install_success` promises "Restart to load it" even when deps failed**
   - When `dep_warning` is set, the base message still said "Restart JobDocs to load it." — misleading because the plugin may not actually load without its dependencies.
   - Fix applied: when `dep_warning` is truthy, base message now reads "files copied… may not load until dependencies are resolved" (QMessageBox.warning); only the success path keeps "Restart JobDocs to load it." (QMessageBox.information).

---

## 2026-04-15 — `PR #20: build: replace PyInstaller with embedded Python for Windows` — review run 3

**Actionable comments posted: 2**

**♻️ Duplicate comments (1)**

**main.py (1)**

`57-63`: _⚠️ Potential issue_ | _🟠 Major_

**Flatpak still surfaces a recovery command that targets the read-only runtime.**

This branch correctly skips auto-install on Flatpak, but the returned `sys.executable -m pip ...` advice still points users at the same sandboxed interpreter you just deemed unwritable. For dependency-backed plugins, that leaves no working recovery path. Either remove the manual command here and state that manual dependency install is unsupported in Flatpak builds, or switch Flatpak to a supported user-writable install target.

---

---

## 2026-04-15 — `main.py` (PR #20 review run 3 — Flatpak recovery command & quoting)

**Review:** CodeRabbit flagged 2 actionable issues (1 duplicate + 1 new inline) and 1 nitpick in `_install_deps`.
**Result:** All 3 fixed.

### Findings

1. **Flatpak recovery command points at read-only `sys.executable`**
   - After using `sys.executable` in the Flatpak skip message, CodeRabbit noted that `sys.executable` IS the sandboxed read-only runtime — so the manual command was also unworkable.
   - Fix applied: removed the pip command entirely; message now states "dependency installation is not supported inside a Flatpak build."

2. **`sys.executable` not quoted in failure recovery command**
   - Paths containing spaces (e.g. `C:\Program Files\...`) would break the copy-paste command.
   - Fix applied: wrapped as `"{sys.executable}"` in the failure message f-string.

3. **Docstring contains invalid escape `runtime\python.exe`**
   - Bare backslash in a regular (non-raw) docstring is an invalid escape sequence.
   - Fix applied: escaped as `runtime\python.exe`.

---

## 2026-04-15 — `PR #20: build: replace PyInstaller with embedded Python for Windows` — review run 4

**🧹 Nitpick comments (1)**

**main.py (1)**

`60-63`: **Remove extraneous `f` prefixes from strings without placeholders.**

Lines 61 and 62 are f-strings but contain no interpolation placeholders. This is flagged by Ruff (F541).

**Suggested fix**

```diff
         if os.getenv('FLATPAK_ID'):
             return (
-                f"\n\nDependency installation is not supported inside a Flatpak build.\n"
-                f"Install the plugin's dependencies on the host system before use."
+                "\n\nDependency installation is not supported inside a Flatpak build.\n"
+                "Install the plugin's dependencies on the host system before use."
             )
```

---

---

## 2026-04-15 — `main.py` (PR #20 review run 4 — unnecessary f-strings)

**Review:** 1 nitpick (Ruff F541).
**Result:** Fixed.

### Findings

1. **F-strings with no placeholders (Ruff F541)**
   - Flatpak return block used `f"..."` on two lines that contain no `{}` interpolation.
   - Fix applied: removed `f` prefixes; plain string literals.

---

## 2026-04-15 — `PR #22: fix: add ../app to embedded Python _pth so launcher works` — review run 1

**Actionable comments posted: 1**

---

---

## 2026-04-15 — `PR #22: fix: add ../app to embedded Python _pth so launcher works` — review run 2

**Actionable comments posted: 1**

---

---

## 2026-04-16 — `PR #24: feat: batch print drawings from job/quote/search` — review run 1

**🧹 Nitpick comments (3)**

**shared/utils.py (2)**

`189-189`: **Redundant import.**

`subprocess` is now imported at module level (line 11), making this local import unnecessary.

**🧹 Remove redundant import**

```diff
 def open_folder(path: str) -> Tuple[bool, Optional[str]]:
     """
     Open a folder in the OS file browser.
 
     Args:
         path: Path to the folder to open
 
     Returns:
         Tuple of (success, error_message)
     """
-    import subprocess
     try:
         if platform.system() == "Windows":
```

---

`206-214`: **Silent failures when printing files.**

The function silently skips non-files and doesn't report errors if `os.startfile()` or `lp` fails. Users won't know if printing failed (e.g., `lp` not installed on Linux, permission denied, or unsupported file type).

Consider returning status information or raising exceptions for critical failures.

**♻️ Suggested improvement with basic error handling**

```diff
-def print_files(paths: List[str]) -> None:
-    """Send each file to the OS print handler (opens the system print dialog)."""
-    for path in paths:
-        if not os.path.isfile(path):
-            continue
-        if platform.system() == 'Windows':
-            os.startfile(path, 'print')  # type: ignore[attr-defined]
-        else:
-            subprocess.Popen(['lp', path])
+def print_files(paths: List[str]) -> Tuple[int, List[str]]:
+    """Send each file to the OS print handler (opens the system print dialog).
+    
+    Returns:
+        Tuple of (success_count, list of error messages)
+    """
+    success = 0
+    errors = []
+    for path in paths:
+        if not os.path.isfile(path):
+            errors.append(f"Not a file: {path}")
+            continue
+        try:
+            if platform.system() == 'Windows':
+                os.startfile(path, 'print')  # type: ignore[attr-defined]
+            else:
+                subprocess.Popen(['lp', path])
+            success += 1
+        except FileNotFoundError:
+            errors.append(f"Print command not found (is 'lp' installed?)")
+        except OSError as e:
+            errors.append(f"Failed to print {path}: {e}")
+    return success, errors
```

Note: The static analysis warnings (S603, S607) about subprocess security are low-risk here since paths originate from user-selected files that pass `os.path.isfile()` validation, but consider using `shutil.which('lp')` to verify availability before attempting to print on non-Windows systems.

**modules/search/module.py (1)**

`759-764`: **Minor UX consideration: Context menu visibility depends on clicked item.**

The "Print Selected" action only appears when right-clicking on a file item (line 759: `if is_file:`). If a user has multiple files selected but right-clicks on a folder row, the print option won't appear.

This is a minor edge case and the current behavior is acceptable, but you could consider showing "Print Selected" whenever there's at least one file in the selection.

---

## 2026-04-16 — `shared/utils.py`, `shared/widgets.py` (PR #24 — batch print)

**Review:** CodeRabbit flagged redundant local `import subprocess` inside `open_folder()` and S603/S607 subprocess security warnings for bare `['lp', path]` call without verifying `lp` availability.
**Result:** Removed redundant local import; guarded `lp` calls with `shutil.which('lp')` in both `utils.py` and `widgets.py`.

### Findings

1. **Redundant local import**
   - `import subprocess` inside `open_folder()` duplicated the module-level import added when `print_files` was introduced
   - Removed the local import

2. **S607 — subprocess called without full path verification**
   - `subprocess.Popen(['lp', path])` could fail silently on systems without `lp`
   - Fixed: `lp = shutil.which('lp'); if lp: Popen([lp, path])`

---

## 2026-04-16 — `PR #24: feat: batch print drawings from job/quote/search` — review run 2

**Actionable comments posted: 2**

**🧹 Nitpick comments (4)**

**shared/widgets.py (3)**

`1380-1393`: **Type hints reference undefined names at module scope.**

The string-based type hints (`'QPainter'`, `'QImage'`, `'QRectF'`) won't cause runtime errors, but static type checkers (mypy, pyright) won't resolve them. Consider using a `TYPE_CHECKING` import block:

**🔧 Proposed fix**

Add near the top of the file with other imports:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtGui import QPainter, QImage
    from PyQt6.QtCore import QRectF
```

Then the function signature can use the actual types without strings:
```diff
-def _draw_image_fitted(painter: 'QPainter', img: 'QImage', page_rect: 'QRectF') -> None:  # type: ignore[name-defined]
+def _draw_image_fitted(painter: QPainter, img: QImage, page_rect: QRectF) -> None:
```

---

`1464-1471`: **Fallback print silently fails on non-Windows if `lp` is unavailable.**

When `lp` is not found via `shutil.which`, non-renderable files are silently skipped with no user feedback. Consider logging a warning or collecting failed paths to report to the user:

**🛡️ Proposed improvement**

```diff
     for path in fallback:
         if platform.system() == 'Windows':
             os.startfile(path, 'print')  # type: ignore[attr-defined]
         else:
             import subprocess as _sp
             lp = shutil.which('lp')
             if lp:
                 _sp.Popen([lp, path])
+            else:
+                # Consider logging or collecting these for user notification
+                print(f"[print_files_with_dialog] lp not found, cannot print: {path}", flush=True)
```

---

`1428-1462`: **Consider wrapping QPainter in try/finally to ensure `end()` is called.**

If an unexpected exception occurs during rendering (e.g., QImage creation fails), `painter.end()` won't be called, which can leave the printer in an inconsistent state.

**🛡️ Proposed fix**

```diff
         painter = QPainter(printer)
-        page_rect = QRectF(painter.viewport())
-        first = True
-
-        for path in renderable:
-            # ... rendering logic ...
-
-        painter.end()
+        try:
+            page_rect = QRectF(painter.viewport())
+            first = True
+
+            for path in renderable:
+                # ... rendering logic ...
+        finally:
+            painter.end()
```

**core/app_context.py (1)**

`87-98`: **Consider adding type hints for the print provider API.**

The provider parameter and return type are untyped. For better IDE support and documentation, consider adding type hints. If you want to keep it flexible for plugins, `Any` or a `Protocol` would work:

```python
from typing import Protocol

class PrintProvider(Protocol):
    def add_files_to_list(self, paths: list) -> None: ...
```

Then: `def register_print_provider(self, provider: PrintProvider | None) -> None`

This is optional but improves discoverability of the expected interface.

---

---

## 2026-04-17 — `shared/widgets.py` (QPrintPreviewDialog render safety)

**Review:** PR #25 — CodeRabbit flagged two actionable bugs in `do_render` and one nitpick.
**Result:** Both actionable items fixed; nitpick logged for future optimisation.

### Findings

1. **Blank pages emitted for unreadable images**
   - `pr.newPage()` and `first = False` were called before `img.isNull()` check, producing blank pages for files that fail to load.
   - Fix: load `QImage` first, `continue` on `isNull()`, only then advance the page counter.

2. **`painter.end()` and `doc.close()` not guaranteed on exception**
   - If `_fitz.open()` or rendering raised inside `do_render`, `painter.end()` was skipped, crashing the print backend. `doc.close()` was also skipped, leaking the file handle.
   - Fix: wrapped QPainter body in `try/finally` for `painter.end()`; wrapped `doc` usage in inner `try/finally` for `doc.close()`; per-file exceptions caught and logged via `logger.warning(..., exc_info=True)`.
   - Added module-level `logger = logging.getLogger(__name__)` to `shared/widgets.py`.

3. **Nitpick — PDF pages re-rasterised on every `paintRequested` emission** *(not yet fixed)*
   - `QPrintPreviewDialog` re-emits `paintRequested` on zoom/layout/resize, causing repeated 200 DPI renders of all PDF pages on the GUI thread.
   - Future fix: pre-render PDF pages to `QImage` cache before connecting the signal; `do_render` blits from cache. Keep full 200 DPI only for the actual print path.

**Actionable comments posted: 2**

**🧹 Nitpick comments (1)**

**shared/widgets.py (1)**

`1473-1477`: **Optimize PDF rendering in preview to avoid repeated rasterization on user interaction.**

`QPrintPreviewDialog` re-emits `paintRequested` whenever the user changes zoom, page layout, orientation, or resizes the dialog. Currently, `do_render` re-opens and rasterizes every PDF page at 200 DPI (line 1452) for each emission, freezing the UI for multi-page documents on the GUI thread.

Cache rendered PDF pages to `QImage` objects before connecting the signal, so `do_render` only blits cached images—or render at a lower preview DPI and perform a full 200 DPI re-render only after the user accepts and prints.

---

---

## 2026-04-17 — `PR #25: feat: print preview dialog` — review run 1

**🧹 Nitpick comments (2)**

**shared/widgets.py (2)**

`1475-1483`: **Minor: consider symmetry with the PDF branch.**

The image path has no local `try/except`, so an unexpected raise from `QImage(path)` or `_draw_image_fitted` would escape `do_render` and (per Qt) risk aborting the app, whereas the PDF branch logs and continues. In practice `QImage(path)` returns a null image rather than raising, so this is very low risk — flagging only for consistency. Feel free to defer.

---

`1427-1436`: **Optional: log when PDFs are demoted to the OS fallback.**

When `fitz` is missing, every `.pdf` is silently moved from `renderable` to `fallback`, which changes user-visible behavior (no preview, OS print dialog instead). Since you now have a module logger, a single warning here would make this traceable in support logs without touching UX.

**♻️ Suggested log statement**

```diff
         try:
             import fitz as _fitz  # pymupdf
         except ImportError:
             _fitz = None
             # PDFs can't be previewed — move them to OS fallback
             for _p in list(renderable):
                 if Path(_p).suffix.lower() == '.pdf':
                     fallback.append(_p)
                     renderable.remove(_p)
+            if any(Path(p).suffix.lower() == '.pdf' for p in fallback):
+                logger.warning(
+                    "pymupdf (fitz) unavailable; PDFs will be sent to the OS "
+                    "print handler without preview."
+                )
```

Also a nit: the `for _p in list(renderable): ... renderable.remove(_p)` pass is O(n²); a single comprehension split would be clearer and linear, e.g. `pdfs, renderable = [p for p in renderable if Path(p).suffix.lower() == '.pdf'], [p for p in renderable if Path(p).suffix.lower() != '.pdf']; fallback.extend(pdfs)`. Trivial given typical list sizes.

---

---

## 2026-04-17 — `PR #25: feat: print preview dialog` — review run 2

**Actionable comments posted: 1**

**🧹 Nitpick comments (1)**

**shared/widgets.py (1)**

`1446-1478`: **Preview cache pre-renders every page of every PDF at 96 DPI into RAM.**

For a multi-PDF selection (or a single long PDF), `preview_cache` can grow large — e.g. a 100-page US-Letter PDF at 96 DPI RGB888 is ~250 MB, and the list holds the full set for the lifetime of the dialog. Images are also fully loaded via `QImage(path)` regardless of size. Consider:

- Capping the number of pre-rendered pages (e.g., first N) and re-rendering on demand for the rest.
- Using a smaller preview DPI (72) or downsampling images above a threshold.
- Rendering lazily inside `do_render` for pages outside a small cached window, keyed by page index.

Not a correctness blocker, but worth addressing before this ships to users who print large multi-page jobs.

---

---

## 2026-04-17 — `PR #25: feat: print preview dialog` — review run 3

**🧹 Nitpick comments (3)**

**shared/widgets.py (3)**

`1556-1565`: **Dead code left from the refactor: `_pw` and `QPrintPreviewWidget` import are unused.**

After moving printing to `_render_to(_print_printer, 200)` on a fresh `QPrinter`, `_pw` is no longer referenced anywhere in `_do_print` (no `_pw.print_()` call remains), and the `QPrintPreviewWidget` import at line 1557 is only used to look it up. Remove both to keep the intent clear.

**♻️ Proposed cleanup**

```diff
             from PyQt6.QtPrintSupport import QPrintPreviewDialog, QPrintDialog
-            from PyQt6.QtPrintSupport import QPrintPreviewWidget
             from PyQt6.QtGui import QKeySequence, QAction

             preview = QPrintPreviewDialog(preview_printer, parent)
             preview.paintRequested.connect(do_render)

             # Intercept the built-in Print toolbar button so we can render at
             # 200 DPI on a native HighResolution printer, not the PDF preview printer.
-            _pw = preview.findChild(QPrintPreviewWidget)
-
             def _do_print() -> None:
```

---

`1495-1554`: **Minor: `do_render` and `_render_to` duplicate the PDF/image dispatch loop.**

`do_render` blits the 48 DPI cache while `_render_to` re-renders from source at 200 DPI. The PDF-vs-image branching, first-page/newPage bookkeeping, and `_draw_image_fitted` plumbing are otherwise structurally identical to the cache-building loop above. Not a correctness issue — `_render_to` is necessary because the cache is too low-res for print — but the three near-identical loops are a maintenance hazard. Consider factoring a helper like `_iter_pages(path, dpi) -> Iterable[QImage]` used by all three call sites.

Also, for very large PDFs the 200 DPI re-render in `_render_to` runs synchronously on the GUI thread inside the print QAction handler, which will freeze the dialog until done. Fine for the common few-page case; worth a progress indicator or `QApplication.processEvents()` tick if large jobs become common.

---

`1575-1587`: **Silent failure if the Print toolbar action doesn't match `StandardKey.Print` — defensive programming.**

In Qt 6 / PyQt6, `QPrintPreviewDialog` reliably binds `QKeySequence.StandardKey.Print` (Ctrl+P) to its built-in Print toolbar `QAction`, and the action is discoverable via `findChildren(QAction)`. However, if this hook fails to install for any reason (e.g., future Qt changes, atypical dialog customization), `_do_print` is never wired up, leaving the user with silent failure: the Print button triggers the default PDF preview printer instead of real-printer output with no error or warning.

Consider adding defensive tracking — either log a warning if the hook is not installed, or add an explicit Print button to the dialog button bar so the real-print path doesn't depend on shortcut discovery.

**🛡️ Defensive: log if hook is not installed**

```diff
+            _hooked = False
             for _act in preview.findChildren(QAction):
                 if _act.shortcut().matches(
                     QKeySequence(QKeySequence.StandardKey.Print)
                 ) == QKeySequence.SequenceMatch.ExactMatch:
                     try:
                         _act.triggered.disconnect()
                     except TypeError:
                         pass
                     _act.triggered.connect(_do_print)
+                    _hooked = True
                     break
+            if not _hooked:
+                logger.warning(
+                    "print_files_with_dialog: could not locate Print toolbar "
+                    "action; toolbar Print will route through the PDF preview "
+                    "printer instead of a real printer."
+                )
```

---

## 2026-04-17 — `shared/widgets.py` (PR #25 run 2 — _hooked flag, dead code, deferred nitpick)

**Review:** CodeRabbit PR #25 run 2 — 1 actionable finding, 1 nitpick
**Result:** Actionable fixed (dead code removed, `_hooked` flag added with warning). Nitpick deferred.

### Findings

1. **Validate `_do_print` hook registration with `_hooked` flag**
   - CodeRabbit: detect whether the `for` loop actually connected `_do_print`; log loudly if no `QAction` was hooked rather than silently falling back to the PDF preview printer.
   - Fix: Added `_hooked = False` before the loop, set `_hooked = True` on match, added `logger.warning(...)` after the loop if `not _hooked`.

2. **Remove dead `_pw` variable and unused `QPrintPreviewWidget` import**
   - `_pw = preview.findChild(QPrintPreviewWidget)` was left over after `_do_print` was refactored to call `_render_to()` directly; `_pw` was never read.
   - Fix: Removed both the import and the dead assignment.

3. **Nitpick: factor three nearly-identical render loops into a helper** *(deferred)*
   - CodeRabbit: `preview_cache` pre-render loop, `do_render` blit loop, and `_render_to` render loop share similar structure; could be extracted to reduce duplication.
   - Decision: deferred — extracting is over-engineering for three call sites with subtly different concerns (pre-cache vs blit vs high-DPI). Log here for future reference.

---

## 2026-04-17 — `shared/widgets.py`, `build_scripts/clean_sp.py`, workflow (PR #25 run 4)

**Review:** CodeRabbit PR #25 run 4 — 4 actionable findings (1 duplicate, 3 new)
**Result:** 3 new findings fixed; duplicate `_hooked` escalation acknowledged but not changed.

### Findings

1. **`clean_sp.py`: heading-reset guard too broad** *(fixed)*

---

## 2026-04-18 — `PR #25: feat: print preview dialog` — review run 1

**Actionable comments posted: 2**

**♻️ Duplicate comments (1)**

**shared/widgets.py (1)**

`1464-1505`: _⚠️ Potential issue_ | _🟠 Major_

**Failed pre-render PDFs are still attempted during the actual print pass.**

`failed_pre_render` records the basename of PDFs that fail pre-rendering, but `renderable` itself is never pruned. When the user prints, `_render_to` (Line 1504) iterates the full `renderable` list and calls `_fitz.open(path)` again on the same bad files. The preview shows N pages (minus the failed PDFs), but the real print job tries to render them a second time — typically adding them to `failed_print_render` and producing a second warning dialog for the same files, and if a transient error caused the first failure the print output can diverge from what the user saw in preview.

**🐛 Suggested fix: filter renderable for the print pass**

```diff
             preview_cache: list[QImage] = []
+            renderable_for_print: list[str] = []
             for path in renderable:
                 ext = Path(path).suffix.lower()
                 if ext == '.pdf' and _fitz is not None:
                     try:
                         doc = _fitz.open(path)
                         try:
+                            _page_imgs: list[QImage] = []
                             for page_num in range(doc.page_count):
                                 pg = doc[page_num]
                                 pix = pg.get_pixmap(
                                     matrix=_fitz.Matrix(
                                         _PREVIEW_DPI / 72, _PREVIEW_DPI / 72
                                     ),
                                     alpha=False,
                                 )
                                 samples = bytes(pix.samples)
-                                preview_cache.append(
+                                _page_imgs.append(
                                     QImage(
                                         samples, pix.width, pix.height,
                                         pix.stride, QImage.Format.Format_RGB888,
                                     ).copy()
                                 )
+                            preview_cache.extend(_page_imgs)
+                            renderable_for_print.append(path)
                         finally:
                             doc.close()
                     except Exception:
                         logger.warning(
                             "print_files_with_dialog: failed to pre-render PDF %s",
                             path, exc_info=True,
                         )
                         failed_pre_render.append(os.path.basename(path))
                 else:
                     img = QImage(path)
                     if not img.isNull():
                         preview_cache.append(img)
+                        renderable_for_print.append(path)
```

Then iterate `renderable_for_print` inside `_render_to`.

**🧹 Nitpick comments (2)**

**shared/widgets.py (1)**

`1622-1644`: **Three stacked `QMessageBox.warning` dialogs on failure paths.**

When a print run has fallback failures plus PDF pre-render failures plus PDF print-render failures, the user dismisses three separate modal warnings back-to-back. Consider consolidating into a single dialog that groups the categories, e.g.:

```
Some files could not be printed:

Not supported by system handler:
  • drawing.dwg

Could not be previewed (skipped):
  • corrupt.pdf

Failed during printing:
  • encrypted.pdf
```

Also, `from PyQt6.QtWidgets import QMessageBox` is repeated three times in the same scope — hoist it once (or to the top of the function) for readability.

**build_scripts/clean_sp.py (1)**

`148-158`: **`lines_before`/`lines_after` count newlines, not lines.**

`str.count('\n')` undercounts by one when the file doesn't end with a newline, and the label "Lines" is slightly misleading. Minor, diagnostic-only. Consider `len(original.splitlines())` for accuracy.

and an opening <details...> on
the same line, so update the logic around the re.search(r' ') branch to
first detect inline openers (e.g., using re.search(r'(?i)<details\b') or
checking parts for '<details') and either (a) route that line through the
opener-handling logic instead of continuing early, or (b) process the line
token-by-token so openers increment skip/depth and closers decrement them in
sequence; ensure the variables skip and depth are updated in the correct order
so the opener branch (the existing opener-handling code that adjusts skip/depth)
runs for inline openers and prevents leaking tag text to out.

In `@shared/widgets.py`:
- Around line 1588-1605: The code currently sets cancelled = True when _hooked
is False inside print_files_with_dialog, causing renderable files to be dropped
instead of sent to the OS fallback; update the branch where _hooked is False to
append the current renderable items to the fallback list (e.g., extend fallback
with renderable or fallback += renderable) before setting cancelled = True so
the OS print fallback (os.startfile('print') / lp) gets a chance to handle them,
and keep the existing QMessageBox warning text unchanged.

---

Duplicate comments:
In `@shared/widgets.py`:
- Around line 1464-1505: The code records failed_pre_render basenames but never
removes those entries from renderable, causing _render_to (function _render_to)
to re-attempt opening the same bad PDFs during printing; fix by filtering
renderable into a new list (e.g., renderable_for_print) excluding any paths
whose basename is in failed_pre_render before the print pass, then iterate
renderable_for_print inside _render_to instead of the original renderable so
PDFs that failed pre-render are skipped during the actual print.

---

Nitpick comments:
In `@build_scripts/clean_sp.py`:
- Around line 148-158: The current lines_before/lines_after use str.count('\n')
which miscounts lines; replace those two assignments to use
len(original.splitlines()) and len(cleaned.splitlines()) respectively (use
splitlines() on the original and cleaned variables), then keep the same print
statement (or adjust the label if you want clearer wording). This change touches
the variables lines_before and lines_after in the block that computes
diagnostics before writing via SP.write_text.

In `@shared/widgets.py`:
- Around line 1622-1644: Consolidate the three separate QMessageBox.warning
calls into a single warning dialog: hoist "from PyQt6.QtWidgets import
QMessageBox" once (top of the function or scope), build a single message body
that conditionally appends the three sections for unprinted, failed_pre_render,
and failed_print_render (use names = '\n'.join(...) as done), and call
QMessageBox.warning(parent, "Print", combined_message) once so users see one
grouped dialog; preserve the existing bullet formatting and sort/deduplicate
failed_print_render as before.
```

---

---

## 2026-04-17 — `shared/widgets.py`, `build_scripts/clean_sp.py` (PR #25 run 6)

**Review:** CodeRabbit PR #25 run 6 — 2 actionable findings
**Result:** Both fixed.

### Findings

1. **`clean_sp.py`: inline `<details>` opener after `</details>` closer silently dropped** *(fixed)*
   - A line with both a closer and an opener (e.g. `</details><details>`) was handled by the closer branch which did `continue`, never reaching the opener branch.
   - Fix: after processing closers, fall through to the opener branch if the tail segment contains a `<details>` opener.

2. **`shared/widgets.py`: renderable files silently dropped when `_hooked=False`** *(fixed)*
   - When the Print toolbar action could not be hooked, `cancelled = True` was set but `renderable` files were not moved to `fallback`, so they were silently lost rather than sent to the OS print handler.
   - Fix: `fallback.extend(renderable)` before setting `cancelled = True`.

---

## 2026-04-19 — `PR #33: fix: print preview blocked on Linux — toolbar hook too narrow` — run 1

Actionable: ?  Nitpicks: 3
- Harden tag lookup for repos with mixed/no tags.
- Graceful degradation is reasonable; consider a one-time user hint.
- Prefer objectName/shortcut over the broad text substring match.

---

## 2026-04-18 — `PR #34: fix: auto job/quote numbers scan CF and BP dirs for existing numbers` — run 1

Actionable: 2  Nitpicks: 2
- Clarify the version computation step in the example.
- Specify the expected action when checking thresholds.
- Configuration used

---

## 2026-04-18 — `PR #35: feat: automated weekly code audit posts findings as GitHub issues` — run 1

Actionable: 3  Nitpicks: 1
- Consider a summary-issue mode to avoid issue-tracker noise.
- Configuration used
