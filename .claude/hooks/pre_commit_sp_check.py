"""
Pre-commit coding-notes pattern checker for Claude Code (Windows-compatible).
Triggered via PreToolUse hook on Bash tool calls.
Reads tool input JSON from stdin, skips non-commit commands,
then checks the staged diff against known .claude/CODING_NOTES.md anti-patterns.
"""

import sys
import json
import re
import shlex
import shutil
import subprocess


# git global options that consume the following token as their argument
_ARG_OPTIONS = frozenset({
    "-C", "-c", "--exec-path", "--git-dir",
    "--work-tree", "--namespace", "--super-prefix",
    "--list-cmds",
})
_OPERATOR_CHARS = frozenset("();<>|&")


def _command_segments(command: str) -> list:
    """Split a shell command line into simple commands at &&, ||, ;, |, & and newlines.

    Only the first git invocation used to be inspected, so `git add f && git commit` looked like a plain
    `git add` and the staged-diff check silently never ran. Newlines are turned into `;` first because shlex
    treats them as plain whitespace; inside quotes (a multi-line commit message) they stay part of one token.
    """
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments, current = [], []
    for tok in lexer:
        if tok and all(ch in _OPERATOR_CHARS for ch in tok):
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)
    return [seg for seg in segments if seg]


def _segment_is_git_commit(tokens: list) -> bool:
    try:
        git_idx = next(i for i, t in enumerate(tokens) if t == "git" or t.endswith("/git"))
    except StopIteration:
        return False
    i = git_idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in _ARG_OPTIONS:
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            return tok == "commit"
    return False


def _is_git_commit_command(command: str) -> bool:
    """Return True when any simple command in the line invokes the git commit subcommand."""
    try:
        segments = _command_segments(command)
    except ValueError:
        return bool(re.search(r"git\s+commit", command))
    return any(_segment_is_git_commit(seg) for seg in segments)


def _added_lines_by_file(diff: str) -> list:
    """Return (path, added line) pairs from a unified diff, so checks can be limited to the right file types."""
    pairs, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/")
        elif line.startswith("+"):
            pairs.append((path, line))
    return pairs


def get_staged_diff() -> str:
    git = shutil.which("git")
    if not git:
        return ""
    try:
        result = subprocess.run(
            [git, "diff", "--cached"],
            capture_output=True, text=True
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def main():
    try:
        data = json.load(sys.stdin)
        # A PreToolUse hook matched on Bash receives the command nested at tool_input.command, not
        # top-level — reading the top-level key always returned "", so this check silently no-op'd
        # on every single commit since it was written. Confirmed against Claude Code's real
        # PreToolUse hook input schema and caught by CodeRabbit on i-machine-arr/reaparr PR #2.
        command = data.get("tool_input", {}).get("command", "")
    except json.JSONDecodeError:
        sys.exit(0)

    if not _is_git_commit_command(command):
        sys.exit(0)

    diff = get_staged_diff()
    if not diff:
        sys.exit(0)

    added = _added_lines_by_file(diff)
    added_lines = [line for _, line in added]  # line-only view used by the checks below

    warnings = []

    # ---------------------------------------------------------------
    # Coding-notes checks — add new entries here as CodeRabbit reviews land
    # ---------------------------------------------------------------

    # [2026-04-06] Broad except Exception
    # Python files only: docs that show the anti-pattern as an example must not trip it.
    for path, line in added:
        if path.endswith(".py") and re.search(r"except\s+Exception\b", line):
            warnings.append(
                "Broad 'except Exception' detected — use specific exceptions "
                "(e.g. OSError, AttributeError). [CODING_NOTES 2026-04-06]"
            )
            break

    # [2026-04-06] Helper functions defined inside methods (8+ spaces = nested scope)
    for line in added_lines:
        if re.search(r"^\+\s{8,}def\s+_\w+", line):
            warnings.append(
                "Private helper function defined inside a method — move to class or "
                "module level. [CODING_NOTES 2026-04-06]"
            )
            break

    # [2026-04-06] Sort key puts files before dirs (isdir without not)
    for line in added_lines:
        if re.search(r"key\s*=\s*lambda.*os\.path\.isdir", line) and not re.search(r"not\s+os\.path\.isdir", line):
            warnings.append(
                "Sort key may put files before directories — "
                "use 'not os.path.isdir(...)' to sort dirs first. [CODING_NOTES 2026-04-06]"
            )
            break

    # ---------------------------------------------------------------

    if warnings:
        message = (
            f"Coding Notes Pre-commit Check — {len(warnings)} issue(s) found:\n"
            + "\n".join(f"  * {w}" for w in warnings)
            + "\n\nReview .claude/CODING_NOTES.md before proceeding. Commit is NOT blocked — "
              "fix on next commit if intentional."
        )
        # Plain stdout from a PreToolUse hook is only logged. systemMessage shows the warning to the user;
        # additionalContext puts it in front of Claude. Neither blocks the tool call (no permissionDecision).
        print(json.dumps({
            "systemMessage": message,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": message},
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
