# JobDocs Branch Structure

This document explains the purpose and usage of each branch in the JobDocs repository.

## Branch Overview

```
stable       - Production-ready releases
PSM-stable   - PSM-specific customizations (stable)
testing      - Active development and testing
```

## Branch Descriptions

### `stable` (default)
**Purpose**: Production-ready code for general use

**Characteristics**:
- Main branch for releases
- Thoroughly tested features
- Suitable for end users
- Receives merges from `testing` after feature stabilization
- Tagged with version numbers for releases

**Use When**:
- You want the most stable, production-ready version
- Deploying to end users
- Creating official releases

**Latest Features** (as of last merge):
- PO number support for job creation
- Network shared settings
- User authentication
- OOBE wizard
- Full modular architecture

---

### `PSM-stable`
**Purpose**: PSM (Precision Sheet Metal) specific customizations

**Characteristics**:
- Branch for PSM-specific requirements
- May have customized folder structures
- May have different default settings
- Maintained separately from main stable branch
- Based on stable branch with PSM modifications

**Use When**:
- Working specifically for PSM environment
- Need PSM-specific folder structures or workflows
- Deploying to PSM production

**Key Differences from `stable`**:
- Custom job folder structure for PSM workflow
- Remote settings synchronization features
- PSM-specific UI configurations

---

### `testing` (current development)
**Purpose**: Active development and feature testing

**Characteristics**:
- Latest features and improvements
- May contain experimental code
- Actively receives commits
- Features are tested here before merging to stable
- May have breaking changes

**Use When**:
- Developing new features
- Testing improvements
- Contributing to the project
- Want access to cutting-edge features (accept some instability)

**Recent Features** (not yet in stable):
- Auto-generate job/quote numbers (starting at 10000)
- User session tracking and monitoring
- Active session display in login dialog (Users tab)
- Improved admin settings dialog for team settings
- Logout returns to login screen
- Directory cleanup and improved documentation

**Important**: This branch may have bugs or incomplete features. Always test thoroughly before using in production.

---

## Branch Workflow

### Development Flow
```
testing → (stabilization & testing) → stable
                                   ↓
                              PSM-stable (with PSM customizations)
```

### How to Switch Branches

**Switch to stable**:
```bash
git checkout stable
git pull origin stable
```

**Switch to PSM-stable**:
```bash
git checkout PSM-stable
git pull origin PSM-stable
```

**Switch to testing**:
```bash
git checkout testing
git pull origin testing
```

### For Contributors

1. **New Features**: Develop in `testing` branch
2. **Bug Fixes**:
   - Critical fixes: Fix in `stable`, then merge to `testing` and `PSM-stable`
   - Non-critical: Fix in `testing`, merge to `stable` when ready
3. **PSM-Specific Changes**: Work in `PSM-stable` branch

### Merging Strategy

**From testing to stable**:
```bash
git checkout stable
git merge testing
git push origin stable
```

**From stable to PSM-stable**:
```bash
git checkout PSM-stable
git merge stable
# Resolve any conflicts with PSM customizations
git push origin PSM-stable
```

---

## Version Compatibility

All branches share the same core architecture and data formats:
- Settings files (`settings.json`) are compatible across branches
- History files (`history.json`) are compatible across branches
- User data (`users.json`, `sessions.json`) are compatible across branches
- Network shared configurations work across all branches

This means you can switch between branches without losing data, though some features may only be available in specific branches.

---

## Current Status (2026-01-02)

- **stable**: Stable with PO number support, ready for production
- **PSM-stable**: PSM-specific customizations, production-ready for PSM
- **testing**: Latest features including auto-generate, session tracking, improved docs
  - Ready for testing and validation
  - Pending merge to stable after thorough testing

---

## Choosing the Right Branch

| Scenario | Recommended Branch |
|----------|-------------------|
| Production deployment (general) | `stable` |
| PSM production deployment | `PSM-stable` |
| Development/testing | `testing` |
| Want latest features (accept some risk) | `testing` |
| Need maximum stability | `stable` |
| PSM-specific requirements | `PSM-stable` |

---

## Questions?

For more information:
- See [README.md](README.md) for general documentation
- See [RELEASE_NOTES.md](RELEASE_NOTES.md) for version history
- Check commit history: `git log --oneline --graph --all`
