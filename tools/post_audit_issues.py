#!/usr/bin/env python3
"""
Parse flake8 and bandit output and create GitHub issues for new findings.

Deduplicates against existing open issues tagged 'automated-audit' so
re-running the workflow never creates duplicate issues.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

LABEL = 'automated-audit'
_existing_titles: set | None = None


def _fetch_existing_titles() -> set:
    """Fetch titles of all open automated-audit issues. Aborts on failure."""
    global _existing_titles
    if _existing_titles is not None:
        return _existing_titles

    result = subprocess.run(
        ['gh', 'issue', 'list',
         '--label', LABEL,
         '--state', 'open',
         '--json', 'title',
         '--limit', '1000'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f'ERROR: could not fetch existing issues: {result.stderr}', file=sys.stderr)
        sys.exit(1)

    _existing_titles = {i['title'] for i in json.loads(result.stdout or '[]')}
    return _existing_titles


def _ensure_label() -> None:
    """Create all labels used by this script idempotently."""
    labels = [
        (LABEL, 'e4e669', 'Opened automatically by the weekly code audit'),
        ('bug', 'd73a4a', 'Something is not working'),
        ('security', 'e11d48', 'Security vulnerability or concern'),
    ]
    for name, color, desc in labels:
        subprocess.run(
            ['gh', 'label', 'create', name,
             '--color', color,
             '--description', desc,
             '--force'],
            capture_output=True,
        )


def _fingerprint(tool: str, code: str, filepath: str, lineno: str | int, msg: str) -> str:
    """Short deterministic hash that survives message truncation."""
    key = f'{tool}:{code}:{filepath}:{lineno}:{msg}'
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:8]  # nosec B324


def _make_title(tool: str, code: str, msg: str, fname: str, lineno: str | int,
                fp: str) -> str:
    snippet = msg[:72]
    return f'[Audit] {tool} {code}: {snippet} in {fname}:{lineno} [{fp}]'


def _create_issue(title: str, body: str, extra_label: str) -> None:
    existing = _fetch_existing_titles()
    if title in existing:
        print(f'  skip (exists): {title[:100]}')
        return
    result = subprocess.run(
        ['gh', 'issue', 'create',
         '--title', title,
         '--body', body,
         '--label', LABEL,
         '--label', extra_label],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        existing.add(title)
        print(f'  created: {title[:100]}')
    else:
        print(f'  error: {result.stderr[:200]}', file=sys.stderr)


# ---------------------------------------------------------------------------
# flake8
# ---------------------------------------------------------------------------
def _parse_flake8(path: str) -> list:
    findings = []
    if not os.path.exists(path):
        return findings
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            m = re.match(r'^(.+?):(\d+):(\d+): ([EF]\d+) (.+)$', line)
            if not m:
                continue
            filepath, lineno, col, code, msg = m.groups()
            fname = os.path.basename(filepath)
            fp = _fingerprint('flake8', code, filepath, lineno, msg)
            title = _make_title('flake8', code, msg, fname, lineno, fp)
            body = (
                f'**Tool:** flake8  \n'
                f'**File:** `{filepath}:{lineno}:{col}`  \n'
                f'**Code:** `{code}`  \n'
                f'**Message:** {msg}\n\n'
                f'---\n'
                f'*Opened automatically by the weekly code audit. '
                f'Close this issue once the finding is resolved or accepted.*'
            )
            findings.append((title, body, 'bug'))
    return findings


# ---------------------------------------------------------------------------
# bandit
# ---------------------------------------------------------------------------
def _parse_bandit(path: str) -> list:
    findings = []
    if not os.path.exists(path):
        return findings
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return findings
    for result in data.get('results', []):
        test_id = result.get('test_id', '')
        test_name = result.get('test_name', '')
        msg = result.get('issue_text', '')
        severity = result.get('issue_severity', 'LOW')
        confidence = result.get('issue_confidence', 'LOW')
        filepath = result.get('filename', '')
        lineno = result.get('line_number', 0)
        fname = os.path.basename(filepath)
        fp = _fingerprint('bandit', test_id, filepath, lineno, msg)
        title = _make_title('bandit', test_id, msg, fname, lineno, fp)
        body = (
            f'**Tool:** bandit  \n'
            f'**File:** `{filepath}:{lineno}`  \n'
            f'**Test:** `{test_id}` — {test_name}  \n'
            f'**Severity:** {severity} | **Confidence:** {confidence}  \n'
            f'**Message:** {msg}\n\n'
            f'---\n'
            f'*Opened automatically by the weekly code audit. '
            f'Close this issue once the finding is resolved or accepted.*'
        )
        findings.append((title, body, 'security'))
    return findings


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    _ensure_label()

    findings: list = []
    findings += _parse_flake8('flake8_results.txt')
    findings += _parse_bandit('bandit_results.json')

    print(f'Audit complete: {len(findings)} finding(s)')

    for title, body, extra_label in findings:
        _create_issue(title, body, extra_label)


if __name__ == '__main__':
    main()
