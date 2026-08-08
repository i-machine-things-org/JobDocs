# JobDocs Branch Structure

This document explains the purpose and usage of each branch in the JobDocs repository.

## Branch Overview

```
master       - Production-ready releases (default branch)
staging      - Integration/test branch; all feature PRs land here first
```

## Branch Descriptions

### `master` (default)
**Purpose**: Production-ready code for general use

**Characteristics**:
- Main branch for releases
- Only ever updated by merging `staging` in (see Branch Workflow below)
- Tagged with version numbers for releases (`vMAJOR.MINOR.PATCH`)
- `.github/workflows/require-staging-base.yml` fails any PR into `master`
  whose head isn't `staging`; branch protection on `master` marks this
  check required so a failing check blocks the merge button

---

### `staging`
**Purpose**: Integration and test branch for everything in flight

**Characteristics**:
- Every feature/fix/chore PR targets this branch, not `master`
- Where CodeRabbit/CI review and manual testing happen before promotion
- Periodically merged into `master` via a `staging` → `master` PR once its
  contents are verified

**Use When**:
- Opening any new PR with `gh pr create --base staging`.

---

## Branch Workflow

### Development Flow
```text
feature/fix/chore branch → PR into staging → (review + testing) → staging → master PR → master
```

### For Contributors

1. Branch off `staging` (not `master`) for new work:
   ```bash
   git checkout staging
   git pull origin staging
   git checkout -b feat/my-thing
   ```
2. Open the PR against `staging`.
3. Once a batch of merged work in `staging` has been verified, someone opens
   a `staging` → `master` PR to promote it. This is the only PR type allowed
   to target `master` directly.

---

## Questions?

For more information:
- See [README.md](README.md) for general documentation
- Check commit history: `git log --oneline --graph --all`
