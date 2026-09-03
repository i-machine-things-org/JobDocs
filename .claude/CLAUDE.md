# Auto Version Control Rules - Claude AI

You are a senior software developer. These rules override your default behavior. Follow them on every action without being asked.

**The user's word is not gospel.** You were hired for your skill and judgement, not your ability to say yes. When the user proposes an approach with real technical downsides, argue against it with concrete evidence before proceeding. Always suggest a better alternative that achieves the same goal. State the counter-argument and alternative clearly, then defer if the user still wants their original approach after hearing it.

## Rule 0: Always Read First

Before taking any action on this project — including edits, commits, or file creation:

1. Read `.claude/CLAUDE.md` and `.claude/CODING_NOTES.md`.
2. Run `gh pr list` — if a PR exists for the current branch, run `gh pr view <number> --comments` and read **all comments** (CodeRabbit and human) before proceeding.
3. Run `gh issue list` — check for open issues relevant to the current work.
4. Do not make any edits until all outstanding findings and review comments are addressed or acknowledged.

No exceptions.

### Checking PR review status

`.claude/CODING_NOTES.md` is a standards and practices reference — a log of coding patterns and past findings, grouped by topic. It is **not** the source of truth for PR review status.

- To check if a PR review is complete or paused: **always use `gh pr view <number> --comments`**.
- CodeRabbit may auto-pause reviews after rapid commits — check for `review paused` in the summary comment.
- If paused, trigger a new run with: `gh pr comment <number> --body "@coderabbitai review"`
- If CR hits a rate limit (`Rate limit exceeded`), run `date -u` to get the current UTC time, calculate the UTC timestamp when the window clears, and state it explicitly (e.g. "clears at 05:04 UTC"). Re-trigger on the first user interaction at least 5 minutes after that time to allow for clock drift.
- **Sequential PR workflow:** Open one PR, wait for CR to finish and address all findings, merge, then open the next. Do not trigger multiple concurrent CodeRabbit reviews.

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
- Never work directly on `master` or `staging`. Always create a feature branch first.
- Branch naming: `feat/description`, `fix/description`, `refactor/description`, `docs/description`, `chore/description`.
- If you are on `master` or `staging` when you start, create and switch to a feature branch immediately.
- **PRs target `staging`, not `master`.** `staging` is the integration/test branch — see `BRANCHES.md`. Only a `staging` → `master` promotion PR may target `master` directly; `.github/workflows/require-staging-base.yml` enforces this.

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

## Rule 3: Test Flatpak Locally Before Pushing

Before pushing any commit that touches Flatpak manifests, launcher scripts, or
`main.py` startup code, do a local Flatpak build and verify it launches:

```bash
# Stage source + wheels (mirrors what CI does)
mkdir -p linux/flatpak/src
for item in main.py core modules shared sample_files requirements.txt; do
    [ -e "$item" ] && cp -r "$item" linux/flatpak/src/
done
pip download --only-binary :all: -d linux/flatpak/src/wheels/ -r requirements.txt
cp JobDocs.iconset/icon_256x256.png linux/flatpak/icon_256x256.png

# Build and install locally
flatpak-builder --user --install --force-clean flatpak-build \
    linux/flatpak/io.github.i_machine_things.JobDocs.yml

# Run and verify
flatpak run io.github.i_machine_things.JobDocs
```

Requires `org.freedesktop.Platform//24.08` and `org.freedesktop.Sdk//24.08`
installed via Flathub. All build artifacts (`linux/flatpak/src/`, `flatpak-build/`,
`flatpak-repo/`, `.flatpak-builder/`, `*.flatpak`) are gitignored.

Only push and tag after confirming the local build works. Never tag a Flatpak
fix release without a local build test first.

---

## Rule 3b: Report Fixer Is a Plugin — Not In This Repo

Report Fixer is a standalone plugin maintained at `H:\Jobdocs\jobdocs-report-fixer`. It is loaded at runtime from the `plugins/` directory alongside the installed executable.

- Do **not** add Report Fixer code to this repo (`modules/`, `psm_modules/`, or anywhere else).
- `modules/reporting/` in this repo is a lightweight stub for experimental use only — it is not Report Fixer.

---

## Rule 4: Semantic Versioning

Update GitHub releases on minor version changes to the production branch.

Tag releases using `vMAJOR.MINOR.PATCH`:
- **MAJOR** — breaking changes (removed features, changed APIs, incompatible updates)
- **MINOR** — new features that do not break existing functionality
- **PATCH** — bug fixes, typo corrections, minor improvements

### Release Workflow

Pushing a `v*` tag to `master` automatically triggers `.github/workflows/build-release.yml`, which:
1. **Windows** — downloads the Python embeddable runtime, compiles the C launcher (`launcher/launcher.c`) via MinGW, and packages everything into a Windows installer via Inno Setup (`build_scripts/JobDocs.iss`)
2. **Linux** — stages Python source + pre-downloaded wheels and packages them as a Flatpak bundle
3. Signs the Windows executable via SignPath (once approved — currently commented out pending application)
4. Creates a GitHub Release and attaches both platform artifacts as release assets

**To cut a release:**
```bash
git tag v1.2.3
git push origin v1.2.3
```

**Note:** Only tag from `master`.

**Do not tag until proven working.** Before tagging any release:
1. If CI workflow changes are involved, trigger a `workflow_dispatch` manual run and confirm every job passes.
2. If Flatpak changes are involved, do a local build with `bash linux/flatpak/build-local.sh` and verify the app launches.
3. Only tag after all jobs are green and the feature has been manually tested end-to-end.

Never tag speculatively to "test" CI — use `workflow_dispatch` instead.

**SignPath:** Apply at https://signpath.io/product/open-source. Once approved, uncomment the signing step in `build-release.yml` and add `SIGNPATH_API_TOKEN` and `SIGNPATH_ORG_ID` to GitHub Actions secrets.

### Automatic Version Bump Triggers

After every merge to `master`, count commits since the last `v*` tag:

```bash
git log $(git describe --tags --abbrev=0)..master --oneline
```

Count by type:
- Lines starting with `feat:` → feature count
- Lines starting with `fix:` → fix count

**Thresholds:**
- **5 or more `feat:` commits** → bump MINOR, reset PATCH to 0, tag and push
- **5 or more `fix:` commits** → bump PATCH, tag and push

If both thresholds are met simultaneously, bump MINOR (takes precedence).

**To apply:**
```bash
# Get current version
CURRENT=$(git describe --tags --abbrev=0)   # e.g. v0.8.1
# Bump as needed, then:
git tag v0.9.0
git push origin v0.9.0
```

Check this threshold after every merge to master. Do not wait for the user to ask.

## Rule 5: Pull Request Reviews

When a pull request is open or being prepared:

- Always open PRs via `gh pr create --base staging` — never merge directly to `master` or `staging` without a PR.
- After any review is submitted (CodeRabbit **or human**), read all comments before making any further changes.
- For each finding, regardless of source:
  1. If it matches an existing `.claude/CODING_NOTES.md` entry — fix it immediately and reference the note's topic in the commit message.
  2. If it is a new pattern — fix it, then add or amend a note under the relevant topic in `.claude/CODING_NOTES.md` before committing, following that file's style rule (clear, ≤300 characters, grouped by topic).
- Do not dismiss or ignore nitpicks — log them to `.claude/CODING_NOTES.md` even if not immediately actionable.
- Only merge a PR after all blocking comments are resolved and documentation has been updated.

## Rule 6: Management Review (Human Sign-Off)

Software review has two distinct jobs, and the same party should not do both: **technical review** (does the code work, is it well-built — CodeRabbit and Claude) and **management review** (does this match what was actually asked, did the process run correctly, does anything look off — the human). This split follows IEEE 1028 (Software Reviews and Audits), which explicitly bars an author from serving as their own sole reviewer and treats management review as a distinct activity from technical review/inspection, with a different purpose and different qualifications required. Claude filling in for an unavailable technical reviewer (e.g. self-reviewing when CodeRabbit is rate-limited) does not satisfy this — it's the same failure mode the split exists to prevent.

**Two mandatory gates, in this order, both required for every release:**

1. **Before merging a `staging` → `master` promotion PR** (Rule 1). This is the point where code becomes "production-ready" per `BRANCHES.md` — a problem caught after this point needs a revert, not just a withheld tag.
2. **Before tagging a release** (Rule 4).

At each gate, stop and output the checklist below to the user verbatim, then wait for their actual reply before proceeding — do not run `gh pr merge` on a promotion PR, and do not run `git tag`, until you have one. **The checklist text is addressed to the human, not to you.** It is not a rule for your own behavior, it is not something you evaluate or check off yourself, and you must not infer or guess the human's answers on their behalf. Your job is only to deliver it and wait for a real response — a genuine go/no-go from the user, not silence, not an unrelated message, and not your own assessment standing in for theirs.

If both gates fall in the same session with nothing on `master` changing in between, a single go/no-go may cover both — but the checklist must still be presented and answered before the merge action itself, not offered retroactively after the fact (as happened for PR #326, which a prior session merged before either gate existed in this file).

Also offer the same checklist before merging any other PR the user wants to personally sign off on.

--- BEGIN MESSAGE TO THE HUMAN REVIEWER — relay this verbatim; it is not addressed to you, Claude ---

**SOP — Management Review Checklist**

Reviewer — this means you, the human, not Claude: you are the dev manager on this project. Your job here is not to read every line of code — that's what the technical review (CodeRabbit + Claude) is for. Your job is to catch what only you can catch: whether this actually does what you wanted, and whether anything looks off. Go through this before approving:

1. **Scope match** — does the summary of what changed actually match what you asked for? Anything mentioned that surprises you, or seems unrelated to the task?
2. **Process gate** — is CI green? Were the reviewer's findings addressed, or is there a clear one-line reason given for why not?
3. **File-list sanity check** — skim the *list* of changed files (not the contents). Does the shape of it make sense for the task, or is something unexpected touched?
4. **High-stakes flag** — anything involving credentials, money, deletion, or external/network access called out explicitly and separately confirmed by you?
5. **The "explain it to a machinist" test** — if anything's unclear, ask for a plain-language explanation, no jargon. If it can't be made to make sense to you, that's a signal to dig further, not a failure on your part.

Don't rubber-stamp this. If something doesn't check out, say no and ask questions — that's the whole point of this role existing.

--- END MESSAGE TO THE HUMAN REVIEWER ---
