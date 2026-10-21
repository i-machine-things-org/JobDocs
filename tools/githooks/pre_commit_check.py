#!/usr/bin/env python3
"""
Pre-commit check: block a commit that contains real JobBOSS employee
identifiers (name/code) anywhere in its staged diff.

Why this exists: an earlier session used real employee names, codes, and
hours as illustrative examples while reverse-engineering a report formula
(modules/reporting/reports/employee_efficiency.py), and that data landed
in ~20 pushed commits on this public repo before anyone caught it. This
check is the mechanical backstop so the same mistake can't recur silently
-- see .claude/CODING_NOTES.md's "Reporting Module" section. Invoked by
the tools/githooks/pre-commit shell dispatcher, not run directly as a git
hook itself (see that file for why: shebang-based interpreter resolution
isn't reliable across machines/shells).

Checks staged content (`git diff --cached`) against the local identifier
cache at .claude/sensitive_identifiers.txt (gitignored -- it's real HR
data itself, built by tools/generate_sensitive_identifiers.py from the
live DB). Only checks ADDED lines, not removed ones, so scrubbing a past
mention doesn't itself get blocked.

If the cache doesn't exist (no DB access configured on this machine, or
never generated), this WARNS and allows the commit rather than blocking
all commits unconditionally -- it's a safety net on machines that can
build the list, not a universal guarantee. Run
`python tools/generate_sensitive_identifiers.py` once (and again whenever
the employee roster changes) to enable the actual check.

A genuine false positive (a real identifier that's also an ordinary
word/variable name) can be bypassed with `git commit --no-verify` --
use deliberately, not reflexively, and double-check the diff first.
"""
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_IDENTIFIERS_PATH = _REPO_ROOT / '.claude' / 'sensitive_identifiers.txt'


def _load_identifiers() -> set:
    if not _IDENTIFIERS_PATH.exists():
        return set()
    return {
        line.strip() for line in _IDENTIFIERS_PATH.read_text(encoding='utf-8').splitlines()
        if line.strip()
    }


def _added_lines_from_diff(diff_text: str):
    """Yield (file_path, line_text) for every '+' line in a unified diff,
    skipping the '+++' file-header lines themselves.
    """
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith('+++ '):
            # '+++ b/path/to/file' (or '+++ /dev/null' for a deleted file)
            current_file = line[4:]
            if current_file.startswith('b/'):
                current_file = current_file[2:]
            continue
        if line.startswith('+') and not line.startswith('+++'):
            yield current_file, line[1:]


def main() -> int:
    identifiers = _load_identifiers()
    if not identifiers:
        print(
            "pre-commit: sensitive-identifier cache not found "
            f"({_IDENTIFIERS_PATH}) -- skipping the real-employee-data check. "
            "Run `python tools/generate_sensitive_identifiers.py` to enable it.",
            file=sys.stderr,
        )
        return 0

    try:
        diff = subprocess.run(
            ['git', 'diff', '--cached', '--unified=0'],
            cwd=_REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        print(f"pre-commit: couldn't read staged diff ({exc}) -- allowing commit.", file=sys.stderr)
        return 0

    patterns = {ident: re.compile(r'\b' + re.escape(ident) + r'\b', re.IGNORECASE) for ident in identifiers}

    findings = []
    for file_path, line_text in _added_lines_from_diff(diff):
        for ident, pattern in patterns.items():
            if pattern.search(line_text):
                findings.append((file_path, ident, line_text.strip()[:100]))

    if not findings:
        return 0

    print("pre-commit: BLOCKED -- staged changes contain real JobBOSS employee data:\n", file=sys.stderr)
    for file_path, ident, snippet in findings[:20]:
        print(f"  {file_path}: matched '{ident}' in: {snippet}", file=sys.stderr)
    if len(findings) > 20:
        print(f"  ... and {len(findings) - 20} more", file=sys.stderr)
    print(
        "\nUse an anonymized placeholder (e.g. EMP-A/EMP-B) instead of a real name/code "
        "in any committed file. If this is a genuine false positive, `git commit --no-verify`.",
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    sys.exit(main())
