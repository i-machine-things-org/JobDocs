#!/usr/bin/env python3
"""Sanitize a markdown file to prevent recurring MD040 and MD024 lint violations.

Usage:
  python3 sanitize_review.py <file_path>

Changes applied:
  MD040 — Adds a 'text' language tag to bare opening fences (any backtick count >= 3).
           Closing fences are left unchanged. Content inside fenced blocks is not
           re-parsed for nested fences, matching CommonMark semantics.
  MD024 — Not applied here; duplicate headings are handled by the caller via the
           run-counter suffix in the heading line before appending.
"""
import re
import sys


def _strip_blockquote_prefix(line: str) -> tuple[str, str]:
    """Return (prefix, content) after stripping leading '> ' or '>' markers."""
    prefix = ""
    content = line
    while True:
        if content.startswith("> "):
            prefix += "> "
            content = content[2:]
        elif content.startswith(">"):
            prefix += ">"
            content = content[1:]
        else:
            break
    return prefix, content


def sanitize_fences(text: str) -> str:
    """Add 'text' to bare opening fences throughout the text."""
    lines = text.split("\n")
    result = []
    # Stack of opener backtick counts (int). Empty = not inside a fence.
    fence_stack: list[int] = []

    for line in lines:
        stripped = line.rstrip()
        prefix, content = _strip_blockquote_prefix(stripped)

        # Match a line that is purely backtick characters (3+) with optional trailing text.
        m = re.match(r"^(`{3,})(.*)", content)
        if m:
            backticks: str = m.group(1)
            rest: str = m.group(2).strip()
            n: int = len(backticks)

            if fence_stack and n >= fence_stack[-1] and not rest:
                # This line closes the innermost open fence.
                fence_stack.pop()
                result.append(stripped)
            elif not fence_stack and not rest:
                # Bare opening fence — add language tag.
                fence_stack.append(n)
                result.append(prefix + backticks + "text")
            else:
                # Either: opening fence with language already set,
                # or: a fence-like line that is content inside an outer fence.
                if not fence_stack:
                    fence_stack.append(n)
                result.append(stripped)
        else:
            result.append(stripped if stripped else line)

    return "\n".join(result)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sanitize_review.py <file_path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        original = f.read()

    sanitized = sanitize_fences(original)

    if sanitized != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(sanitized)


if __name__ == "__main__":
    main()
