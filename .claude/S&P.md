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
> ```text
> </details>
>
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```text
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
```text

```diff
-                        print(f"[find_job_folders] Prefix path doesn't exist!", flush=True)
+                        print("[find_job_folders] Prefix path doesn't exist!", flush=True)
```

Note: Line 268's f-string with `{{po_number}}` is intentional (escaped braces display the literal).

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
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
```text

</details>

</blockquote></details>
<details>
<summary>modules/quote/module.py (1)</summary><blockquote>

`837-848`: **Align ITAR prefix detection to match search module pattern for consistency.**

The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.

Update line 839:

```diff
-            is_itar = display_name.startswith('[ITAR]')
+            is_itar = display_name.startswith(('[ITAR] ', '[ITAR-BP] '))
```

This aligns with the search module's pattern and improves clarity about expected prefix formats.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In `@modules/quote/module.py` around lines 837 - 848, The ITAR prefix detection in
the quote module is inconsistent: update the logic around display_name and
is_itar to mirror the search module pattern by checking
display_name.startswith(('[ITAR] ', '[ITAR-BP] ')) and adjust downstream
customer extraction to remove the matching prefix(s) (e.g., strip the bracketed
prefix plus trailing space) before building bp_dir/customer_bp; make this change
in the block that defines display_name, is_itar, customer and bp_dir so folder
resolution uses the consistent prefix detection used elsewhere.
```text

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```text
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

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 2

**Actionable comments posted: 2**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````text
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
````text

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

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 3

**Actionable comments posted: 1**

<details>
<summary>♻️ Duplicate comments (3)</summary><blockquote>

<details>
<summary>.claude/S&P.md (3)</summary><blockquote>

`217-217`: _⚠️ Potential issue_ | _🟡 Minor_

**Remove spaces inside inline code span.**

Line 217 has spaces inside the backticks around the ITAR token, triggering MD038. Change `` ` [ITAR] ` `` to `` `[ITAR]` ``.




<details>
<summary>📝 Suggested fix</summary>

```diff
-The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
+The search module (lines 674, 787) uses `startswith(('[ITAR] ', '[ITAR-BP] '))` to detect ITAR customers, but this module at line 839 uses `startswith('[ITAR]')`. While the simpler pattern technically matches `[ITAR-BP]` prefixes, it lacks the explicit space requirement and is inconsistent with the search module's more precise approach. The code also replaces both `[ITAR]` and `[ITAR]` patterns, suggesting both formats should be handled consistently.
```text

</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 217, Fix the inline code span that contains extra
spaces around the ITAR token: replace the backticked string that currently reads
with spaces around the token (i.e., "` [ITAR] `") so it becomes a
properly-formatted inline code span "`[ITAR]`"; ensure other similar occurrences
match this format (no leading/trailing spaces inside backticks) to satisfy MD038
and keep consistency with the search module's token usage.
```

</details>

---

`31-96`: _⚠️ Potential issue_ | _🟡 Minor_

**Resolve the contradiction about finding 15's commit status.**

Line 32 states "All 16 fixes applied" but lines 93-96 explicitly note that the change to `old/test-scripts/test_ui_loading.py` (finding 15) was "applied locally but not committed." Either update line 32 to "15 fixes applied" or rephrase to clarify that finding 15 was addressed locally but excluded from the commit.




<details>
<summary>📝 Suggested fix</summary>

```diff
-**Result:** All 16 fixes applied on `fix/coderabbit-full-review`.
+**Result:** 15 fixes applied on `fix/coderabbit-full-review`. Finding 15 applied locally only (file gitignored).
```text

</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 31 - 96, Update the summary to resolve the
contradiction between the top-line "All 16 fixes applied on
`fix/coderabbit-full-review`" and the Finding 15 note that the change to
`old/test-scripts/test_ui_loading.py` was "applied locally but not committed":
either change the summary string "All 16 fixes applied on
`fix/coderabbit-full-review`" to "15 fixes applied on
`fix/coderabbit-full-review`" or append a clarifying parenthetical to the
summary indicating that Finding 15 was fixed locally but intentionally excluded
from the commit; locate the exact summary text "All 16 fixes applied on
`fix/coderabbit-full-review`" and the Finding 15 bullet mentioning "applied
locally but not committed" to make the consistent edit.
```

</details>

---

`150-150`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to fenced code blocks.**

Multiple fenced code blocks lack language identifiers (lines 150, 193, 231, 253, 413), triggering MD040 warnings. Add `text` or an appropriate language identifier after each opening fence.




<details>
<summary>📝 Suggested fix</summary>

```diff
-```
+```text
 Verify each finding against the current code and only fix it if needed.
```text

Apply this change to all five occurrences.

</details>


Also applies to: 193-193, 231-231, 253-253, 413-413

<details>
<summary>🤖 Prompt for AI Agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 150, Update each fenced code block that currently
opens with ``` so it includes a language identifier (e.g., change ``` to
```text) for the five occurrences flagged (the plain triple-backtick fences near
the reported spots). Locate the opening fences (``` ) and replace them with
```text (or another appropriate language identifier) so each code block has an
explicit language, mirroring the suggested fix example (```text Verify each
finding against the current code and only fix it if needed.). Ensure you apply
this change to all five occurrences flagged in the comment.
````text

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 406: The duplicate H2 "2026-04-07 — `PR `#6`: fix: address all 16
CodeRabbit findings from full codebase review`" at line 406 should be made
unique to avoid MD024; edit that heading (the H2 string) to append a
distinguishing suffix such as a run identifier or timestamp (e.g., "— Run ID:
<id>" or "— review run 2") so it differs from the earlier H2 at line 106; update
only the heading text for the section starting with "## 2026-04-07 — `PR `#6`:
fix: address all 16 CodeRabbit findings from full codebase review`".

---

Duplicate comments:
In @.claude/S&P.md:
- Line 217: Fix the inline code span that contains extra spaces around the ITAR
token: replace the backticked string that currently reads with spaces around the
token (i.e., "` [ITAR] `") so it becomes a properly-formatted inline code span
"`[ITAR]`"; ensure other similar occurrences match this format (no
leading/trailing spaces inside backticks) to satisfy MD038 and keep consistency
with the search module's token usage.
- Around line 31-96: Update the summary to resolve the contradiction between the
top-line "All 16 fixes applied on `fix/coderabbit-full-review`" and the Finding
15 note that the change to `old/test-scripts/test_ui_loading.py` was "applied
locally but not committed": either change the summary string "All 16 fixes
applied on `fix/coderabbit-full-review`" to "15 fixes applied on
`fix/coderabbit-full-review`" or append a clarifying parenthetical to the
summary indicating that Finding 15 was fixed locally but intentionally excluded
from the commit; locate the exact summary text "All 16 fixes applied on
`fix/coderabbit-full-review`" and the Finding 15 bullet mentioning "applied
locally but not committed" to make the consistent edit.
- Line 150: Update each fenced code block that currently opens with ``` so it
includes a language identifier (e.g., change ``` to ```text) for the five
occurrences flagged (the plain triple-backtick fences near the reported spots).
Locate the opening fences (``` ) and replace them with ```text (or another
appropriate language identifier) so each code block has an explicit language,
mirroring the suggested fix example (```text Verify each finding against the
current code and only fix it if needed.). Ensure you apply this change to all
five occurrences flagged in the comment.
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

**Run ID**: `e4e7be04-be8f-4aa7-979c-ce1dad4459d4`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 910cb708457d66c0f9255a29821330b18a3e3f20 and 975f9df492b8403858dfb483a8c67e54a463590b.

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `.claude/S&P.md`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-07 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 4

**Actionable comments posted: 1**

> [!CAUTION]
> Some comments are outside the diff and can’t be posted inline due to platform limitations.
>
>
>
> <details>
> <summary>⚠️ Outside diff range comments (3)</summary><blockquote>
>
> <details>
> <summary>core/module_loader.py (1)</summary><blockquote>
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
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```text
> Verify each finding against the current code and only fix it if needed.
>
> In `@core/module_loader.py` around lines 52 - 64, The inline comment in
> module_loader.py referencing "Rule 3" is ambiguous; update the comment above the
> hardcoded all_modules list to briefly explain what "Rule 3" means (e.g.,
> "PSM-only modules are excluded from stable builds per release policy: PSM
> modules are runtime-only and must not be bundled") or add a one-line link to the
> external policy doc, and mention the coupling to JobDocs.spec's hiddenimports so
> future maintainers know to update both all_modules and hiddenimports together;
> ensure references to all_modules and deprecated_modules remain unchanged.
> ```
>
> </details>
>
> </blockquote></details>
> <details>
> <summary>modules/quote/module.py (1)</summary><blockquote>
>
> `802-815`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Link creation not gated by `bp_dest` existence in the "both" destination path.**
>
> Same issue as in `modules/job/module.py`: if the copy to `bp_dest` fails due to `PermissionError`, `bp_dest` won't exist but line 812 still attempts to create a link from it.
>
> <details>
> <summary>Suggested fix</summary>
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
> </details>
>
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```text
> Verify each finding against the current code and only fix it if needed.
>
> In `@modules/quote/module.py` around lines 802 - 815, The copy-to-bp_dest can fail
> with PermissionError but the code still attempts to create a link from bp_dest;
> change the "both" branch so that you only call create_file_link(bp_dest,
> quote_dest, link_type) and increment added if bp_dest.exists() (or perform the
> link inside the try block after a successful shutil.copy2) and otherwise skip
> linking/increment skipped and log the PermissionError; ensure references to
> bp_dest, quote_dest, create_file_link, file_path, file_name, link_type, added,
> and skipped are updated so added is only increased when the link was actually
> created.
> ```
>
> </details>
>
> </blockquote></details>
> <details>
> <summary>modules/job/module.py (1)</summary><blockquote>
>
> `849-862`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Link creation not gated by `bp_dest` existence in the "both" destination path.**
>
> If the copy to `bp_dest` fails due to `PermissionError`, `bp_dest` won't exist but line 859 still attempts to create a link from it. This will fail or produce undefined behavior.
>
> <details>
> <summary>Suggested fix</summary>
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
> </details>
>
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```text
> Verify each finding against the current code and only fix it if needed.
>
> In `@modules/job/module.py` around lines 849 - 862, The current "both" branch may
> call create_file_link(bp_dest, job_dest, link_type) even if the prior
> shutil.copy2 failed and bp_dest does not exist; update the block so that after
> the except PermissionError path you only attempt create_file_link if
> bp_dest.exists(), otherwise skip linking (and increment skipped) and keep the
> existing warning; ensure added is incremented only when create_file_link
> succeeds and reference bp_dest, job_dest, create_file_link, link_type,
> file_path, and file_name when locating the change.
> ```
>
> </details>
>
> </blockquote></details>
>
> </blockquote></details>

<details>
<summary>♻️ Duplicate comments (3)</summary><blockquote>

<details>
<summary>.claude/S&P.md (3)</summary><blockquote>

`406-406`: _⚠️ Potential issue_ | _🟡 Minor_

**Make repeated PR `#6` H2 headings unique.**

Line 406 and Line 482 repeat the same H2 text (already duplicated with Line 106), which keeps triggering MD024.

 

<details>
<summary>Suggested edit</summary>

```diff
-## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review`
+## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review` — review run 2

...

-## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review`
+## 2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings from full codebase review` — review run 3
```text
</details>


Also applies to: 482-482

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 406, The H2 "2026-04-07 — `PR `#6`: fix: address all 16
CodeRabbit findings from full codebase review`" is duplicated; update the
repeated H2 occurrences so each heading is unique (for example append a
disambiguator like "(continued)", "(part 2)", or a specific file/module tag)
where the same exact heading string appears; locate the headings by searching
for that exact H2 text and change the duplicates to unique variants while
keeping the original heading intact for the first occurrence.
```

</details>

---

`413-413`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to newly added fenced blocks.**

Line 413, Line 514, Line 551, Line 599, and Line 621 still open fenced blocks without a language, so MD040 persists in the new sections.

 

<details>
<summary>Suggested edit</summary>

```diff
-````
+```text
 Verify each finding against the current code and only fix it if needed.
 ...
-````
+```
```text
</details>


Also applies to: 514-514, 551-551, 599-599, 621-621

<details>
<summary>🤖 Prompt for AI Agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 413, Several fenced code blocks were added without
language identifiers; update each opening triple-backtick fence for the newly
added blocks (the ones that wrap the "Verify each finding against the current
code..." and similar note blocks) to include a language tag such as text (i.e.,
change ``` to ```text) so MD040 is resolved; locate the untagged fences (the
bare ``` blocks) and replace them with ```text for consistency.
````text

</details>

---

`217-217`: _⚠️ Potential issue_ | _🟡 Minor_

**Remove internal spacing in inline code span.**

Line 217 still contains a spaced code span variant (`[ITAR]`), which triggers MD038.

 

<details>
<summary>Suggested edit</summary>

```diff
-The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
+The code also handles both `[ITAR]` (with and without trailing-space variants in raw text), suggesting both formats should be handled consistently.
```text
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 217, The inline code span contains a trailing space
variant `[ITAR] ` which triggers MD038; update the text to use the non-spaced
inline code span `[ITAR]` and make the markdown consistent by replacing any
other occurrences of `[ITAR] ` with `[ITAR]`; also ensure the document's
described detection logic references the exact patterns (`startswith(('[ITAR] ',
'[ITAR-BP] ')` vs `startswith('[ITAR]')`) consistently in prose so readers and
the code replacement logic that handles both `[ITAR] ` and `[ITAR]` are aligned.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>core/app_context.py (1)</summary><blockquote>

`268-268`: **Remove extraneous `f` prefix from string literal.**

This f-string has no placeholders—the double braces `{{po_number}}` produce a literal `{po_number}`. Remove the `f` prefix.

```diff
-                    print(f"[find_job_folders] Detected {{po_number}} in prefix, enumerating PO dirs", flush=True)
+                    print("[find_job_folders] Detected {po_number} in prefix, enumerating PO dirs", flush=True)
```text

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In `@core/app_context.py` at line 268, In the print in find_job_folders, remove
the unnecessary f-string prefix so the literal "{po_number}" is printed
correctly; change the print call that currently uses print(f"[find_job_folders]
Detected {{po_number}} in prefix, enumerating PO dirs", flush=True) to a regular
string literal without the leading f to avoid treating it as an f-string.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@modules/quote/module.py`:
- Around line 829-868: In open_blueprints_folder: initialize is_itar = False at
the start, ensure the branch that reads the customer combo sets is_itar (e.g.,
from self.quote_itar_check.isChecked()), and change the fallback get_setting
call to use 'itar_blueprints_dir' when is_itar is True (otherwise
'blueprints_dir'); this makes the final bp_dir lookup consistent with how
is_itar is determined earlier in the function.

---

Outside diff comments:
In `@core/module_loader.py`:
- Around line 52-64: The inline comment in module_loader.py referencing "Rule 3"
is ambiguous; update the comment above the hardcoded all_modules list to briefly
explain what "Rule 3" means (e.g., "PSM-only modules are excluded from stable
builds per release policy: PSM modules are runtime-only and must not be
bundled") or add a one-line link to the external policy doc, and mention the
coupling to JobDocs.spec's hiddenimports so future maintainers know to update
both all_modules and hiddenimports together; ensure references to all_modules
and deprecated_modules remain unchanged.

In `@modules/job/module.py`:
- Around line 849-862: The current "both" branch may call
create_file_link(bp_dest, job_dest, link_type) even if the prior shutil.copy2
failed and bp_dest does not exist; update the block so that after the except
PermissionError path you only attempt create_file_link if bp_dest.exists(),
otherwise skip linking (and increment skipped) and keep the existing warning;
ensure added is incremented only when create_file_link succeeds and reference
bp_dest, job_dest, create_file_link, link_type, file_path, and file_name when
locating the change.

In `@modules/quote/module.py`:
- Around line 802-815: The copy-to-bp_dest can fail with PermissionError but the
code still attempts to create a link from bp_dest; change the "both" branch so
that you only call create_file_link(bp_dest, quote_dest, link_type) and
increment added if bp_dest.exists() (or perform the link inside the try block
after a successful shutil.copy2) and otherwise skip linking/increment skipped
and log the PermissionError; ensure references to bp_dest, quote_dest,
create_file_link, file_path, file_name, link_type, added, and skipped are
updated so added is only increased when the link was actually created.

---

Duplicate comments:
In @.claude/S&P.md:
- Line 406: The H2 "2026-04-07 — `PR `#6`: fix: address all 16 CodeRabbit findings
from full codebase review`" is duplicated; update the repeated H2 occurrences so
each heading is unique (for example append a disambiguator like "(continued)",
"(part 2)", or a specific file/module tag) where the same exact heading string
appears; locate the headings by searching for that exact H2 text and change the
duplicates to unique variants while keeping the original heading intact for the
first occurrence.
- Line 413: Several fenced code blocks were added without language identifiers;
update each opening triple-backtick fence for the newly added blocks (the ones
that wrap the "Verify each finding against the current code..." and similar note
blocks) to include a language tag such as text (i.e., change ``` to ```text) so
MD040 is resolved; locate the untagged fences (the bare ``` blocks) and replace
them with ```text for consistency.
- Line 217: The inline code span contains a trailing space variant `[ITAR] `
which triggers MD038; update the text to use the non-spaced inline code span
`[ITAR]` and make the markdown consistent by replacing any other occurrences of
`[ITAR] ` with `[ITAR]`; also ensure the document's described detection logic
references the exact patterns (`startswith(('[ITAR] ', '[ITAR-BP] ')` vs
`startswith('[ITAR]')`) consistently in prose so readers and the code
replacement logic that handles both `[ITAR] ` and `[ITAR]` are aligned.

---

Nitpick comments:
In `@core/app_context.py`:
- Line 268: In the print in find_job_folders, remove the unnecessary f-string
prefix so the literal "{po_number}" is printed correctly; change the print call
that currently uses print(f"[find_job_folders] Detected {{po_number}} in prefix,
enumerating PO dirs", flush=True) to a regular string literal without the
leading f to avoid treating it as an f-string.
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

**Run ID**: `025e0b68-45ef-480e-8831-db9dbd3c3d71`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 975f9df492b8403858dfb483a8c67e54a463590b and c109116f1c4b7d324166a6ee69dbed87a8eab211.

</details>

<details>
<summary>📒 Files selected for processing (5)</summary>

* `.claude/S&P.md`
* `core/app_context.py`
* `core/module_loader.py`
* `modules/job/module.py`
* `modules/quote/module.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->
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
> <details>
> <summary>⚠️ Outside diff range comments (1)</summary><blockquote>
>
> <details>
> <summary>modules/quote/module.py (1)</summary><blockquote>
>
> `602-610`: _⚠️ Potential issue_ | _🟠 Major_
>
> **Missing worker cancellation before synchronous search.**
>
> Unlike `search_jobs` in the job module (which now cancels any running worker at lines 653-655), `search_quotes` does not cancel `self._worker` before clearing the tree and performing a synchronous search. If `refresh_quote_tree()` is still loading, its queued `customer_loaded` emissions can repopulate `self.quote_tree` after line 610 clears it, mixing stale browse results with search results.
>
>
> <details>
> <summary>Suggested fix</summary>
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
> </details>
>
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
>
> ```text
> Verify each finding against the current code and only fix it if needed.
>
> In `@modules/quote/module.py` around lines 602 - 610, search_quotes is missing
> cancellation of any running background worker, so add the same worker-cancel
> logic used in search_jobs: if self._worker exists and is running, call its
> cancel/stop method and wait/handle cancellation before calling
> self.refresh_quote_tree() or clearing self.quote_tree; ensure this runs at the
> start of search_quotes (referencing method name search_quotes and attribute
> self._worker) so pending customer_loaded signals from refresh_quote_tree()
> cannot repopulate the tree after you clear it.
> ```text
>
> </details>
>
> </blockquote></details>
>
> </blockquote></details>

<details>
<summary>🧹 Nitpick comments (2)</summary><blockquote>

<details>
<summary>.claude/S&P.md (2)</summary><blockquote>

`1200-1202`: **Minor grammar nit: hyphenate "f-prefix".**

Static analysis flags line 1202. The phrase "removed f prefix" should be "removed f-prefix" (compound modifier).

```diff
-   - Fix: removed f prefix
+   - Fix: removed f-prefix
```

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 1200 - 1202, Update the documentation line that
currently reads "removed f prefix" to use the hyphenated compound modifier
"removed f-prefix" in the S&P entry referencing the change to
core/app_context.py (the "f-prefix on {{po_number}} print" note); edit the
sentence in .claude/S&P.md so the phrase is "removed f-prefix".
```text

</details>

---

`960-992`: **MD038 warning is in a quoted duplicate-comment log entry.**

Line 964 triggers MD038 due to the spaced code span `` `[ITAR] ` ``, but this text is inside a `<details>` block quoting a prior CodeRabbit comment. Since this is a verbatim log of historical review feedback (not new prose you're authoring), editing it would misrepresent the original comment.

If you want a clean lint pass, you could either:
1. Wrap the entire quoted section in a raw HTML block so linters skip it, or
2. Accept the warning as a known artifact of logging verbatim review history.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 960 - 992, The quoted duplicate-comment log
entry contains a spaced inline code span `[ITAR] ` that triggers MD038; do not
alter the historical verbatim text — instead wrap that entire
quoted/duplicate-comment block (the <details> / quoted review text containing ``
`[ITAR] ` ``) in a raw HTML pre/code block (e.g., <pre><code>...</code></pre>)
so linters skip it, or alternatively replace only the spaced inline code span
`[ITAR] ` with the non-spaced `[ITAR]` everywhere in that quoted section if you
prefer to normalize; target the quoted duplicate-comment block and the exact
token `[ITAR] ` when making the change.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

Outside diff comments:
In `@modules/quote/module.py`:
- Around line 602-610: search_quotes is missing cancellation of any running
background worker, so add the same worker-cancel logic used in search_jobs: if
self._worker exists and is running, call its cancel/stop method and wait/handle
cancellation before calling self.refresh_quote_tree() or clearing
self.quote_tree; ensure this runs at the start of search_quotes (referencing
method name search_quotes and attribute self._worker) so pending customer_loaded
signals from refresh_quote_tree() cannot repopulate the tree after you clear it.

---

Nitpick comments:
In @.claude/S&P.md:
- Around line 1200-1202: Update the documentation line that currently reads
"removed f prefix" to use the hyphenated compound modifier "removed f-prefix" in
the S&P entry referencing the change to core/app_context.py (the "f-prefix on
{{po_number}} print" note); edit the sentence in .claude/S&P.md so the phrase is
"removed f-prefix".
- Around line 960-992: The quoted duplicate-comment log entry contains a spaced
inline code span `[ITAR] ` that triggers MD038; do not alter the historical
verbatim text — instead wrap that entire quoted/duplicate-comment block (the
<details> / quoted review text containing `` `[ITAR] ` ``) in a raw HTML
pre/code block (e.g., <pre><code>...</code></pre>) so linters skip it, or
alternatively replace only the spaced inline code span `[ITAR] ` with the
non-spaced `[ITAR]` everywhere in that quoted section if you prefer to
normalize; target the quoted duplicate-comment block and the exact token `[ITAR]
` when making the change.
```text

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: defaults

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `67f46ac5-a17e-4956-8a33-3a2d718681f4`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between c109116f1c4b7d324166a6ee69dbed87a8eab211 and cf2b71e71e902622ab3e565e9b21f89bf024cd49.

</details>

<details>
<summary>📒 Files selected for processing (5)</summary>

* `.claude/S&P.md`
* `core/app_context.py`
* `core/module_loader.py`
* `modules/job/module.py`
* `modules/quote/module.py`

</details>

<details>
<summary>✅ Files skipped from review due to trivial changes (1)</summary>

* core/app_context.py

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (1)</summary>

* core/module_loader.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 7

**Actionable comments posted: 3**

<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>modules/job/module.py (1)</summary><blockquote>

`900-916`: _⚠️ Potential issue_ | _🟠 Major_

**Preserve the active ITAR context through the fallback path.**

Line 900 still enters the Create-tab branch whenever no customer-specific folder was found, even if a tree selection already established the context, and Line 903 only updates `is_itar` when `customer` is non-empty. That means an empty customer + checked ITAR box still falls back to `blueprints_dir`, and a missing tree folder can be replaced by stale Create-tab state instead of the selected ITAR base.

 

<details>
<summary>Suggested fix</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In `@modules/job/module.py` around lines 900 - 916, The code currently delays
computing is_itar until after checking customer text, causing an empty customer
with the ITAR checkbox set to use the non-ITAR blueprints_dir and allowing
Create-tab state to override a prior tree selection; to fix, compute is_itar
up-front from self.itar_check (e.g., is_itar = self.itar_check.isChecked() if
self.itar_check else False) before any customer or folder_to_open logic so the
same is_itar is used both when building customer_bp (customer_bp =
os.path.join(bp_dir, customer)) and in the fallback bp_dir lookup via
self.app_context.get_setting('itar_blueprints_dir' if is_itar else
'blueprints_dir', ''), and ensure you only run the create-tab/customer branch
when folder_to_open is still empty to preserve any tree-selected folder_to_open.
```text

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>modules/job/module.py (1)</summary><blockquote>

`659-682`: **Extract the add-tab filter selection into one helper.**

`search_jobs()` now has a second copy of the same radio/customer filtering logic from `refresh_job_tree()`/`JobTreeWorker.run()`. Since this PR is explicitly keeping search and refresh aligned, pulling that branching into one helper will keep the next filter change from drifting again.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In `@modules/job/module.py` around lines 659 - 682, Extract the duplicated
"add-tab" radio/customer filtering from search_jobs() and
refresh_job_tree()/JobTreeWorker.run() into a single helper (e.g.,
_get_add_tab_dirs) that returns the dirs_to_search list of (prefix, dir) and the
selected_customer/show_all flag; have search_jobs(), refresh_job_tree(), and
JobTreeWorker.run() call this helper instead of re-implementing the logic that
inspects add_all_radio, add_standard_radio, add_customer_combo,
app_context.get_setting('customer_files_dir'/'itar_customer_files_dir'),
_get_customer_files_dirs(), and os.path.exists; ensure the helper preserves the
exact behavior (including empty/default handling) and only returns validated
existing directories so callers can iterate customers as before.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 1252: Two fenced code blocks were opened without language identifiers
(MD040); update both opening fences to include the language token "text" so they
read "```text". Locate the two occurrences of bare "```" around the snippet that
begins "Verify each finding against the current code and only fix it if needed."
(the occurrences noted at the two problem locations) and change each opening
fence to "```text" to silence the warnings and match the document style.

In `@core/app_context.py`:
- Around line 266-273: The prefix handling allows "{po_number}" embedded inside
a segment (e.g. "PO-{po_number}") which breaks directory discovery; update the
logic in the function that processes prefix (the code using variables prefix,
pre_po, post_po, base_path and referenced by build_job_path()) to enforce that
"{po_number}" is its own path segment or reject the template: either validate by
splitting prefix on path separators and require one segment exactly equal to
"{po_number}" (and if not, raise/log a configuration error and skip/abort), or
parse the surrounding segment properly by extracting the full segment containing
the placeholder rather than naively joining pre_po and base_path; ensure the
check handles leading/trailing segments (start, middle, end) consistently and
produces a clear error when templates are invalid.
- Around line 274-292: The current try/except in find_job_folders wraps the
entire loop over base_path so a single OSError aborts processing all PO dirs;
instead, move the OSError handling to each PO directory iteration (around the
os.listdir and os.path operations for po_dir/sub_path) so that on exception you
log or print the error (keeping the existing "[find_job_folders]" message) and
continue to the next po_dir; update the code that builds jobs (using base_path,
po_dir, sub_path, suffix, post_po, jobs) to remain unchanged except skip the
failing subtree on error.

---

Duplicate comments:
In `@modules/job/module.py`:
- Around line 900-916: The code currently delays computing is_itar until after
checking customer text, causing an empty customer with the ITAR checkbox set to
use the non-ITAR blueprints_dir and allowing Create-tab state to override a
prior tree selection; to fix, compute is_itar up-front from self.itar_check
(e.g., is_itar = self.itar_check.isChecked() if self.itar_check else False)
before any customer or folder_to_open logic so the same is_itar is used both
when building customer_bp (customer_bp = os.path.join(bp_dir, customer)) and in
the fallback bp_dir lookup via
self.app_context.get_setting('itar_blueprints_dir' if is_itar else
'blueprints_dir', ''), and ensure you only run the create-tab/customer branch
when folder_to_open is still empty to preserve any tree-selected folder_to_open.

---

Nitpick comments:
In `@modules/job/module.py`:
- Around line 659-682: Extract the duplicated "add-tab" radio/customer filtering
from search_jobs() and refresh_job_tree()/JobTreeWorker.run() into a single
helper (e.g., _get_add_tab_dirs) that returns the dirs_to_search list of
(prefix, dir) and the selected_customer/show_all flag; have search_jobs(),
refresh_job_tree(), and JobTreeWorker.run() call this helper instead of
re-implementing the logic that inspects add_all_radio, add_standard_radio,
add_customer_combo,
app_context.get_setting('customer_files_dir'/'itar_customer_files_dir'),
_get_customer_files_dirs(), and os.path.exists; ensure the helper preserves the
exact behavior (including empty/default handling) and only returns validated
existing directories so callers can iterate customers as before.
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

**Run ID**: `2d6f1879-407a-463f-9f80-eff48353efd1`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between c109116f1c4b7d324166a6ee69dbed87a8eab211 and 9cf55370acf1fd78e528878667bb00c0c05857eb.

</details>

<details>
<summary>📒 Files selected for processing (5)</summary>

* `.claude/S&P.md`
* `core/app_context.py`
* `core/module_loader.py`
* `modules/job/module.py`
* `modules/quote/module.py`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (2)</summary>

* core/module_loader.py
* modules/quote/module.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 8

**Actionable comments posted: 2**

<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>.claude/S&P.md (1)</summary><blockquote>

`1252-1252`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifier to fenced code block.**

This fenced code block lacks a language identifier, triggering MD040. This same issue was flagged in a previous review but remains unresolved.

<details>
<summary>📝 Suggested fix</summary>

```diff
-```
+```text
 Verify each finding against the current code and only fix it if needed.
```text

</details>




Also applies to: 1289-1289

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 1252, A fenced code block containing the text "Verify
each finding against the current code and only fix it if needed." is missing a
language identifier (MD040); update the opening fence to include a language tag
(e.g., add "text" after the backticks) so it becomes a labeled fenced code block
and repeat the same fix for the other occurrence flagged at the secondary
location.
```text

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 1465: Three fenced code blocks open with bare ``` (no language) and
trigger MD040; update each opening fence to include the language identifier
"text". Locate the three occurrences of triple-backtick blocks (one that
contains the line "Verify each finding against the current code and only fix it
if needed." and the two other similar bare fences near it) and change their
opening from ``` to ```text so all fenced blocks consistently include a language
identifier.
- Line 1428: The duplicate heading at the second occurrence (previously flagged
by MD024) should be made unique — edit the duplicate heading text around where
the heading at line 1428 appears and append a distinguishing suffix (e.g., the
run timestamp or the Run ID `2d6f1879-407a-463f-9f80-eff48353efd1` from the
document metadata) so the two headings are no longer identical; update only the
heading text (not other content) to preserve context and avoid further MD024
violations.

---

Duplicate comments:
In @.claude/S&P.md:
- Line 1252: A fenced code block containing the text "Verify each finding
against the current code and only fix it if needed." is missing a language
identifier (MD040); update the opening fence to include a language tag (e.g.,
add "text" after the backticks) so it becomes a labeled fenced code block and
repeat the same fix for the other occurrence flagged at the secondary location.
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

**Run ID**: `22e1d0e8-9e8a-48b4-a33c-3427b0b438db`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 9cf55370acf1fd78e528878667bb00c0c05857eb and a760adb4d5433ac4d5cdb84f225bffbabdd8a97b.

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `.claude/S&P.md`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 9



<details>
<summary>♻️ Duplicate comments (2)</summary><blockquote>

<details>
<summary>.claude/S&P.md (2)</summary><blockquote>

`1252-1252`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifiers to all remaining fenced code openings (MD040).**

These fences are still opened without a language token. Update each opener to include one (typically `text`; preserve triple vs quadruple backtick style as needed).

<details>
<summary>📝 Suggested patch pattern</summary>

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
</details>

 


Also applies to: 1289-1289, 1465-1465, 1500-1500, 1525-1525, 1688-1688, 1708-1708

<details>
<summary>🤖 Prompt for AI Agents</summary>

`````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 1252, Several fenced code blocks are opened without
language identifiers (MD040); locate each opening backtick fence (both triple
``` and quadruple ````) that precedes the text "Verify each finding against the
current code and only fix it if needed." and add a language token (e.g., text)
to the opener so the fences become ```text and ````text respectively; apply the
same change to the other occurrences referenced (the other identical fences
further down) to ensure all remaining unlabelled fences are labeled.
`````

</details>

---

`1428-1428`: _⚠️ Potential issue_ | _🟡 Minor_

**Make repeated H2 headings unique to resolve MD024.**

Line 1428 and Line 1653 use the same H2 text, which keeps `no-duplicate-heading` failing. Please append a distinct suffix (for example run ID / “review run N”) to one of them.

 


Also applies to: 1653-1653

<details>
<summary>🤖 Prompt for AI Agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 1428, Two identical H2 headings ("2026-04-08 — `PR
`#6`: fix: address all 16 CodeRabbit findings from full codebase review`") cause
MD024; locate both H2 occurrences and make one unique by appending a short
suffix such as " — review run 1" or a run ID (e.g., change one heading to
"2026-04-08 — `PR `#6`: ...` — review run 1"); ensure the modified H2 string is
distinct from the other so the linter no longer reports no-duplicate-heading.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

`````text
Verify each finding against the current code and only fix it if needed.

Duplicate comments:
In @.claude/S&P.md:
- Line 1252: Several fenced code blocks are opened without language identifiers
(MD040); locate each opening backtick fence (both triple ``` and quadruple ````)
that precedes the text "Verify each finding against the current code and only
fix it if needed." and add a language token (e.g., text) to the opener so the
fences become ```text and ````text respectively; apply the same change to the
other occurrences referenced (the other identical fences further down) to ensure
all remaining unlabelled fences are labeled.
- Line 1428: Two identical H2 headings ("2026-04-08 — `PR `#6`: fix: address all
16 CodeRabbit findings from full codebase review`") cause MD024; locate both H2
occurrences and make one unique by appending a short suffix such as " — review
run 1" or a run ID (e.g., change one heading to "2026-04-08 — `PR `#6`: ...` —
review run 1"); ensure the modified H2 string is distinct from the other so the
linter no longer reports no-duplicate-heading.
`````

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: defaults

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `fccea686-81f9-41d4-bb25-7f31b67c1834`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between a760adb4d5433ac4d5cdb84f225bffbabdd8a97b and 3cc548e871b5710612482df3a9f9a4dedc1c927e.

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `.claude/S&P.md`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 10

**Actionable comments posted: 5**

<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>.claude/S&P.md (1)</summary><blockquote>

`1897-1897`: _⚠️ Potential issue_ | _🟡 Minor_

**Add language identifier to fenced code block.**

The quadruple-backtick fence at line 1897 lacks a language identifier, triggering MD040.



<details>
<summary>📝 Suggested fix</summary>

```diff
-`````
+`````text
 Verify each finding against the current code and only fix it if needed.
 `````
```text
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

``````
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md at line 1897, Add a language identifier to the
quadruple-backtick fenced code block (the fence starting with `````) so the
block is properly classified (e.g., change the opening fence to `````text or
`````bash); update only the opening fence near the existing ````` to include the
appropriate language token and leave the closing fence as-is to resolve MD040.
``````

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>.claude/S&P.md (1)</summary><blockquote>

`26-1935`: **Consider running the sanitization script comprehensively on the entire document.**

The PR description mentions `.github/scripts/sanitize_review.py` was created to automatically fix MD040 and MD024 violations. However, multiple review runs continue to flag the same types of violations in newly appended content. The script may not be processing the entire document or handling all fence variants (triple vs quadruple backticks, nested sections).

Consider either:
1. Running the sanitization script on the complete S&P.md file after each append operation
2. Enhancing the script to handle all backtick fence variants and nested prompt sections
3. Adding a pre-commit hook or CI check to prevent these violations from being committed

This would prevent the feedback loop where each review run adds more content that triggers the same lint violations.

<details>
<summary>🤖 Prompt for AI Agents</summary>

`````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 26 - 1935, The S&P.md file is still getting
MD024/MD040 violations because the sanitization step only fixes parts of the
document; run or extend the sanitizer to cover the entire file (not just the
appended fragment) and handle all fence variants so new sections don't
reintroduce errors. Specifically, run .github/scripts/sanitize_review.py across
the full .claude/S&P.md (or update the script to treat both triple and quadruple
backticks, nested prompt blocks, and repeated H2 headings), then reformat
occurrences of bare ```, ```` and spaced inline code spans and ensure duplicate
H2s are suffixed (e.g., “— review run N”); finally, add the full-file
sanitization to the commit workflow (pre-commit hook or CI step) so
.claude/S&P.md is always sanitized before push.
`````

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

``````text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 1839: A fenced code block opening with four backticks is missing a
language identifier (MD040); update the opening fence by adding the language
label "text" (i.e., change the opening fence from ````` to `````text) so the
block is properly annotated—locate the quadruple-backtick fence in the
.claude/S&P.md content and add the "text" identifier after the opening
backticks.
- Line 1817: Add a language identifier to the opening fenced code block (the
triple backticks) in the suggested patch section so the block is lint-compliant;
change the opening fence from ``` to ```text and ensure the closing fence
remains ``` so the block reads as a text code block (i.e., use "text" as the
language identifier for that fenced code block).
- Around line 1891-1894: The markdown contains inline code spans that have
spaces around backticks (the triple-backtick and quadruple-backtick literals)
which trigger MD038; locate the occurrences referencing the fences that precede
"Verify each finding against the current code and only fix it if needed." and
remove the spaces inside the code span or, better, replace the bare fence spans
with fenced code openers that include a language token (e.g., change ``` to
```text and ```` to ````text) or escape the backticks so the inline code no
longer contains leading/trailing spaces.

In @.github/scripts/sanitize_review.py:
- Around line 20-25: The current loop only strips the two-character sequence ">
" so lines starting with ">" without a following space (e.g., ">```") are not
recognized; update the loop that manipulates content and prefix so it strips any
leading ">" and an optional single space repeatedly (e.g., test
content.startswith(">") then remove the first ">" and if the next char is a
space remove it and append "> " to prefix), ensuring sequences of nested
blockquote markers (">", "> ", ">> ", etc.) are all handled.
- Around line 26-35: The fence close check is too strict: change the equality
check on content (```/````) to compare lengths against the current opener
(fence_stack[-1]) so a fence closes when its length is >= the opener; if
fence_stack is empty treat content as an opening (push to fence_stack and append
prefix+content+"text"); if fence_stack exists and len(content) >= len(opening)
pop the stack and append stripped (closing fence); otherwise (len(content) <
len(opening)) treat the line as literal content and just append stripped. Ensure
you update the branch that currently uses fence_stack[-1] == content to use this
length-based logic and keep using variables fence_stack, content, stripped,
result, and prefix.

---

Duplicate comments:
In @.claude/S&P.md:
- Line 1897: Add a language identifier to the quadruple-backtick fenced code
block (the fence starting with `````) so the block is properly classified (e.g.,
change the opening fence to `````text or `````bash); update only the opening
fence near the existing ````` to include the appropriate language token and
leave the closing fence as-is to resolve MD040.

---

Nitpick comments:
In @.claude/S&P.md:
- Around line 26-1935: The S&P.md file is still getting MD024/MD040 violations
because the sanitization step only fixes parts of the document; run or extend
the sanitizer to cover the entire file (not just the appended fragment) and
handle all fence variants so new sections don't reintroduce errors.
Specifically, run .github/scripts/sanitize_review.py across the full
.claude/S&P.md (or update the script to treat both triple and quadruple
backticks, nested prompt blocks, and repeated H2 headings), then reformat
occurrences of bare ```, ```` and spaced inline code spans and ensure duplicate
H2s are suffixed (e.g., “— review run N”); finally, add the full-file
sanitization to the commit workflow (pre-commit hook or CI step) so
.claude/S&P.md is always sanitized before push.
``````

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

**Run ID**: `aaca3adb-52b0-4efb-8667-9f17919d7bf9`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 3cc548e871b5710612482df3a9f9a4dedc1c927e and 397c82d934f0b38295774db5306e4c94619ea9c0.

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `.claude/S&P.md`
* `.github/scripts/sanitize_review.py`
* `.github/workflows/log-coderabbit-review.yml`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (1)</summary>

* .github/workflows/log-coderabbit-review.yml

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 11

**Actionable comments posted: 1**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```text
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/S&P.md:
- Line 1939: The H2 "2026-04-08 — `PR `#6`: fix: address all 16 CodeRabbit
findings from full codebase review` — review run 6" is duplicated; update the
second occurrence to a unique heading (e.g., change the trailing "review run 6"
to "review run 6b", "review run 7", or append a short qualifier like "(duplicate
run)") so the H2 is distinct; locate the duplicate heading text and replace only
the heading line to preserve the rest of the section.
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

**Run ID**: `ad300eb4-8313-40ca-ac99-841504e90630`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 397c82d934f0b38295774db5306e4c94619ea9c0 and 2b20225f0e90a3db2fbe453f8549bdfd093427e5.

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `.claude/S&P.md`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #6: fix: address all 16 CodeRabbit findings from full codebase review` — review run 12



<details>
<summary>♻️ Duplicate comments (2)</summary><blockquote>

<details>
<summary>.claude/S&P.md (2)</summary><blockquote>

`1971-1979`: _⚠️ Potential issue_ | _🟡 Minor_

**Add a language identifier to the six-backtick fenced block.**

Line 1971 opens a fenced block with `````` but no language tag, which keeps MD040 active in this section.

 

<details>
<summary>🛠️ Suggested fix</summary>

```diff
-``````
+``````text
 Verify each finding against the current code and only fix it if needed.
 ...
 ``````
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 1971 - 1979, The six-backtick fenced code block
opening token (``````) in the .claude/S&P.md content should include a language
identifier to satisfy MD040; edit the opening fence near the existing `````` to
add a language tag (for example change the opening fence from `````` to
``````text or ``````bash) and leave the existing closing `````` fence unchanged
so the block is properly classified.
```````

</details>

---

`1976-1977`: _⚠️ Potential issue_ | _🟡 Minor_

**Avoid ambiguous inline backtick spans in prompt prose.**

Line 1976 and Line 1977 still use backtick-heavy inline literals that trigger MD038. Prefer plain wording (e.g., “five-backtick opener + text”) instead of raw fence literals.

 

<details>
<summary>🛠️ Suggested fix</summary>

```diff
-block is properly classified (e.g., change the opening fence to `````text or
-`````bash); update only the opening fence near the existing ````` to include the
+block is properly classified (e.g., change the opening fence to five-backtick + `text` or `bash`);
+update only the opening fence near the existing five-backtick marker to include the
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

``````text
Verify each finding against the current code and only fix it if needed.

In @.claude/S&P.md around lines 1976 - 1977, The prose at the two occurrences
flagged by MD038 uses ambiguous raw backtick fence literals; update the phrases
near the existing ````` markers (lines referenced in the comment) to avoid
inline backtick spans by using descriptive wording such as "five-backtick opener
+ text" or "five-backtick + `bash`" and reword the sentence to "change the
opening fence to five-backtick + text or five-backtick + bash; update only the
opening fence near the existing five-backtick marker to include the…" so no raw
multi-backtick sequences remain in the sentence.
``````

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```````text
Verify each finding against the current code and only fix it if needed.

Duplicate comments:
In @.claude/S&P.md:
- Around line 1971-1979: The six-backtick fenced code block opening token
(``````) in the .claude/S&P.md content should include a language identifier to
satisfy MD040; edit the opening fence near the existing `````` to add a language
tag (for example change the opening fence from `````` to ``````text or
``````bash) and leave the existing closing `````` fence unchanged so the block
is properly classified.
- Around line 1976-1977: The prose at the two occurrences flagged by MD038 uses
ambiguous raw backtick fence literals; update the phrases near the existing
````` markers (lines referenced in the comment) to avoid inline backtick spans
by using descriptive wording such as "five-backtick opener + text" or
"five-backtick + `bash`" and reword the sentence to "change the opening fence to
five-backtick + text or five-backtick + bash; update only the opening fence near
the existing five-backtick marker to include the…" so no raw multi-backtick
sequences remain in the sentence.
```````

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: defaults

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `39534453-1735-4420-ba62-b3d544474cc9`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 2b20225f0e90a3db2fbe453f8549bdfd093427e5 and bd662b951161e1dc93ed6b6a4822bb769aab229d.

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `.claude/S&P.md`
* `.github/scripts/sanitize_review.py`
* `.github/workflows/log-coderabbit-review.yml`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (2)</summary>

* .github/workflows/log-coderabbit-review.yml
* .github/scripts/sanitize_review.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-08 — `PR #7: fix: remove inspection reports feature` — review run 1



<details>
<summary>🧹 Nitpick comments (2)</summary><blockquote>

<details>
<summary>modules/quote/module.py (1)</summary><blockquote>

`497-510`: **Remove stale “report(s)” wording from link log message.**

Line 510 still mentions reports, which contradicts the drawings-only behavior and this PR’s objective.


<details>
<summary>Proposed text fix</summary>

```diff
-                    self.log_message(f"Linked {files_added} drawing(s)/report(s)")
+                    self.log_message(f"Linked {files_added} drawing(s)")
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@modules/quote/module.py` around lines 497 - 510, The log message in the
drawing-linking flow still says "drawing(s)/report(s)" which is stale; in the
method where the DrawingSearchDialog is used (the block creating dialog =
DrawingSearchDialog(self.get_widget(), self.app_context) and iterating
selected_files in the same function), update the process that calls
self.log_message(...) to use wording that only references drawings (e.g.,
"Linked {files_added} drawing(s)") so the message matches the drawings-only
behavior; keep the variable files_added and the existing pluralization format
intact.
```

</details>

</blockquote></details>
<details>
<summary>modules/job/module.py (1)</summary><blockquote>

`531-544`: **Update link log message to match drawings-only behavior.**

Line 544 still contains “report(s)”, which is inconsistent with the updated dialog purpose.


<details>
<summary>Proposed text fix</summary>

```diff
-                    self.log_message(f"Linked {files_added} drawing(s)/report(s)")
+                    self.log_message(f"Linked {files_added} drawing(s)")
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@modules/job/module.py` around lines 531 - 544, The log message after linking
files still says "Linked {files_added} drawing(s)/report(s)" which is
inconsistent with the drawings-only dialog (DrawingSearchDialog); update the
call to self.log_message in this method to only reference drawings (e.g.,
"Linked {files_added} drawing(s)") so it matches the UI behavior and the items
added to self.job_files/self.job_files_list.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Nitpick comments:
In `@modules/job/module.py`:
- Around line 531-544: The log message after linking files still says "Linked
{files_added} drawing(s)/report(s)" which is inconsistent with the drawings-only
dialog (DrawingSearchDialog); update the call to self.log_message in this method
to only reference drawings (e.g., "Linked {files_added} drawing(s)") so it
matches the UI behavior and the items added to
self.job_files/self.job_files_list.

In `@modules/quote/module.py`:
- Around line 497-510: The log message in the drawing-linking flow still says
"drawing(s)/report(s)" which is stale; in the method where the
DrawingSearchDialog is used (the block creating dialog =
DrawingSearchDialog(self.get_widget(), self.app_context) and iterating
selected_files in the same function), update the process that calls
self.log_message(...) to use wording that only references drawings (e.g.,
"Linked {files_added} drawing(s)") so the message matches the drawings-only
behavior; keep the variable files_added and the existing pluralization format
intact.
```

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `aac89868-4af1-48a7-bf17-10a94883c7c3`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between e31866f1abe4a4f72ca7044240df8f53d92ccbda and 1bf612c4361d4f54a65b3577925686f8c81520b4.

</details>

<details>
<summary>📒 Files selected for processing (7)</summary>

* `core/settings_dialog.py`
* `main.py`
* `modules/job/module.py`
* `modules/quote/module.py`
* `modules/search/module.py`
* `modules/search/ui/search_tab.ui`
* `shared/widgets.py`

</details>

<details>
<summary>💤 Files with no reviewable changes (4)</summary>

* core/settings_dialog.py
* modules/search/module.py
* main.py
* modules/search/ui/search_tab.ui

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-09 — `PR #9: ci: add build-release workflow for signed Windows exe` — review run 1

**Actionable comments posted: 4**

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>.github/workflows/build-release.yml (1)</summary><blockquote>

`16-16`: **Pin GitHub Actions to commit SHAs.**

Floating major version tags (`@v4`, `@v5`, `@v2`) weaken supply-chain guarantees. Pin to full commit SHAs for `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and `softprops/action-gh-release`.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In @.github/workflows/build-release.yml at line 16, The workflow currently uses
floating tags like "uses: actions/checkout@v4" which weakens supply-chain
guarantees; update each third-party action reference (e.g., actions/checkout@v4,
actions/setup-python@..., actions/upload-artifact@...,
softprops/action-gh-release@...) to pin to the corresponding full commit SHA for
that action repository instead of the major/minor tag, replacing the tag strings
with the exact commit SHAs so each "uses:" entry references a specific immutable
commit.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

````
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.claude/CLAUDE.md:
- Around line 84-87: The fenced code block containing the git commands ("git tag
v1.2.3" and "git push origin v1.2.3") needs a language identifier to satisfy
MD040; edit the fenced block in .claude/CLAUDE.md so the opening fence reads
```bash (instead of just ```), preserving the two command lines and closing
fence.

In @.github/workflows/build-release.yml:
- Around line 3-6: Add a guard that verifies the pushed tag's commit is
descended from the stable branch before running the release workflow: create a
pre-release job (e.g., verify-stable-ancestry) that runs on the tag event
(on.push.tags) and uses actions/checkout to fetch origin stable, then run git
merge-base --is-ancestor origin/stable $GITHUB_SHA (or equivalent git check) and
fail the job if it returns non-zero; reference the job name
verify-stable-ancestry and the CI env var GITHUB_SHA so the release job
depends_on this verification step.
- Around line 23-25: The CI step named "Install dependencies" currently installs
PyMuPDF with a looser constraint (PyMuPDF>=1.23.0) which diverges from the
tested baseline; update that step in the build-release.yml to install exact test
requirements by running pip install -r requirements.txt (or, if you prefer
minimal change, change the explicit package spec to match the baseline:
pymupdf>=1.24.0,<1.25.0) so the workflow uses the same dependency bounds as the
requirements file and ensures reproducible releases.
- Around line 43-53: The SignPath step is referenced before the unsigned
artifact is uploaded and the release publishes an unsigned binary; reorder the
workflow so the job that creates and uploads the unsigned artifact (artifact
name "JobDocs-unsigned") runs before the SignPath action
(signpath/github-action-submit-signing-request@v1), then add a step after
SignPath to download the signed artifact ("JobDocs-signed") and replace or point
the release input at that signed file instead of build_dist/JobDocs.exe; ensure
the GitHub Release step uses the downloaded "JobDocs-signed" artifact rather
than the original unsigned file.

---

Nitpick comments:
In @.github/workflows/build-release.yml:
- Line 16: The workflow currently uses floating tags like "uses:
actions/checkout@v4" which weakens supply-chain guarantees; update each
third-party action reference (e.g., actions/checkout@v4,
actions/setup-python@..., actions/upload-artifact@...,
softprops/action-gh-release@...) to pin to the corresponding full commit SHA for
that action repository instead of the major/minor tag, replacing the tag strings
with the exact commit SHAs so each "uses:" entry references a specific immutable
commit.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `1c359722-1c07-474a-898b-7b07bc030558`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between f7451a9e5c1f0c425d6922a4fcb63918be861b7d and 62d0c5bb661c6bdbcca77b7cfa86eeb3306f4476.

</details>

<details>
<summary>📒 Files selected for processing (2)</summary>

* `.claude/CLAUDE.md`
* `.github/workflows/build-release.yml`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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
> <details>
> <summary>⚠️ Outside diff range comments (1)</summary><blockquote>
> 
> <details>
> <summary>.github/workflows/build-release.yml (1)</summary><blockquote>
> 
> `29-33`: _⚠️ Potential issue_ | _🟠 Major_
> 
> **Drop repository write scope from the build jobs.**
> 
> These jobs only read the repo and upload artifacts; neither operation requires `contents: write`. Keeping this scope on them increases blast radius if any build step, action, or dependency is compromised. Only `create-release` needs it to publish the GitHub Release.
> 
> 
> 
> <details>
> <summary>Suggested change</summary>
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
> </details>
> 
> Also applies to: 92-96
> 
> <details>
> <summary>🤖 Prompt for AI Agents</summary>
> 
> ```
> Verify each finding against the current code and only fix it if needed.
> 
> In @.github/workflows/build-release.yml around lines 29 - 33, Remove the
> overly-broad repository write permission from the build jobs: in the
> build-windows job (and the other build jobs with the same block) remove or
> change the permissions block so it no longer sets contents: write; these jobs
> only need read access and artifact upload rights, so limit to the minimal scopes
> (or omit the permissions block to use defaults) and leave contents: write only
> on the create-release job that actually publishes the GitHub Release (identify
> and modify the permissions block inside the build-windows job and the equivalent
> build jobs referenced later).
> ```
> 
> </details>
> 
> </blockquote></details>
> 
> </blockquote></details>

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>.github/workflows/build-release.yml (1)</summary><blockquote>

`61-66`: **Avoid uploading the same EXE twice while signing is disabled.**

`JobDocs-unsigned` and `JobDocs-windows` currently contain the same `build_dist/JobDocs.exe`. Keeping one artifact until SignPath is enabled will simplify the release flow and cut redundant upload/storage cost.



<details>
<summary>Possible cleanup</summary>

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
</details>


Also applies to: 83-87

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In @.github/workflows/build-release.yml around lines 61 - 66, The workflow is
uploading the same build_dist/JobDocs.exe twice as artifacts named
JobDocs-unsigned and JobDocs-windows; change the upload steps so only one
artifact is produced when signing is disabled (e.g., guard the JobDocs-windows
upload with the SignPath condition or remove the JobDocs-unsigned step and keep
JobDocs-windows until signing is enabled). Update the steps labeled "Upload
unsigned artifact" and the later "Upload signed/windows" step to reference the
SignPath boolean (or a single upload step) and ensure only one artifact name
(JobDocs-windows or JobDocs-unsigned) is used for build_dist/JobDocs.exe to
avoid duplicate uploads.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.github/workflows/build-release.yml:
- Around line 107-115: The GitHub Actions job currently installs Python deps and
runs PyInstaller on the runner (steps named "Install Python dependencies" and
"Build PyInstaller binary"), which produces a binary tied to the host libc;
instead build the executable inside the Flatpak SDK runtime so it links against
org.freedesktop.Platform//23.08 instead of the runner. Change the workflow to
run PyInstaller under the Flatpak SDK (for example via flatpak run
--command=python3 org.freedesktop.Sdk//23.08 or use flatpak-builder / a
container image matching the SDK) and move the dependency installation and the
PyInstaller invocation into that SDK context (replace the two steps that run pip
install and python -m PyInstaller with equivalent commands executed inside the
Flatpak SDK), ensuring the built binary is produced within build_dist inside the
SDK environment.

In `@linux/flatpak/io.github.i_machine_things.JobDocs.metainfo.xml`:
- Around line 2-34: The AppStream metadata is missing the required license tags:
add a <metadata_license> and a <project_license> element inside the <component
type="desktop-application"> for io.github.i_machine_things.JobDocs using
appropriate SPDX identifiers (for example
<metadata_license>CC0-1.0</metadata_license> and
<project_license>GPL-3.0-or-later</project_license>) so appstreamcli/Flathub
validation passes; ensure the tags are placed alongside the existing <name>,
<summary>, and <url> elements within the component.

In `@linux/flatpak/io.github.i_machine_things.JobDocs.yml`:
- Around line 14-15: The manifest currently grants broad home access via the
--filesystem=home flag; replace this with scoped permissions and explicit
user-access flows: remove --filesystem=home, add a dedicated data path like
--filesystem=xdg-data/JobDocs for app configuration/storage, and rely on file
chooser portals (document portal usage) or explicit per-directory --filesystem
entries only for directories users select (e.g., --filesystem=/path/to/project
when consented). Ensure the YAML entry for filesystem reflects the scoped path
and update any launch/install documentation to show how the app requests
user-selected directories via portals instead of omnibus home access.

---

Outside diff comments:
In @.github/workflows/build-release.yml:
- Around line 29-33: Remove the overly-broad repository write permission from
the build jobs: in the build-windows job (and the other build jobs with the same
block) remove or change the permissions block so it no longer sets contents:
write; these jobs only need read access and artifact upload rights, so limit to
the minimal scopes (or omit the permissions block to use defaults) and leave
contents: write only on the create-release job that actually publishes the
GitHub Release (identify and modify the permissions block inside the
build-windows job and the equivalent build jobs referenced later).

---

Nitpick comments:
In @.github/workflows/build-release.yml:
- Around line 61-66: The workflow is uploading the same build_dist/JobDocs.exe
twice as artifacts named JobDocs-unsigned and JobDocs-windows; change the upload
steps so only one artifact is produced when signing is disabled (e.g., guard the
JobDocs-windows upload with the SignPath condition or remove the
JobDocs-unsigned step and keep JobDocs-windows until signing is enabled). Update
the steps labeled "Upload unsigned artifact" and the later "Upload
signed/windows" step to reference the SignPath boolean (or a single upload step)
and ensure only one artifact name (JobDocs-windows or JobDocs-unsigned) is used
for build_dist/JobDocs.exe to avoid duplicate uploads.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `985ec0eb-6726-45ab-9494-92e3d599ed12`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 552c60246291a2a21d76bbc19effc4812ad6147f and 11521ce4e660fbdf11a56ae3ad89cf35bcdad3e6.

</details>

<details>
<summary>📒 Files selected for processing (5)</summary>

* `.github/workflows/build-release.yml`
* `.gitignore`
* `linux/flatpak/io.github.i_machine_things.JobDocs.desktop`
* `linux/flatpak/io.github.i_machine_things.JobDocs.metainfo.xml`
* `linux/flatpak/io.github.i_machine_things.JobDocs.yml`

</details>

</details>

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

<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>.github/workflows/build-release.yml (1)</summary><blockquote>

`77-81`: **Provision or at least assert `iscc` before invoking it.**

Line 80 invokes `iscc build_scripts\JobDocs.iss` without installing or validating Inno Setup. This makes the Windows release job depend on the hosted runner image's toolset rather than a declared build dependency, which risks pipeline failures if the image configuration changes.

<details>
<summary>♻️ Minimal guard</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In @.github/workflows/build-release.yml around lines 77 - 81, The "Build Windows
installer" step calls the external tool "iscc" (iscc build_scripts\JobDocs.iss)
without ensuring Inno Setup is available; add a guard that either installs Inno
Setup (for example via Chocolatey) or asserts presence and fails fast: use a
PowerShell check like Get-Command iscc -ErrorAction SilentlyContinue and if
missing run choco install innosetup --confirm (or exit with a clear error), then
proceed to set $env:RELEASE_VERSION and run iscc; update the step that currently
contains "iscc build_scripts\JobDocs.iss" to include this installation/check
sequence so the job no longer depends on the runner image having iscc
preinstalled.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.github/workflows/build-release.yml:
- Around line 142-145: The workflow currently copies only the launcher binary
(cp dist/JobDocs/JobDocs) which omits the PyInstaller onedir runtime files;
change the staging step to copy the entire onedir tree (recursively stage the
dist/JobDocs directory into the flatpak staging dir) so all libraries and data
are included, and then update the Flatpak manifest's handling of JobDocs (the
install command "install -Dm755 JobDocs /app/bin/JobDocs" and the JobDocs source
entry) to treat JobDocs as a directory (either set the source type to dir or
adjust build-commands to install the launcher and required runtime files from
the staged directory), ensuring the manifest installs the launcher and its
runtime files rather than expecting a single file.

---

Nitpick comments:
In @.github/workflows/build-release.yml:
- Around line 77-81: The "Build Windows installer" step calls the external tool
"iscc" (iscc build_scripts\JobDocs.iss) without ensuring Inno Setup is
available; add a guard that either installs Inno Setup (for example via
Chocolatey) or asserts presence and fails fast: use a PowerShell check like
Get-Command iscc -ErrorAction SilentlyContinue and if missing run choco install
innosetup --confirm (or exit with a clear error), then proceed to set
$env:RELEASE_VERSION and run iscc; update the step that currently contains "iscc
build_scripts\JobDocs.iss" to include this installation/check sequence so the
job no longer depends on the runner image having iscc preinstalled.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `d0a64a06-ed6c-4265-887a-570dacc35f6d`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between b95329c957824238499eb46595b72a57b371122e and ef7acd1a69e0430d13f20002904ccbf975c80051.

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `.github/workflows/build-release.yml`
* `build_scripts/JobDocs.iss`
* `build_scripts/JobDocs.spec`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@core/module_loader.py`:
- Around line 77-84: The plugin-directory scan currently calls
self.plugins_dir.iterdir() and walks entries without handling
OSError/PermissionError, so update the loops that scan self.plugins_dir (the
block using iterdir() that appends to all_modules and sets
self._plugin_module_dirs, and the similar block around the later scan) to wrap
the directory iteration and per-item filesystem checks in try/except that
catches OSError and PermissionError, logs the exception with context (including
the plugin path and exception message) via the module logger, and
continues—i.e., on exception skip that plugins_dir or item and do not abort
discovery so built-in modules still load.
- Around line 128-143: The plugin loader branch that handles external plugins
(uses variables plugin_dir, module_path, spec, module and spec.loader) does not
set package context so relative imports in plugin packages fail; fix by
assigning spec.submodule_search_locations to the plugin package directory before
exec_module and ensure the parent package (e.g. "plugins.<module_name>") is
present in sys.modules with a ModuleType instance whose __path__ includes
module_path.parent so relative imports (like from .helpers) resolve correctly;
do this immediately after creating the spec (and before spec.loader.exec_module)
and register both the package name and the full spec.name in sys.modules.

In `@core/settings_dialog.py`:
- Around line 333-339: The install flow uses the current textbox value
(plugins_dir_edit.text()) but never persists it, so the application won't see
the new plugins_dir on next startup; update the install handler(s) that use
plugins_dir_str (the block around plugins_dir_edit/Text usage and the other
occurrences referenced) to save the value to your persistent settings (e.g., via
QSettings or the existing settings API) before proceeding with
extraction/install, and/or refuse to treat the install as "restart-ready" until
the in-memory textbox value matches the persisted value—i.e., call the settings
write (e.g., setValue('plugins_dir', plugins_dir_str) or the project's
equivalent) immediately after validating plugins_dir_str and before returning
from the install routine.
- Around line 363-425: The _install_github_plugin function is performing network
and file I/O on the GUI thread; refactor it to run the download/extract/copy
logic inside a background worker (QThread subclass or QRunnable used with
QThreadPool) and only emit signals back to the dialog for UI updates. Move all
calls to urllib.request.urlopen, resp.read(), zipfile.ZipFile.extractall,
shutil.copytree, and any filesystem writes into the worker; have the worker emit
success (module_name and dest path) and error signals (exception message) which
the main thread connects to show QMessageBox.information/QMessageBox.critical,
clear github_repo_edit and set installed flag, and ensure plugins_dir.mkdir is
done in the worker or synchronized before showing success. Keep the UI handler
(button click) lightweight: start the worker and disable the button until
completion.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `2ed3b398-fbbf-4985-828f-b87460e3b6a7`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 6328c6b988dd687547fccc3a1e2b128722e62956 and 06a003d32c95a0c50b9a9bb35d8caaea47c91bc2.

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `core/module_loader.py`
* `core/settings_dialog.py`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>core/settings_dialog.py (1)</summary><blockquote>

`420-421`: _⚠️ Potential issue_ | _🟠 Major_

**Persist `plugins_dir` through the real settings store here.**

`self.settings` is only the dialog-local copy created in `__init__`, so this assignment is still lost if the user installs successfully and then closes with Cancel. The success path says “restart” even though next startup will still read the old persisted `plugins_dir`.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@core/settings_dialog.py` around lines 420 - 421, The dialog currently assigns
plugins_dir_str only to the dialog-local self.settings, which doesn't persist
across app restarts; instead write the value into the application's persistent
settings store (use the existing app/settings manager API used elsewhere in the
codebase) rather than only self.settings, and also update self.settings to keep
the dialog state in sync; locate the code around self.settings and the
plugins_dir_str assignment in settings_dialog.py and replace the local-only
assignment with a call to the global/persistent settings API (e.g., the
project's settings manager set/save method) so the change survives closing with
Cancel and the restart message is accurate.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@core/settings_dialog.py`:
- Around line 71-74: Currently the code deletes dest (plugins_dir / repo) before
copying, which can lose a working plugin if copy fails; change the behavior in
both places where dest is removed and replaced (the block handling dest =
plugins_dir / repo and the analogous block at lines 88-91) to first copy
src_root into a temporary sibling directory (e.g., dest.with_suffix('.tmp') or
dest + '.tmp'), verify the copy succeeded, then atomically move/replace the temp
into place using os.replace or shutil.move, and ensure you remove the temp on
failure so the original dest remains untouched until the new copy is fully
staged.

---

Duplicate comments:
In `@core/settings_dialog.py`:
- Around line 420-421: The dialog currently assigns plugins_dir_str only to the
dialog-local self.settings, which doesn't persist across app restarts; instead
write the value into the application's persistent settings store (use the
existing app/settings manager API used elsewhere in the codebase) rather than
only self.settings, and also update self.settings to keep the dialog state in
sync; locate the code around self.settings and the plugins_dir_str assignment in
settings_dialog.py and replace the local-only assignment with a call to the
global/persistent settings API (e.g., the project's settings manager set/save
method) so the change survives closing with Cancel and the restart message is
accurate.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `086ba464-38ba-4dc7-88f4-505dccfc2ed6`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 06a003d32c95a0c50b9a9bb35d8caaea47c91bc2 and 0f9227abe8f1912de8831fb40bf0f32344d05427.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `build_scripts/JobDocs.iss`
* `core/module_loader.py`
* `core/settings_dialog.py`

</details>

<details>
<summary>✅ Files skipped from review due to trivial changes (1)</summary>

* build_scripts/JobDocs.iss

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-14 — `PR #16: feat: plugins directory with GitHub install support` — review run 1

**Actionable comments posted: 3**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@core/settings_dialog.py`:
- Around line 433-436: The current flow in settings_dialog.py blindly assumes
self._save_callback({'plugins_dir': plugins_dir_str}) persisted the value;
change the call-site in the code that sets self.settings['plugins_dir'] so it
either catches an exception from the callback or checks a boolean success return
(agree on one API), and if persistence failed (callback raised or returned
False) abort before starting the plugin install/worker. Update the contract with
the caller (main._partial_save_settings) so it either raises an IOError on
failure or returns True/False, and in settings_dialog use that to stop the
install worker when persistence did not succeed.
- Around line 453-458: Disable all install-related controls when starting
_PluginInstallWorker: besides calling self.github_install_btn.setEnabled(False),
also disable self.plugins_dir_edit and any dialog action buttons (e.g.,
Save/Cancel) or set a flag to block accept() and reject() while
self._install_worker is active; re-enable those controls (or clear the blocking
flag) in the _on_plugin_install_success and _on_plugin_install_error handlers
where worker finishes, and ensure this same behavior is applied to the code
paths around lines 460-474 that start the worker so the dialog cannot be
edited/closed while installation is running.
- Around line 90-103: The current swap removes the live plugin
(shutil.rmtree(dest)) before ensuring the temp rename succeeded, which can leave
no plugin if rename fails; change the sequence to perform an atomic replace of
dest with the temp copy instead of deleting dest first: after
shutil.copytree(src, tmp_dest) call tmp_dest.replace(dest) (or
os.replace(tmp_dest, dest)) in place of tmp_dest.rename(dest), keep the existing
exception handler to rmtree tmp_dest on failure, and remove the explicit
shutil.rmtree(dest) call so the live plugin is only replaced when the atomic
replace succeeds (refer to tmp_dest, dest, shutil.copytree, tmp_dest.rename in
the diff).
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `4d2fe782-5341-4cf9-9edc-e4805c740200`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 0f9227abe8f1912de8831fb40bf0f32344d05427 and d5791453f964a1cfe6c38cfec135570d649d6c5e.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (2)</summary>

* `core/settings_dialog.py`
* `main.py`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (1)</summary>

* main.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-14 — `PR #16: feat: plugins directory with GitHub install support` — review run 2



<details>
<summary>♻️ Duplicate comments (2)</summary><blockquote>

<details>
<summary>core/settings_dialog.py (2)</summary><blockquote>

`97-99`: _⚠️ Potential issue_ | _🟠 Major_

**Preserve the current plugin until the final swap succeeds.**

Line 98 deletes the live plugin before Line 99 is guaranteed to succeed. If rename fails, users lose the working plugin.

  

<details>
<summary>Proposed safer swap (with rollback)</summary>

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
</details>

```shell
#!/bin/bash
# Verify current non-rollback swap flow in worker
sed -n '90,110p' core/settings_dialog.py
```

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@core/settings_dialog.py` around lines 97 - 99, The current swap deletes the
live plugin via shutil.rmtree(dest) before tmp_dest.rename(dest) succeeds;
change the flow to preserve/rollback by first renaming/moving the current dest
to a backup name (e.g., dest_backup) instead of deleting it, then rename
tmp_dest to dest, and on any failure of tmp_dest.rename(dest) attempt to restore
by renaming dest_backup back to dest; only remove the backup after the new dest
is successfully in place; update the logic around dest.exists(),
shutil.rmtree(dest) and tmp_dest.rename(dest) accordingly and ensure exceptions
during rename trigger the rollback rename of the backup.
```

</details>

---

`438-443`: _⚠️ Potential issue_ | _🟠 Major_

**Block dialog edits/close while plugin install worker is running.**

Only the Install button is disabled. Users can still Save/Cancel/close, which can race worker callbacks against disposed UI state.

  

<details>
<summary>Proposed guard for in-flight install lifecycle</summary>

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
</details>

```shell
#!/bin/bash
# Verify install-state handling and whether Save/Cancel/close are guarded
rg -n -C2 "github_install_btn.setEnabled|button_box|def reject|_install_in_progress|worker.start" core/settings_dialog.py
```


Also applies to: 445-459

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@core/settings_dialog.py` around lines 438 - 443, The dialog allows
Save/Cancel/close while a plugin install worker (created in the block that sets
self.github_install_btn and self._install_worker and starts worker) is running,
which can race with callbacks
(_on_plugin_install_success/_on_plugin_install_error) against a disposed UI; add
an in-flight guard: introduce a boolean like self._install_in_progress set True
before worker.start() and False in both _on_plugin_install_success and
_on_plugin_install_error, disable the dialog buttons (e.g. the button box, and
block reject/accept/close) while _install_in_progress is True, and make
reject/accept early-return when the flag is set so callbacks won't touch
disposed widgets.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Duplicate comments:
In `@core/settings_dialog.py`:
- Around line 97-99: The current swap deletes the live plugin via
shutil.rmtree(dest) before tmp_dest.rename(dest) succeeds; change the flow to
preserve/rollback by first renaming/moving the current dest to a backup name
(e.g., dest_backup) instead of deleting it, then rename tmp_dest to dest, and on
any failure of tmp_dest.rename(dest) attempt to restore by renaming dest_backup
back to dest; only remove the backup after the new dest is successfully in
place; update the logic around dest.exists(), shutil.rmtree(dest) and
tmp_dest.rename(dest) accordingly and ensure exceptions during rename trigger
the rollback rename of the backup.
- Around line 438-443: The dialog allows Save/Cancel/close while a plugin
install worker (created in the block that sets self.github_install_btn and
self._install_worker and starts worker) is running, which can race with
callbacks (_on_plugin_install_success/_on_plugin_install_error) against a
disposed UI; add an in-flight guard: introduce a boolean like
self._install_in_progress set True before worker.start() and False in both
_on_plugin_install_success and _on_plugin_install_error, disable the dialog
buttons (e.g. the button box, and block reject/accept/close) while
_install_in_progress is True, and make reject/accept early-return when the flag
is set so callbacks won't touch disposed widgets.
```

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `33c76dda-ae89-418c-b244-735b3c652f87`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between d5791453f964a1cfe6c38cfec135570d649d6c5e and 0890df4e3d4e0cc3ea16cffff2bf9eb28ff18f29.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (2)</summary>

* `core/settings_dialog.py`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-14 — `PR #17: fix: add difflib to hiddenimports for plugin compatibility` — review run 1

**Actionable comments posted: 1**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@core/settings_dialog.py`:
- Around line 29-30: The constructor signature uses default None for typed
parameters without Optional: update def __init__ to annotate available_modules
as Optional[List[tuple]] and save_callback as Optional[Callable[..., Any]] (or
Optional[Callable] if simpler), import Optional and Callable (and Any if not
already) from typing, and keep the defaults = None; adjust references to
available_modules/save_callback within the class if necessary to satisfy the new
types.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `5af0e09e-d66a-4e81-938f-bb98200fc7f1`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between c1067e4bd0a622cac8745c6ba7f82d6fc097e960 and 1eebe8483c12d53db1444ecaae592b7813b938ab.

</details>

<details>
<summary>📒 Files selected for processing (3)</summary>

* `build_scripts/JobDocs.spec`
* `core/settings_dialog.py`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-14 — `PR #18: fix: bundle pandas/openpyxl for plugins and restore plugin installer` — review run 1

**Actionable comments posted: 4**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@main.py`:
- Around line 50-51: The code currently assumes branches ('main','master') in
the for loop that constructs zip_url, which will fail for repos with other
default branches; change the logic to first query the repo metadata from
GitHub's API (GET https://api.github.com/repos/{owner}/{repo}) and read the
default_branch field, then build zip_url using that default_branch value; if the
API call is rate-limited or fails, fall back to prompting the user for a branch
name (or only then try the ('main','master') fallback). Update the code paths
that construct zip_url (the loop using zip_url and any related download
functions) to use the resolved branch variable instead of the hard-coded tuple.
- Around line 72-85: The code currently picks the first directory with module.py
(candidates list -> module_folder) which is ambiguous; change the logic to fail
fast unless there is exactly one candidate: after building candidates (variable
candidates), if len(candidates) == 0 emit the existing error, if len(candidates)
> 1 emit an error listing the ambiguous candidate names (or count) and return,
otherwise proceed setting module_folder = candidates[0] and computing dest,
module_name, src as before; update any tests or messages to mention ambiguous
plugin roots so callers know to disambiguate.
- Around line 87-98: The current sequence removes the existing plugin (dest)
before committing the new copy, risking data loss if tmp_dest.rename(dest)
fails; change to a safe swap: after creating tmp_dest (tmp_dest =
dest.with_name(dest.name + '.tmp')), do not delete dest—first move/rename the
current dest to a backup (e.g., backup_dest = dest.with_name(dest.name +
'.backup')) ensuring any preexisting backup is removed, then rename tmp_dest to
dest, and only after successful rename remove the backup; on any exception,
attempt to restore from backup (rename backup_dest back to dest) and clean up
tmp_dest and backup_dest with ignore_errors=True. Ensure all operations
reference tmp_dest, dest, src and handle exceptions to avoid leaving the system
without a working plugin.
- Around line 44-48: The plugins_dir.mkdir call in run executes before the
worker's try block so a PermissionError will terminate the thread without
invoking the worker's error handling; wrap the directory creation in the same
error-handling as the worker (or add a local try/except around
plugins_dir.mkdir) and on failure call the worker's error-emission path (e.g.,
call self.error or the same error handler used inside run) passing the caught
exception, then abort/return to avoid continuing; locate symbols run,
self._plugins_dir, plugins_dir.mkdir and the worker's existing try/except to
integrate the mkdir into that error flow.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `5485000d-3ec1-4426-9e5b-fcd82626e30e`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between ce304ec214964c6ba34efc2c08887f2aa3ca26eb and 4ff59fb26bb2512772bd11b08022001244156741.

</details>

<details>
<summary>📒 Files selected for processing (2)</summary>

* `build_scripts/JobDocs.spec`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-14 — `PR #19: fix: isolate plugin deps into plugin-local deps/ directory` — review run 1

**Actionable comments posted: 4**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@main.py`:
- Around line 55-57: The current creation of deps_dir and subsequent pip install
into that path (variable deps_dir) can leave stale/partial packages; change the
flow to create a fresh temporary directory (e.g., temp_deps_dir), run pip
install --target into that temp directory, verify success, then atomically
replace/move temp_deps_dir to deps_dir (remove or backup existing deps_dir only
after successful install) to avoid overlaying and leftover files—apply the same
pattern for the other install sites referenced around the blocks using deps_dir
(lines noted 72-77 and 91-92) so installs are always performed into a clean temp
folder and swapped into place on success.
- Around line 103-106: The returned error message omits the --target flag so
users run pip globally; update the string construction that returns the manual
recovery command to include the plugin-local target by adding --target
"{deps_dir}" (use the existing deps_dir variable alongside req_file and
last_err) so the suggested command is pip install --target "{deps_dir}" -r
"{req_file}" and preserve the existing error text fallback (last_err or 'no
usable Python found on PATH').
- Around line 61-67: When sys.frozen is true the code currently appends system
Python names into candidates before ever trying the embedded pip, causing wheels
to be chosen for the system ABI; change the candidates construction so that when
getattr(sys, 'frozen', False) is True you try the bundled pip API
(pip._internal) first and only then extend with ['python','python3','py'] as a
last resort—i.e., ensure the candidates list contains a pip._internal attempt
first in frozen mode and falls back to the system Python names otherwise.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `564b50cc-67cd-49b3-b031-57621bf81fa5`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 09700c52e8b62d3c6ea0ded20e7f767f2741e370 and f00a384bba3632eca3a8fda3be7bb02ee247a6d7.

</details>

<details>
<summary>📒 Files selected for processing (4)</summary>

* `.gitignore`
* `build_scripts/JobDocs.spec`
* `core/module_loader.py`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>🧹 Nitpick comments (3)</summary><blockquote>

<details>
<summary>.gitignore (1)</summary><blockquote>

`54-54`: **Consider anchoring `AddonPackages/` to repo root.**

If this is only meant for the root-level dev symlink, use `/AddonPackages/` to avoid unintentionally ignoring same-named nested directories.  

<details>
<summary>Diff suggestion</summary>

```diff
-AddonPackages/
+/AddonPackages/
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In @.gitignore at line 54, The .gitignore entry "AddonPackages/" should be
anchored to the repository root to avoid ignoring same-named nested directories;
replace "AddonPackages/" with "/AddonPackages/" (i.e., update the AddonPackages/
pattern to start with a leading slash) so it only ignores the root-level dev
symlink.
```

</details>

</blockquote></details>
<details>
<summary>build_scripts/JobDocs.spec (1)</summary><blockquote>

`156-166`: **Refresh this note to match the current plugin install model.**

This block still describes the removed `deps/` + `sys.path` flow, but `main.py` now shells out to `python -m pip install -r ...` into the active environment. Leaving the old description here will send the next person debugging packaging down the wrong path.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@build_scripts/JobDocs.spec` around lines 156 - 166, Update the comment block
that currently references the removed "deps/" folder and "sys.path" manipulation
to reflect the new plugin install model: replace the description about plugins
managing deps in a deps/ subfolder and the module loader prepending sys.path
with a note that main.py now shells out to "python -m pip install -r
<requirements.txt>" into the active environment (i.e., installs into the running
Python environment), and remove or reword any instructions that suggest using
pip --target deps/ or modifying sys.path so future debuggers are directed to
check main.py's shell-out install behavior instead.
```

</details>

</blockquote></details>
<details>
<summary>launcher/launcher.rc (1)</summary><blockquote>

`11-12`: **Drive the EXE version metadata from the build, not a literal.**

The installer version already comes from `RELEASE_VERSION`, but the launcher resource is pinned to `0.6.0.0`. The next tag will ship an EXE whose file properties disagree with the installer and release asset name unless this is updated by hand. 


Also applies to: 25-30

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@launcher/launcher.rc` around lines 11 - 12, The FILEVERSION and
PRODUCTVERSION entries in launcher.rc are hard-coded to 0,6,0,0; change
launcher.rc to derive these values from the build/release variables (e.g.,
RELEASE_VERSION or build-time VERSION macros) instead of literals so the EXE
metadata matches the installer and release tag—replace the numeric literals used
in FILEVERSION and PRODUCTVERSION (and the corresponding version strings around
lines 25-30) with preprocessor-expanded tokens or injected variables (e.g.,
VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH, VERSION_BUILD or a single
RELEASE_VERSION split into components) so the resource gets populated at build
time.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In @.github/workflows/build-release.yml:
- Around line 48-65: The workflow currently downloads the Python embeddable ZIP
and a floating get-pip.py without verification; update the three steps
("Download Python embeddable", "Enable site-packages in embedded Python",
"Bootstrap pip into embedded Python") to validate payloads before use by pinning
expected hashes and failing on mismatch: add variables for the expected SHA256
for the embeddable ZIP and for get-pip.py, after Invoke-WebRequest compute
Get-FileHash on the downloaded files and compare to the pinned values (fail/exit
when they differ), or alternatively vendor the get-pip.py into the repo and
reference it instead of fetching, and only then run Expand-Archive and
runtime\python.exe get-pip.py; ensure the workflow treats any checksum mismatch
as a hard error so release artifacts never use unverified remote payloads.
- Around line 71-80: The staging step omits README.md so show_readme() (which
expects README.md next to main.py) will fail in the packaged app; update the
$src_items array in the "Stage app source tree" PowerShell step to include
'README.md' alongside 'main.py','core','modules','shared', etc., so README.md is
copied into the app directory during the build.

In `@launcher/launcher.c`:
- Around line 51-66: CreateProcessW is currently called but its BOOL return
value isn't checked, so failures are swallowed and CloseHandle is
unconditionally called on possibly invalid handles; update the code around
CreateProcessW to capture its return (e.g., BOOL created = CreateProcessW(...)),
if created == FALSE call GetLastError(), format or include that error code/text
and show a user-visible error (e.g., MessageBoxW with a descriptive message
referencing python/cmdline/exe_path) and return non-zero (e.g., return 1); only
call CloseHandle on pi.hProcess and pi.hThread when they are valid
(non-NULL/INVALID_HANDLE_VALUE) to avoid closing invalid handles. Ensure you
reference CreateProcessW, pi, si, python, cmdline, and exe_path when
implementing the checks and message.

In `@main.py`:
- Around line 45-69: The packaged Flatpak build writes plugins under a read-only
/app so pip installs from _install_deps will fail; update either
_get_plugins_dir or _install_deps to avoid attempting installs into /app: detect
Flatpak (e.g., via os.getenv('FLATPAK_ID') or by checking if plugin_dir is under
'/app' or not writable) and then (a) return a per-user writable path (use
XDG_DATA_HOME or "~/.var/app/<FLATPAK_ID>/plugins") from _get_plugins_dir, or
(b) in _install_deps short-circuit and return a clear non-empty warning string
when plugin_dir is not writable/read-only so pip is not invoked. Reference the
_get_plugins_dir and _install_deps functions when making the change.

---

Nitpick comments:
In @.gitignore:
- Line 54: The .gitignore entry "AddonPackages/" should be anchored to the
repository root to avoid ignoring same-named nested directories; replace
"AddonPackages/" with "/AddonPackages/" (i.e., update the AddonPackages/ pattern
to start with a leading slash) so it only ignores the root-level dev symlink.

In `@build_scripts/JobDocs.spec`:
- Around line 156-166: Update the comment block that currently references the
removed "deps/" folder and "sys.path" manipulation to reflect the new plugin
install model: replace the description about plugins managing deps in a deps/
subfolder and the module loader prepending sys.path with a note that main.py now
shells out to "python -m pip install -r <requirements.txt>" into the active
environment (i.e., installs into the running Python environment), and remove or
reword any instructions that suggest using pip --target deps/ or modifying
sys.path so future debuggers are directed to check main.py's shell-out install
behavior instead.

In `@launcher/launcher.rc`:
- Around line 11-12: The FILEVERSION and PRODUCTVERSION entries in launcher.rc
are hard-coded to 0,6,0,0; change launcher.rc to derive these values from the
build/release variables (e.g., RELEASE_VERSION or build-time VERSION macros)
instead of literals so the EXE metadata matches the installer and release
tag—replace the numeric literals used in FILEVERSION and PRODUCTVERSION (and the
corresponding version strings around lines 25-30) with preprocessor-expanded
tokens or injected variables (e.g., VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH,
VERSION_BUILD or a single RELEASE_VERSION split into components) so the resource
gets populated at build time.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `0a409c05-78dd-4c0c-b826-fd7a77d7ea94`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 09700c52e8b62d3c6ea0ded20e7f767f2741e370 and 0497fc59fac356810658f46cc56a54a059f686f6.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (7)</summary>

* `.github/workflows/build-release.yml`
* `.gitignore`
* `build_scripts/JobDocs.iss`
* `build_scripts/JobDocs.spec`
* `launcher/launcher.c`
* `launcher/launcher.rc`
* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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



<details>
<summary>♻️ Duplicate comments (2)</summary><blockquote>

<details>
<summary>main.py (1)</summary><blockquote>

`399-414`: _⚠️ Potential issue_ | _🟠 Major_

**Flatpak still resolves plugins into the bundled app tree.**

This only distinguishes the embedded-Windows layout from source layout. The Linux release is still a Flatpak, so `_get_plugins_dir()` will resolve next to the frozen bundle, and `_PluginInstallWorker` then tries to create/copy plugin files there before `_install_deps()` runs. In Flatpak, the app bundle under `/app` is read-only, while per-user data belongs under `$XDG_DATA_HOME` / `~/.var/app/$FLATPAK_ID/data`, so plugin install remains broken on Linux. Return a per-user writable path when `FLATPAK_ID` is set, or disable plugin installation in that mode. ([docs.flatpak.org](https://docs.flatpak.org/zh-cn/latest/sandbox-permissions.html?utm_source=openai))

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@main.py` around lines 399 - 414, The _get_plugins_dir function currently only
switches between embedded and source layouts and can resolve to the read-only
Flatpak bundle; update _get_plugins_dir to detect Flatpak by checking the
FLATPAK_ID environment variable and return a writable per-user plugins path
(prefer XDG_DATA_HOME/plugins or fallback to
~/.var/app/{FLATPAK_ID}/data/plugins) when FLATPAK_ID is set, or alternatively
return None/raise so _PluginInstallWorker/_install_deps know to skip plugin
installation in Flatpak mode; ensure references to _PluginInstallWorker and
_install_deps handle the new None/skip behavior if you choose that route.
```

</details>

</blockquote></details>
<details>
<summary>.github/workflows/build-release.yml (1)</summary><blockquote>

`35-76`: _⚠️ Potential issue_ | _🟠 Major_

**Pin the pip bootstrap input.**

`python -m pip install --target ... pip` still pulls whatever stable `pip` release PyPI serves on build day, and the `python` binary itself comes from the mutable `windows-latest` image. That makes the Windows installer drift over time even when the repo hasn’t changed. Please bootstrap from a pinned wheel or at least a pinned `pip==...` plus hash, and use a specific runner/interpreter for that download step. GitHub notes that `-latest` images migrate over time and recommends `actions/setup-python` for consistent behavior; pip installs stable releases by default when no version is specified. ([github.com](https://github.com/actions/runner-images?utm_source=openai))

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In @.github/workflows/build-release.yml around lines 35 - 76, The bootstrap step
in the build-windows job currently runs "python -m pip install --target
runtime\Lib\site-packages --no-deps pip" without a pinned pip version or hash
and relies on the mutable windows-latest image; change the "Bootstrap pip into
embedded Python" step so it installs a specific pip release (e.g. pip==23.2.1)
with a pinned hash or installs from a vendored wheel file instead of an unpinned
PyPI install, and ensure the runner/interpreter is fixed by adding or using
actions/setup-python to pin the Python runtime before running
runtime\python.exe; update the commands referenced (the install invocation and
the runtime\python.exe -m pip --version check) to reflect the pinned artifact
and verify its checksum.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Duplicate comments:
In @.github/workflows/build-release.yml:
- Around line 35-76: The bootstrap step in the build-windows job currently runs
"python -m pip install --target runtime\Lib\site-packages --no-deps pip" without
a pinned pip version or hash and relies on the mutable windows-latest image;
change the "Bootstrap pip into embedded Python" step so it installs a specific
pip release (e.g. pip==23.2.1) with a pinned hash or installs from a vendored
wheel file instead of an unpinned PyPI install, and ensure the
runner/interpreter is fixed by adding or using actions/setup-python to pin the
Python runtime before running runtime\python.exe; update the commands referenced
(the install invocation and the runtime\python.exe -m pip --version check) to
reflect the pinned artifact and verify its checksum.

In `@main.py`:
- Around line 399-414: The _get_plugins_dir function currently only switches
between embedded and source layouts and can resolve to the read-only Flatpak
bundle; update _get_plugins_dir to detect Flatpak by checking the FLATPAK_ID
environment variable and return a writable per-user plugins path (prefer
XDG_DATA_HOME/plugins or fallback to ~/.var/app/{FLATPAK_ID}/data/plugins) when
FLATPAK_ID is set, or alternatively return None/raise so
_PluginInstallWorker/_install_deps know to skip plugin installation in Flatpak
mode; ensure references to _PluginInstallWorker and _install_deps handle the new
None/skip behavior if you choose that route.
```

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `c3f34243-fac6-441b-9efe-a9835341f695`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 0497fc59fac356810658f46cc56a54a059f686f6 and 1c57a11293dbb3c97308bfde1dbe07726654b5fb.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (6)</summary>

* `.github/workflows/build-release.yml`
* `.gitignore`
* `build_scripts/JobDocs.spec`
* `launcher/launcher.c`
* `launcher/launcher.rc`
* `main.py`

</details>

<details>
<summary>✅ Files skipped from review due to trivial changes (2)</summary>

* .gitignore
* launcher/launcher.rc

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (1)</summary>

* build_scripts/JobDocs.spec

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@main.py`:
- Around line 580-585: The success message in _on_plugin_install_success
incorrectly promises the plugin will load even when dep_warning is set; update
the messaging so that when dep_warning is truthy (requirements skipped/failed)
the dialog text says the plugin files were copied but the plugin may not load
until dependencies are resolved and include the dep_warning details (use
QMessageBox.warning with msg + dep_warning), while when dep_warning is falsy
keep the original "Restart JobDocs to load it." wording (use
QMessageBox.information); reference function _on_plugin_install_success and
variables module_name, dest, dep_warning to locate and change the conditional
message text accordingly.
- Around line 57-76: The two user-facing instructions advising "pip install -r
\"{req_file}\"" should be changed to recommend invoking pip with the current
interpreter to avoid PATH/venv confusion; update the Flatpak message and the
failure message to instruct users to run the installer via sys.executable (e.g.
use the interpreter-qualified form: <sys.executable> -m pip install -r
"{req_file}") so the guidance is accurate; locate the strings near the Flatpak
branch (uses os.getenv('FLATPAK_ID') and req_file) and the subprocess
error-handling block (uses subprocess.run, result.returncode, and err) and
replace the bare "pip install -r ..." instructions with the
interpreter-qualified form using sys.executable.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `531f725e-fb26-4374-a1a5-b6a39b9ab6b7`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 1c57a11293dbb3c97308bfde1dbe07726654b5fb and 3168a7d190279d965f118367178a6ea8b9b17017.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (2)</summary>

* `.github/workflows/build-release.yml`
* `main.py`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (1)</summary>

* .github/workflows/build-release.yml

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>♻️ Duplicate comments (1)</summary><blockquote>

<details>
<summary>main.py (1)</summary><blockquote>

`57-63`: _⚠️ Potential issue_ | _🟠 Major_

**Flatpak still surfaces a recovery command that targets the read-only runtime.**

This branch correctly skips auto-install on Flatpak, but the returned `sys.executable -m pip ...` advice still points users at the same sandboxed interpreter you just deemed unwritable. For dependency-backed plugins, that leaves no working recovery path. Either remove the manual command here and state that manual dependency install is unsupported in Flatpak builds, or switch Flatpak to a supported user-writable install target.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@main.py` around lines 57 - 63, The Flatpak branch currently returns a
recovery command using sys.executable which points to the read-only runtime;
update the returned message in the FLATPAK_ID branch to avoid suggesting the
unwritable runtime. Replace the manual command that uses sys.executable -m pip
install -r "{req_file}" with either (a) a clear statement that manual dependency
installation is unsupported inside Flatpak builds (remove the pip command), or
(b) a supported user-writable alternative such as recommending the host/system
Python or a user-install target (e.g., "python -m pip install --user -r
\"{req_file}\"" or instructing to install on the host), and ensure the message
references req_file but not the sandboxed sys.executable.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@main.py`:
- Around line 62-63: The printed "Install manually" recovery command uses
sys.executable without quotes, which breaks on paths containing spaces; update
both occurrences where the string is constructed (the f-string that includes
sys.executable and req_file) to wrap sys.executable in quotes (e.g.,
f'"{sys.executable}" -m pip install -r "{req_file}"') so the copy-paste command
is safe on Windows; ensure you change both places referenced in the diff (the
two f-strings that include sys.executable and req_file).
- Around line 47-50: The docstring in main.py containing "Install plugin
requirements into the embedded Python's site-packages." includes the sequence
runtime\python.exe which produces an invalid escape; update that docstring (the
triple-quoted string starting with "Install plugin requirements...") to either
escape the backslash as runtime\\python.exe or convert the docstring to a raw
string (e.g., r"""...""") so the backslash is treated literally.

---

Duplicate comments:
In `@main.py`:
- Around line 57-63: The Flatpak branch currently returns a recovery command
using sys.executable which points to the read-only runtime; update the returned
message in the FLATPAK_ID branch to avoid suggesting the unwritable runtime.
Replace the manual command that uses sys.executable -m pip install -r
"{req_file}" with either (a) a clear statement that manual dependency
installation is unsupported inside Flatpak builds (remove the pip command), or
(b) a supported user-writable alternative such as recommending the host/system
Python or a user-install target (e.g., "python -m pip install --user -r
\"{req_file}\"" or instructing to install on the host), and ensure the message
references req_file but not the sandboxed sys.executable.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `b45528b0-9c0e-423e-aec9-9aed4edd0b98`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 3168a7d190279d965f118367178a6ea8b9b17017 and 7e62ebbabe8bca488cef703a55a2b26858329033.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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



<details>
<summary>🧹 Nitpick comments (1)</summary><blockquote>

<details>
<summary>main.py (1)</summary><blockquote>

`60-63`: **Remove extraneous `f` prefixes from strings without placeholders.**

Lines 61 and 62 are f-strings but contain no interpolation placeholders. This is flagged by Ruff (F541).


<details>
<summary>Suggested fix</summary>

```diff
         if os.getenv('FLATPAK_ID'):
             return (
-                f"\n\nDependency installation is not supported inside a Flatpak build.\n"
-                f"Install the plugin's dependencies on the host system before use."
+                "\n\nDependency installation is not supported inside a Flatpak build.\n"
+                "Install the plugin's dependencies on the host system before use."
             )
```
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@main.py` around lines 60 - 63, The returned multiline string uses unnecessary
f-strings (no interpolation) which triggers Ruff F541; remove the leading f
prefixes from the two string literals in the return expression (the strings
beginning with "Dependency installation is not supported inside a Flatpak
build." and "Install the plugin's dependencies on the host system before use.")
so they are plain string literals instead of f-strings.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Nitpick comments:
In `@main.py`:
- Around line 60-63: The returned multiline string uses unnecessary f-strings
(no interpolation) which triggers Ruff F541; remove the leading f prefixes from
the two string literals in the return expression (the strings beginning with
"Dependency installation is not supported inside a Flatpak build." and "Install
the plugin's dependencies on the host system before use.") so they are plain
string literals instead of f-strings.
```

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `e1a7e1e5-a2d9-4ecc-a984-81119a45eb2e`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 7e62ebbabe8bca488cef703a55a2b26858329033 and 1c2ff7c951b829c8963cab8faf1f6fa4e0f2bedb.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `main.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@tests/test_utils.py`:
- Line 18: Change the mutable class attribute EXTS from a list to an immutable
tuple to fix the RUF012 warning: replace EXTS = ['.pdf', '.dwg', '.dxf'] with
EXTS = ('.pdf', '.dwg', '.dxf') in tests/test_utils.py (symbol: EXTS) so the
class attribute is no longer a mutable list.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `cd3123db-b941-44e3-8613-f93ed5b39814`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 1227395f7b0f58c57a241b0af435167ca54a9b8b and 9b944bf956ca932df4ced87403dddc03581f4c6c.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `windows/icon.ico` is excluded by `!**/*.ico`

</details>

<details>
<summary>📒 Files selected for processing (5)</summary>

* `.github/workflows/build-release.yml`
* `pytest.ini`
* `requirements-dev.txt`
* `tests/__init__.py`
* `tests/test_utils.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-15 — `PR #22: fix: add ../app to embedded Python _pth so launcher works` — review run 2

**Actionable comments posted: 1**

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@build_scripts/JobDocs.iss`:
- Around line 50-53: The uninstall script claims to "keep installed plugins'
data" but unconditionally deletes the "{app}\plugins" directory; update the
logic in JobDocs.iss so removal of "{app}\plugins" is conditional on the user's
uninstall choice (or remove the unconditional "Type: filesandordirs; Name:
\"{app}\plugins\"" entry), ensuring that when the uninstall prompt chooses to
keep plugins the plugins directory is not deleted; adjust the corresponding
entries around the other similar entries (the block covering the plugin-related
Type: filesandordirs lines) so the behavior matches the prompt and preserves
embedded install plugin data referenced by main.py:399-423.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `61c2bbb1-35e4-40cd-b417-72f92019f80a`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 9b944bf956ca932df4ced87403dddc03581f4c6c and d90d5b41d7441044f7ac1ccc63945a9d735401f9.

</details>

<details>
<summary>⛔ Files ignored due to path filters (2)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`
* `windows/icon.ico` is excluded by `!**/*.ico`

</details>

<details>
<summary>📒 Files selected for processing (1)</summary>

* `build_scripts/JobDocs.iss`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

---

## 2026-04-16 — `PR #24: feat: batch print drawings from job/quote/search` — review run 1



<details>
<summary>🧹 Nitpick comments (3)</summary><blockquote>

<details>
<summary>shared/utils.py (2)</summary><blockquote>

`189-189`: **Redundant import.**

`subprocess` is now imported at module level (line 11), making this local import unnecessary.


<details>
<summary>🧹 Remove redundant import</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@shared/utils.py` at line 189, There is a redundant local "import subprocess"
that duplicates the module-level import; remove the local import statement so
the code uses the existing top-level subprocess import (search for the local
"import subprocess" occurrence in shared/utils.py and delete it, leaving any
functions or code that reference subprocess unchanged).
```

</details>

---

`206-214`: **Silent failures when printing files.**

The function silently skips non-files and doesn't report errors if `os.startfile()` or `lp` fails. Users won't know if printing failed (e.g., `lp` not installed on Linux, permission denied, or unsupported file type).

Consider returning status information or raising exceptions for critical failures.


<details>
<summary>♻️ Suggested improvement with basic error handling</summary>

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
</details>

Note: The static analysis warnings (S603, S607) about subprocess security are low-risk here since paths originate from user-selected files that pass `os.path.isfile()` validation, but consider using `shutil.which('lp')` to verify availability before attempting to print on non-Windows systems.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@shared/utils.py` around lines 206 - 214, The print_files function currently
swallows non-files and printing errors; update print_files to validate
availability of the print backend and report failures by returning per-path
status or raising on critical errors: inside print_files, for each path
(function print_files), if not os.path.isfile(path) record a failure status (or
raise if that should be fatal); on Windows wrap os.startfile(path, 'print') in a
try/except and capture/return the exception information; on non-Windows first
check shutil.which('lp') and if missing return an informative failure for every
path, otherwise call subprocess.Popen(['lp', path]) but capture exceptions (and
subprocess errors) and return or raise the error; ensure the function signature
and callers are adjusted to accept a mapping/list of results (e.g., path ->
success/error) or document which exceptions are raised.
```

</details>

</blockquote></details>
<details>
<summary>modules/search/module.py (1)</summary><blockquote>

`759-764`: **Minor UX consideration: Context menu visibility depends on clicked item.**

The "Print Selected" action only appears when right-clicking on a file item (line 759: `if is_file:`). If a user has multiple files selected but right-clicks on a folder row, the print option won't appear.

This is a minor edge case and the current behavior is acceptable, but you could consider showing "Print Selected" whenever there's at least one file in the selection.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@modules/search/module.py` around lines 759 - 764, The context menu currently
adds "Print Selected" only when the clicked row is a file (controlled by
is_file); change this to show the action whenever the current selection contains
at least one file. Inside the context-menu construction (the block that checks
is_file and adds print_action), replace the is_file-only check with a
selection-based check that inspects the view/model selection (use the same
selection APIs you already use elsewhere in this class) to determine if any
selected item is a file, and if so call menu.addAction("Print Selected") and
connect it to _print_selected_folder_files; keep the existing "Blueprints Path"
logic and lambda to _blueprints_path_action(path) unchanged.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Nitpick comments:
In `@modules/search/module.py`:
- Around line 759-764: The context menu currently adds "Print Selected" only
when the clicked row is a file (controlled by is_file); change this to show the
action whenever the current selection contains at least one file. Inside the
context-menu construction (the block that checks is_file and adds print_action),
replace the is_file-only check with a selection-based check that inspects the
view/model selection (use the same selection APIs you already use elsewhere in
this class) to determine if any selected item is a file, and if so call
menu.addAction("Print Selected") and connect it to _print_selected_folder_files;
keep the existing "Blueprints Path" logic and lambda to
_blueprints_path_action(path) unchanged.

In `@shared/utils.py`:
- Line 189: There is a redundant local "import subprocess" that duplicates the
module-level import; remove the local import statement so the code uses the
existing top-level subprocess import (search for the local "import subprocess"
occurrence in shared/utils.py and delete it, leaving any functions or code that
reference subprocess unchanged).
- Around line 206-214: The print_files function currently swallows non-files and
printing errors; update print_files to validate availability of the print
backend and report failures by returning per-path status or raising on critical
errors: inside print_files, for each path (function print_files), if not
os.path.isfile(path) record a failure status (or raise if that should be fatal);
on Windows wrap os.startfile(path, 'print') in a try/except and capture/return
the exception information; on non-Windows first check shutil.which('lp') and if
missing return an informative failure for every path, otherwise call
subprocess.Popen(['lp', path]) but capture exceptions (and subprocess errors)
and return or raise the error; ensure the function signature and callers are
adjusted to accept a mapping/list of results (e.g., path -> success/error) or
document which exceptions are raised.
```

</details>

---

<details>
<summary>ℹ️ Review info</summary>

<details>
<summary>⚙️ Run configuration</summary>

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `cb1eaf8e-bef8-4c5d-ab08-127c7fc2b616`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 31d95fdc9858f9d0986f681c14cb7a3766eea4d3 and 7221b1e56b43f6e1f7f36c24e12d20cfa31c7d47.

</details>

<details>
<summary>📒 Files selected for processing (6)</summary>

* `modules/job/module.py`
* `modules/job/ui/job_tab.ui`
* `modules/quote/module.py`
* `modules/quote/ui/quote_tab.ui`
* `modules/search/module.py`
* `shared/utils.py`

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->

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

<details>
<summary>🧹 Nitpick comments (4)</summary><blockquote>

<details>
<summary>shared/widgets.py (3)</summary><blockquote>

`1380-1393`: **Type hints reference undefined names at module scope.**

The string-based type hints (`'QPainter'`, `'QImage'`, `'QRectF'`) won't cause runtime errors, but static type checkers (mypy, pyright) won't resolve them. Consider using a `TYPE_CHECKING` import block:

<details>
<summary>🔧 Proposed fix</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@shared/widgets.py` around lines 1380 - 1393, The function _draw_image_fitted
uses string-based type hints ('QPainter', 'QImage', 'QRectF') which static type
checkers won't resolve; update the module to import actual types only for type
checking by adding "from typing import TYPE_CHECKING" and inside an "if
TYPE_CHECKING:" block import QPainter and QImage from PyQt6.QtGui and QRectF
from PyQt6.QtCore, then change the _draw_image_fitted signature to use the real
types (QPainter, QImage, QRectF) instead of strings so mypy/pyright can resolve
them while avoiding runtime imports.
```

</details>

---

`1464-1471`: **Fallback print silently fails on non-Windows if `lp` is unavailable.**

When `lp` is not found via `shutil.which`, non-renderable files are silently skipped with no user feedback. Consider logging a warning or collecting failed paths to report to the user:

<details>
<summary>🛡️ Proposed improvement</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@shared/widgets.py` around lines 1464 - 1471, The fallback printing loop
silently skips non-Windows paths when 'lp' is absent; update the loop that
iterates over fallback (the branch using platform.system(), os.startfile,
shutil.which('lp') and _sp.Popen) to record any paths that cannot be printed
(e.g., collect into a failed_paths list) and emit a warning after the loop
(using the module logger or logging.warning) that includes those failed paths so
users get feedback when 'lp' is unavailable; ensure the Windows branch
(os.startfile) remains unchanged and only non-Windows missing-'lp' cases are
reported.
```

</details>

---

`1428-1462`: **Consider wrapping QPainter in try/finally to ensure `end()` is called.**

If an unexpected exception occurs during rendering (e.g., QImage creation fails), `painter.end()` won't be called, which can leave the printer in an inconsistent state.

<details>
<summary>🛡️ Proposed fix</summary>

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
</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@shared/widgets.py` around lines 1428 - 1462, The QPainter 'painter' created
for 'printer' must be closed in a finally block so painter.end() always runs;
wrap the main rendering loop (the code iterating over 'renderable' that calls
QPainter(printer), QImage(...), _draw_image_fitted and fitz.open) in try/finally
and call painter.end() from the finally clause, and also ensure any opened
fitz.Document (doc) is closed on error (either by using a with/context manager
or closing doc in a nested finally) so neither the printer nor PDF handles are
left open.
```

</details>

</blockquote></details>
<details>
<summary>core/app_context.py (1)</summary><blockquote>

`87-98`: **Consider adding type hints for the print provider API.**

The provider parameter and return type are untyped. For better IDE support and documentation, consider adding type hints. If you want to keep it flexible for plugins, `Any` or a `Protocol` would work:

```python
from typing import Protocol

class PrintProvider(Protocol):
    def add_files_to_list(self, paths: list) -> None: ...
```

Then: `def register_print_provider(self, provider: PrintProvider | None) -> None`

This is optional but improves discoverability of the expected interface.

<details>
<summary>🤖 Prompt for AI Agents</summary>

```
Verify each finding against the current code and only fix it if needed.

In `@core/app_context.py` around lines 87 - 98, Add explicit typing for the print
provider interface: define a PrintProvider Protocol (or use typing.Any) that
declares add_files_to_list(self, paths: list) -> None, import it from typing,
then update register_print_provider signature to accept provider: PrintProvider
| None -> None and update get_print_provider to return Optional[PrintProvider]
(or PrintProvider | None); update any internal references expecting
_print_provider to reflect the new type.
```

</details>

</blockquote></details>

</blockquote></details>

<details>
<summary>🤖 Prompt for all review comments with AI agents</summary>

```
Verify each finding against the current code and only fix it if needed.

Inline comments:
In `@shared/utils.py`:
- Around line 205-216: Remove the unused print_files function from
shared/utils.py: delete the entire def print_files(paths: List[str]) block and
any related unused imports (os, platform, shutil, subprocess) if they become
unused elsewhere; callers already use print_files_with_dialog in
shared/widgets.py so no call sites need updating. If you prefer to keep it
instead, add explicit error feedback/logging when the OS print handler fails
(e.g., log when shutil.which('lp') returns None or when subprocess fails) so
callers are not silently ignored. Ensure tests/imports still pass after removal.

In `@shared/widgets.py`:
- Around line 1435-1452: The fitz document opened with fitz.open(path) in the
rendering block can leak if an exception happens before doc.close(); modify the
rendering code around fitz.open(path) and doc.close() (the doc variable and the
loop over doc.page_count) to ensure the document is always closed — either use a
context manager (with fitz.open(path) as doc: ...) or wrap the existing logic in
try/finally and call doc.close() in finally; keep the same rendering logic
inside the managed block and preserve the ImportError fallback behavior.

---

Nitpick comments:
In `@core/app_context.py`:
- Around line 87-98: Add explicit typing for the print provider interface:
define a PrintProvider Protocol (or use typing.Any) that declares
add_files_to_list(self, paths: list) -> None, import it from typing, then update
register_print_provider signature to accept provider: PrintProvider | None ->
None and update get_print_provider to return Optional[PrintProvider] (or
PrintProvider | None); update any internal references expecting _print_provider
to reflect the new type.

In `@shared/widgets.py`:
- Around line 1380-1393: The function _draw_image_fitted uses string-based type
hints ('QPainter', 'QImage', 'QRectF') which static type checkers won't resolve;
update the module to import actual types only for type checking by adding "from
typing import TYPE_CHECKING" and inside an "if TYPE_CHECKING:" block import
QPainter and QImage from PyQt6.QtGui and QRectF from PyQt6.QtCore, then change
the _draw_image_fitted signature to use the real types (QPainter, QImage,
QRectF) instead of strings so mypy/pyright can resolve them while avoiding
runtime imports.
- Around line 1464-1471: The fallback printing loop silently skips non-Windows
paths when 'lp' is absent; update the loop that iterates over fallback (the
branch using platform.system(), os.startfile, shutil.which('lp') and _sp.Popen)
to record any paths that cannot be printed (e.g., collect into a failed_paths
list) and emit a warning after the loop (using the module logger or
logging.warning) that includes those failed paths so users get feedback when
'lp' is unavailable; ensure the Windows branch (os.startfile) remains unchanged
and only non-Windows missing-'lp' cases are reported.
- Around line 1428-1462: The QPainter 'painter' created for 'printer' must be
closed in a finally block so painter.end() always runs; wrap the main rendering
loop (the code iterating over 'renderable' that calls QPainter(printer),
QImage(...), _draw_image_fitted and fitz.open) in try/finally and call
painter.end() from the finally clause, and also ensure any opened fitz.Document
(doc) is closed on error (either by using a with/context manager or closing doc
in a nested finally) so neither the printer nor PDF handles are left open.
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

**Configuration used**: Path: .coderabbit.yaml

**Review profile**: CHILL

**Plan**: Pro

**Run ID**: `dde37edf-a7de-446b-a4c2-1a63b4595740`

</details>

<details>
<summary>📥 Commits</summary>

Reviewing files that changed from the base of the PR and between 7221b1e56b43f6e1f7f36c24e12d20cfa31c7d47 and 82176287af7b86b8cbbfc035ddbdb01fea9aefdd.

</details>

<details>
<summary>⛔ Files ignored due to path filters (1)</summary>

* `.claude/S&P.md` is excluded by `!.claude/S&P.md`

</details>

<details>
<summary>📒 Files selected for processing (6)</summary>

* `core/app_context.py`
* `modules/job/module.py`
* `modules/quote/module.py`
* `modules/search/module.py`
* `shared/utils.py`
* `shared/widgets.py`

</details>

<details>
<summary>🚧 Files skipped from review as they are similar to previous changes (3)</summary>

* modules/search/module.py
* modules/quote/module.py
* modules/job/module.py

</details>

</details>

<!-- This is an auto-generated comment by CodeRabbit for review status -->
