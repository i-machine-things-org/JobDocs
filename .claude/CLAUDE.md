# Auto Version Control Rules - Claude AI

You are a senior software developer. These rules override your default behavior. Follow them on every action without being asked.

## Rule 0: Always Read First

Before taking any action on this project — including edits, commits, or file creation:

1. Read `.claude/CLAUDE.md` and `.claude/S&P.md`.
2. Run `gh pr list` — if a PR exists for the current branch, run `gh pr view <number> --comments` and read **all comments** (CodeRabbit and human) before proceeding.
3. Run `gh issue list` — check for open issues relevant to the current work.
4. Do not make any edits until all outstanding findings and review comments are addressed or acknowledged.

No exceptions.

### S&P.md is for programming notes only

`.claude/S&P.md` is a standards and practices log — a reference for coding patterns, past findings, and decisions. It is **not** the source of truth for PR review status.

- To check if a PR review is complete or paused: **always use `gh pr view <number> --comments`**.
- CodeRabbit may auto-pause reviews after rapid commits — check for `review paused` in the summary comment.
- If paused, trigger a new run with: `gh pr comment <number> --body "@coderabbitai review"`

## Trigger Prompt

When the user says **"run auto version control"** (or any close variation like "run avc", "auto version control", "start version control"), immediately run the full assessment:

1. Run `git status`, `git branch`, and `git log --oneline -10`
2. Run `gh issue list` and report any open issues
3. Report the current state: branch, uncommitted changes, recent commits, version tags
4. Flag any issues: working on main, uncommitted changes, missing .gitignore, no tags
5. Recommend next actions

This is how the user explicitly asks you to check in on the project.

## Rule 1: Git Is Mandatory

- If the project is not a git repository, run `git init` and create an initial commit before doing anything else.
- Never work directly on `main`, `master`, or `stable`. Always create a feature branch first then merge into `stable`.
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

## Rule 3: Report Fixer Is a Plugin — Not In This Repo

Report Fixer is a standalone plugin maintained at `H:\Jobdocs\jobdocs-report-fixer`. It is loaded at runtime from the `plugins/` directory alongside the installed executable.

- Do **not** add Report Fixer code to this repo (`modules/`, `psm_modules/`, or anywhere else).
- `PSM-stable` is deprecated and must not be used or merged from.
- `modules/reporting/` in this repo is a lightweight stub for experimental use only — it is not Report Fixer.

---

## Rule 4: Semantic Versioning

Update GitHub releases on minor version changes to the production branch.

Tag releases using `vMAJOR.MINOR.PATCH`:
- **MAJOR** — breaking changes (removed features, changed APIs, incompatible updates)
- **MINOR** — new features that do not break existing functionality
- **PATCH** — bug fixes, typo corrections, minor improvements

### Release Workflow

Pushing a `v*` tag to `stable` automatically triggers `.github/workflows/build-release.yml`, which:
1. **Windows** — downloads the Python embeddable runtime, compiles the C launcher (`launcher/launcher.c`) via MinGW, and packages everything into a Windows installer via Inno Setup (`build_scripts/JobDocs.iss`)
2. **Linux** — builds a PyInstaller binary using `build_scripts/JobDocs.spec` and wraps it in a Flatpak bundle
3. Signs the Windows executable via SignPath (once approved — currently commented out pending application)
4. Creates a GitHub Release and attaches both platform artifacts as release assets

**To cut a release:**
```bash
git tag v1.2.3
git push origin v1.2.3
```

**Note:** Only tag from `stable`.

**SignPath:** Apply at https://signpath.io/product/open-source. Once approved, uncomment the signing step in `build-release.yml` and add `SIGNPATH_API_TOKEN` and `SIGNPATH_ORG_ID` to GitHub Actions secrets.

## Rule 5: Pull Request Reviews

When a pull request is open or being prepared:

- Always open PRs via `gh pr create` — never merge directly to `master` without a PR.
- After any review is submitted (CodeRabbit **or human**), read all comments before making any further changes.
- For each finding, regardless of source:
  1. If it matches an existing `.claude/S&P.md` entry — fix it immediately and reference the S&P entry in the commit message.
  2. If it is a new pattern — fix it, then append it to `.claude/S&P.md` in the standard format before committing.
- Do not dismiss or ignore nitpicks — log them to `.claude/S&P.md` even if not immediately actionable.
- Only merge a PR after all blocking comments are resolved.

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
