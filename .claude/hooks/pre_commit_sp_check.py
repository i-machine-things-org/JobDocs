"""
Pre-commit S&P.md pattern checker for Claude Code (Windows-compatible).
Triggered via PreToolUse hook on Bash tool calls.
Reads tool input JSON from stdin, skips non-commit commands,
then checks the staged diff against known S&P.md anti-patterns.
"""

import sys
import json
import re
import subprocess


def get_staged_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True
        )
        return result.stdout
    except Exception:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("command", "")
    except Exception:
        sys.exit(0)

    # Only run on git commit commands
    if not re.search(r"git\s+commit", command):
        sys.exit(0)

    diff = get_staged_diff()
    if not diff:
        sys.exit(0)

    added_lines = [line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]

    warnings = []

    # ---------------------------------------------------------------
    # S&P checks — add new entries here as CodeRabbit reviews land
    # ---------------------------------------------------------------

    # [2026-04-06] Broad except Exception
    for line in added_lines:
        if re.search(r"except\s+Exception\b", line):
            warnings.append(
                "Broad 'except Exception' detected — use specific exceptions (e.g. OSError, AttributeError). [S&P 2026-04-06]"
            )
            break

    # [2026-04-06] Helper functions defined inside methods (8+ spaces = nested scope)
    for line in added_lines:
        if re.search(r"^\+\s{8,}def\s+_\w+", line):
            warnings.append(
                "Private helper function defined inside a method — move to class or module level. [S&P 2026-04-06]"
            )
            break

    # [2026-04-06] Sort key puts files before dirs (isdir without not)
    for line in added_lines:
        if re.search(r"key\s*=\s*lambda.*os\.path\.isdir", line) and not re.search(r"not\s+os\.path\.isdir", line):
            warnings.append(
                "Sort key may put files before directories — use 'not os.path.isdir(...)' to sort dirs first. [S&P 2026-04-06]"
            )
            break

    # ---------------------------------------------------------------

    if warnings:
        print()
        print(f"S&P.md Pre-commit Check — {len(warnings)} issue(s) found:")
        for w in warnings:
            print(f"  * {w}")
        print()
        print("Review S&P.md before proceeding. Commit is NOT blocked — fix on next commit if intentional.")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
