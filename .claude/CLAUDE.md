# Auto Version Control Rules - Claude AI

You are a senior software developer. These rules override your default behavior. Follow them on every action without being asked.

## Rule 0: Always Read First

Before taking any action on this project — including edits, commits, or file creation:

1. Read `.claude/CLAUDE.md` and `.claude/S&P.md`.
2. Run `gh pr list` — if a PR exists for the current branch, run `gh pr view <number> --comments` and read all CodeRabbit comments before proceeding.
3. Do not make any edits until outstanding CR findings are addressed or acknowledged.

No exceptions.

## Trigger Prompt

When the user says **"run auto version control"** (or any close variation like "run avc", "auto version control", "start version control"), immediately run the full assessment:

1. Run `git status`, `git branch`, and `git log --oneline -10`
2. Report the current state: branch, uncommitted changes, recent commits, version tags
3. Flag any issues: working on main, uncommitted changes, missing .gitignore, no tags
4. Recommend next actions

This is how the user explicitly asks you to check in on the project.

## Rule 1: Git Is Mandatory

- If the project is not a git repository, run `git init` and create an initial commit before doing anything else.
- Never work directly on `main`, `master`,`stable` . Always create a feature branch first then merge into `stable` and `PSM stable`.
- Branch naming: `feat/description`, `fix/description`, `refactor/description`, `docs/description`, `chore/description`.
- If you are on `main` when you start, create and switch to a feature branch immediately.

## Rule 2: Conventional Commits

Every commit message must follow this format:

```
type: short description (imperative, lowercase, no period)
```

Valid types: `feat`, `fix`, `refactor`, `docs`, `test`, `style`, `perf`, `chore`, `ci`, `build`.

Examples:
- `feat: add user authentication endpoint`
- `fix: prevent null pointer in payment handler`
- `refactor: extract validation logic into shared module`
- `docs: add API usage examples to README`

Rules:
- One logical change per commit. Do not bundle unrelated changes.
- Commit after every meaningful change, not at the end of a long session.
- If a commit touches more than 3 unrelated things, you are bundling too much. Split it.
- If a new feature is added or changed, update the top-level README.md before committing.
- After every commit, check if a PR exists for the current branch (`gh pr list --head <branch>`). If none exists, open one immediately via `gh pr create`. Never leave a commit on a feature branch without an open PR.

## Rule 3: Report Fixer Must Never Merge to `stable`

**`modules/reporting/` (Report Fixer) is a PSM-only feature. It must never be merged into `stable`.**

- `stable` is the primary production branch for general use. Report Fixer does not belong there.
- Development happens on `PSM-stable`. When changes from `PSM-stable` are candidates for `stable`, always exclude `modules/reporting/` and its PSM-only dependencies (`pandas`, `openpyxl`) from the merge.
- If Report Fixer files are detected in a diff or staged commit targeting `stable`, **stop immediately and warn the user** before taking any action.
- This rule applies regardless of how the merge is initiated (manual, cherry-pick, or automated).

---

## Rule 4: Semantic Versioning

Update GitHub releases on minor version changes to the production branch.

Tag releases using `vMAJOR.MINOR.PATCH`:
- **MAJOR** — breaking changes (removed features, changed APIs, incompatible updates)
- **MINOR** — new features that do not break existing functionality
- **PATCH** — bug fixes, typo corrections, minor improvements

### Release Workflow

Pushing a `v*` tag to `stable` automatically triggers `.github/workflows/build-release.yml`, which:
1. Builds `JobDocs.exe` via PyInstaller on a Windows runner using `build_scripts/JobDocs.spec`
2. Signs the executable via SignPath (once approved — currently commented out pending application)
3. Creates a GitHub Release and attaches `JobDocs.exe` as a release asset

**To cut a release:**
```
git tag v1.2.3
git push origin v1.2.3
```

**Note:** Only tag from `stable`. Do not push `v*` tags from `PSM-stable` — that branch carries Report Fixer (Rule 3) and must not produce a general release build.

**SignPath:** Apply at https://signpath.io/product/open-source. Once approved, uncomment the signing step in `build-release.yml` and add `SIGNPATH_API_TOKEN` and `SIGNPATH_ORG_ID` to GitHub Actions secrets.

## Rule 5: CodeRabbit Pull Request Reviews

When a pull request is open or being prepared:

- Always open PRs via `gh pr create` — never merge directly to `master` without a PR.
- After CodeRabbit submits its review, read the review comments before making any further changes.
- For each CodeRabbit finding:
  1. If it matches an existing `.claude/S&P.md` entry — fix it immediately and reference the S&P entry in the commit message.
  2. If it is a new pattern — fix it, then append it to `.claude/S&P.md` in the standard format before committing.
- Do not dismiss or ignore CodeRabbit nitpicks — log them to `.claude/S&P.md` even if not immediately actionable.
- Only merge a PR after all blocking CodeRabbit comments are resolved.

### S&P.md Entry Format

```markdown
## YYYY-MM-DD — `path/to/file.py` (short description)

**Review:** WHAT CODERABBIT FLAGGED
**Result:** outcome / resolution

### Findings

1. **Title**
   - Detail
   - Fix applied
```
