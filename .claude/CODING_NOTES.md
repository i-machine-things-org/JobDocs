# Coding Best Practices & Reminders

> **Style rule:** Notes must be clear and concise — 300 characters or less each. Group by topic, not by date. Whenever a PR review (CodeRabbit or human) catches a mistake, add or amend a note here right away so it isn't repeated.

## Python Style & Error Handling

- **Hoist helper functions out of methods.** Defining a helper (e.g. `_is_hidden`) inside a method recreates it on every call — move it to module or class level.
- **Avoid broad `except Exception`.** Catch specific exceptions (`OSError`, `AttributeError`, `shutil.Error`, etc.) so unexpected errors aren't silently masked.
- **Don't leave silent `except Exception: pass`.** Log at debug/warning level so failures stay traceable without breaking the fallback behavior.
- **This repo has no logging config anywhere (no `basicConfig`/handlers).** Default root level is WARNING, so `logger.debug(...)` never fires at runtime. Use `logger.warning` (or higher) for anything that should actually be visible until real logging setup exists.
- **Drop f-string prefixes with no placeholders.** Ruff flags these (F541); use plain string literals instead.
- **Escape backslashes in non-raw docstrings.** A bare backslash (e.g. `runtime\python.exe`) is an invalid escape sequence.
- **Grep-based dead-code checks give false positives on dynamic dispatch and Qt overrides.** `main.py`'s `populate_customer_lists()` calls `populate_*_customer_list` methods via `dir()`/`getattr()` naming convention, not a literal call site; `dragEnterEvent`/`closeEvent`-style Qt overrides are invoked by the framework, not Python source. Verify a method has no *reachable* caller (including reflection/framework dispatch) before removing it as dead code.

## File & Directory Operations

- **`shutil.copy2` overwrites silently — check existence first.** Guard with `if not dest.exists()` before copying; `FileExistsError` handlers around `copy2` are dead code since it never raises that.
- **Sort directories before files in listings.** Use `key=lambda n: (not os.path.isdir(...), n.lower())` so dirs come first, matching OS file-browser conventions.
- **Wrap directory scans in `OSError`/`PermissionError` handlers.** Log per-item/per-dir and continue — never let one bad entry abort discovery (e.g. plugin dir scans).
- **Use atomic swap for install/update operations.** Copy to a temp dir, then backup-then-rename into place, with rollback on failure, so a partial write never corrupts the live install. Same applies to any JSON persistence (settings/history): `open(path, 'w')` truncates before writing, so a crash mid-write leaves an empty/corrupt file. Use `shared.utils.atomic_write_json()` (write to a same-dir temp file, `os.replace()` into place) instead.
- **Gate link creation on copy success.** In "copy then link" flows, track a `*_ready` flag; only create the link if the copy succeeded or the destination already existed.
- **`tempfile.mkstemp()` hardcodes `0o600` on POSIX, ignoring umask.** After `os.replace()` swaps it into place, this silently narrows a shared file's permissions. `os.chmod()` the temp file first — to the original file's mode if it exists, else `0o666 & ~umask` — before replacing. Also `os.fsync(fd)` before `os.replace()`: the rename alone is torn-write-safe but not crash-durable.
- **Probe umask with a throwaway file, not `os.umask()`.** `os.umask()` briefly mutates the process-wide mask to read it, racing any other thread creating a file in that window. Create a uniquely-named file with `O_CREAT|O_EXCL` and inspect its resulting mode instead.
- **Check `create_file_link`'s boolean return at every call site.** It returns `False` on failure instead of raising; ignoring it (or incrementing a success counter unconditionally) reports failed links as successful adds in a windowed GUI app with no visible console.

## ITAR / Filter Consistency (JobDocs)

- **Search must mirror browse/refresh filter logic.** `search_jobs`/`search_quotes` need the same customer + ITAR filtering as `refresh_*_tree`, or search results silently ignore active filters.
- **Detect ITAR prefixes consistently.** Use `startswith(('[ITAR] ', '[ITAR-BP] '))` everywhere a customer label is checked, not a bare `'[ITAR]'` substring.
- **Cancel the active tree worker before a synchronous search.** Otherwise queued `customer_loaded` emissions can repopulate the tree after the search clears it, mixing stale and fresh results.
- **Lazy top-level QTabWidget construction needs a force-build hook for the initially-shown tab.** `setCurrentIndex()` only emits `currentChanged` if the index actually changes — the tab that's already current at startup (or after a CLI-prefill tab switch) never fires it. Call the build handler explicitly for the current index after any programmatic `setCurrentIndex()`.
- **Don't remove a lazy-construction item from its pending/retry tracking dict until the build actually succeeds.** Popping before the `try` around `get_widget()` permanently bricks that tab as a blank placeholder if construction fails once; pop only in the success path so a later click can retry.
- **Track a lazily-built widget's "is it built" state with an explicit flag the caller sets, not by inferring it from the module's own internal caching.** A `get_widget()` contract only promises a returned `QWidget`, not that the implementation caches it to `self._widget` — a plugin that builds fresh each call would always read as "not built" otherwise.
- **Defer a sub-tab's expensive data load until it's actually shown.** `refresh_job_tree`/`refresh_quote_tree` used to walk the whole customer directory tree as soon as the widget was built (via the `populate_*_customer_list` dynamic dispatch). Gate the walk on `<sub_tab_widget>.currentWidget() is <target_tab>`, set a stale flag when skipped, and flush it from `currentChanged` when the tab becomes active.

## Qt / PyQt6 UI Patterns

- **Disable built-in expand-on-double-click before adding a custom handler.** `QTreeWidget` toggles expand state itself; a slot that also calls `setExpanded(not isExpanded())` double-inverts it. Use `setExpandsOnDoubleClick(False)` + `itemFromIndex(index)`.
- **Wrap `QPainter` usage in try/finally.** An exception mid-render skips `painter.end()`, leaving the print backend in an inconsistent state.
- **Cross-thread signals need a real `QObject` receiver.** A plain function connected to a `QThread` signal runs on the worker thread; use a `QObject` with `@pyqtSlot` methods so Qt queues delivery to the main thread.
- **Stream results per-item instead of buffering all in memory.** Emit one `page_ready(QImage)` per page rather than building the full list first, to avoid exhausting memory on large documents.
- **Always emit a "done" signal from try/finally.** If an exception escapes a worker's `run()`, the receiver can wait forever for completion.
- **Block dialog Save/Cancel/close during an in-flight async operation.** Otherwise the user can race a background worker callback against disposed UI state. Applies equally to a manual `QApplication.processEvents()` loop on the GUI thread, not just real `QThread` workers — override `closeEvent`/`reject()` to ignore while a busy flag is set.
- **A close-block needs an escape hatch, or it trades a crash for an unkillable hang.** Blocking `closeEvent`/`reject()` unconditionally with no Cancel control leaves zero way out if the in-flight work stalls (e.g. filesystem I/O against a dead network share) or pops a blocking error dialog per failed item. Add a Cancel button that sets a flag checked between work units, and guard `done()` too (the choke point `accept()`/`reject()` both funnel through) so a future `QDialogButtonBox` can't silently bypass the guard.
- **Persist settings through the real settings store, not a dialog-local copy.** Writing to `self.settings` inside a dialog is lost on Cancel if that object is a local copy rather than the live settings store.
- **Escape untrusted strings before interpolating into RichText labels.** A crafted version string could inject HTML into a `QLabel`; use `html.escape()`.
- **Keep a live reference to non-modal dialogs.** Store on a longer-lived owner (e.g. `window._dialog = dlg`) and clear it on `finished`, or the dialog is garbage-collected and disappears immediately.
- **`QImageReader.setScaledSize()` only bounds decode memory for formats whose Qt plugin supports it — verify with `supportsOption(ScaledSize)`, don't assume.** True for JPEG on this Qt build; False for PNG/BMP/WEBP/ICO/GIF, where Qt still decodes full-res internally then scales down in software (same peak memory as `QPixmap(path)`). Still worth using: it bounds *steady-state* memory for every format (no full-res `QPixmap`/`QImage` held resident afterward), just not decode-time memory for non-native formats. A real decode-time fix for those would need a different library (e.g. Pillow, not currently a dependency) — don't claim "bounded decode" without checking `supportsOption()` for the specific format first.
- **A mode flag (e.g. `readonly_mode`) only enforces anything once it's on `AppContext`, not just `main.py`.** Skipping module *loading* isn't a write guarantee — audit every still-loaded module's write paths and gate each on `app_context.readonly_mode`.

## Print & Rendering

- **Verify `lp` exists before calling it.** Use `shutil.which('lp')` rather than assuming the binary is on PATH.
- **Guard `QPrinterInfo.availablePrinters()` being empty.** Showing a print dialog with an empty printer list and OK enabled risks a crash or nonsensical job.
- **Prune failed pre-render items before the print pass.** If pre-rendering a page fails, remove it from the "to print" list too, or the same bad file is retried (and re-fails) during actual printing.
- **On toolbar-hook failure, still fall back — don't drop the files.** If an action can't be hooked, extend the OS-fallback list with the pending files instead of cancelling silently.

## Search / SQLite Index (JobDocs)

- **Escape LIKE wildcards in path-based queries.** Raw paths in a `LIKE` clause need an explicit `ESCAPE` char (e.g. `'!'`) to avoid matching unintended rows, especially with Windows `\` separators.
- **`os.walk` needs an `onerror` callback.** Without one, subdirectory read errors are silently swallowed and `completed` can end up `True` on partial results.
- **Track staleness recursively, not just on the top directory.** A single `getmtime` on a customer dir misses nested subdirectory changes; walk dirs (not files) for a lightweight recursive mtime check.
- **Don't commit partial index data from a cancelled walk.** Collect rows into a local list first; only delete + insert + mark-indexed after the walk actually completes.
- **Let index-query failures propagate, don't collapse them into "no match."** A caught `sqlite3.Error` returned as `None` is indistinguishable from a confirmed no-match; callers need to fall back to a filesystem scan on failure but trust `None` otherwise.
- **Don't treat a zero-result index query as automatic grounds for a filesystem fallback.** Check `indexed_dirs` coverage (shallow `os.listdir()`) to tell "confirmed zero matches" from "not caught up yet." Caveat: proves indexed *once*, not fresh — pair with the incremental-update note below.
- **Update the index incrementally on job/quote creation, don't rely on the background indexer alone.** It runs once per launch only. `SearchIndex.add_job()`/`add_quote()` insert one row right after a successful create so it's searchable immediately.
- **Every branch of a schema migration must force the same re-index, not just the "normal" path.** (CodeRabbit, PR #297) A v4 migration's "column already exists" fallback bumped `user_version` without clearing `indexed_dirs`, so already-indexed customers would never get the new column backfilled. Both branches of a conditional migration need the same side effects unless there's a real reason they shouldn't.

## Performance / Redundant Work (JobDocs)

- **Memoize a filesystem scan's result instead of re-running it with identical args later in the same operation.** E.g. bulk create's duplicate-check pass and creation pass both queried the same (customer, job_number) — cache the first pass's result set and reuse it, tracking newly-created keys locally for intra-batch duplicates.
- **Re-verify after a blocking, timeout-less confirmation dialog — don't trust a pre-dialog scan.** `QMessageBox.question()` waits indefinitely; on a shared network path, data can change during that wait. Bulk create re-checks non-flagged jobs right after the dialog returns Yes.

## Build & Packaging

- **Quote shell paths containing special characters.** An unquoted `&` in a path acts as the shell background operator and breaks the command.
- **Guard destructive `rm -rf` on possibly-empty variables.** Use `${VAR:?message}` so an empty `BUILD_PATH`/`DIST_PATH` fails loudly instead of expanding to `rm -rf /`.
- **Check external tool availability before invoking it (e.g. `iscc`).** Don't depend implicitly on the hosted runner's preinstalled toolset; assert or install it explicitly.
- **Verify integrity of downloaded build dependencies.** Hash-check embeddable runtimes before use; prefer the already-installed system tool over an unverified network installer script (e.g. `get-pip.py`).
- **Derive version metadata from build variables, not hardcoded literals.** A hardcoded `FILEVERSION` in a `.rc` file drifts from the actual release tag over time.
- **Flatpak's `/app` is read-only at runtime.** Per-user writable state (installed plugins, deps) must go under `$XDG_DATA_HOME` / `~/.var/app/<id>/data`, gated on `FLATPAK_ID`.
- **When switching PyInstaller onefile to onedir, update every downstream consumer.** Flatpak staging, manifests, and verify steps all reference the old single-binary path and need updating together.
- **Manual recovery commands must use `sys.executable`, quoted.** Bare `pip` may resolve to the wrong interpreter; unquoted paths with spaces break copy-pasted commands.
- **Never run a built Inno Setup installer against a real machine's default paths to test it.** `[Setup] AppId` keys the Uninstall/Previous-Data registry entries regardless of `/DIR=`; a throwaway test install can still clobber a real install's registry data or PATH. Test with `iscc` syntax-compile only, or in an isolated VM/container.
- **Inno Setup: use `WizardIsTaskSelected`/task checkboxes, not `[Types]`+`TypesCombo`, for a simple binary install-variant choice.** `WizardForm.TypesComboChange` isn't a scriptable identifier in current Inno Setup; a Tasks-section checkbox plus `GetPreviousData`/`RegisterPreviousData` (not a global `PreviousDataKey`) is simpler and remembers the choice across updates.
- **Pre-select a `[Tasks]` entry via `WizardSelectTasks('name')`, never by matching its Description text.** Description strings get duplicated across `[Tasks]` and `[Code]`; if they drift, the match silently fails. `WizardSelectTasks`/`WizardIsTaskSelected` key off the stable `Name`.

## CI / GitHub Actions

- **Only grant `contents: write` to the job that actually publishes a release.** Build/upload-only jobs need `contents: read`.
- **Pin CI dependency versions to match `requirements.txt`.** Don't duplicate a looser version constraint directly in workflow YAML.
- **Add a stable-ancestry guard on tag-triggered release workflows.** Verify the tag's commit is an ancestor of the correct branch before building/releasing.
- **Order artifact upload before any signing step.** The signing action reads from an already-uploaded artifact.
- **Pin the pip bootstrap; don't rely on `-latest` runner images.** Use `actions/setup-python` with a pinned version and a pinned `pip==` release for reproducible builds.

## Plugins & Dynamic Loading

- **Register a plugin's parent package in `sys.modules` before `exec_module`.** External plugins using relative imports (`from .helpers import ...`) fail without a registered parent package with `__path__` set.
- **Move blocking I/O off the GUI thread.** Network downloads and zip extraction during plugin install must run in a `QThread` worker, not the main thread.
- **In frozen apps, try the bundled interpreter before falling back to system Python.** ABI mismatches between bundled and system Python can break binary wheels.
- **Invalidate any startup-computed module cache on install/uninstall.** A `discover_modules()` result cached once at startup (e.g. for a Settings dialog list) goes stale the moment a plugin is installed/uninstalled mid-session; recompute it in both success handlers, not just at launch.

## Update Checker

- **Strip pre-release suffixes before parsing a version tuple.** `"v0.9.9-test".split('.')` throws; split on `-` first.
- **Only emit a positive result on confirmed success.** Catch specific exceptions (`URLError`, `JSONDecodeError`, etc.) — a bare `except: pass` around a version check can report "up to date" on a network failure.
- **Join/interrupt background threads before the app exits.** Otherwise Qt logs "QThread: Destroyed while thread is still running."
- **Guard against launching duplicate background checkers.** Check `existing.isRunning()` before starting a new one from a menu action.
- **Gate Flatpak-only code paths on `FLATPAK_ID`.** Don't attempt `flatpak-spawn` (or similar) unconditionally on all Linux — it fails silently outside the sandbox.
