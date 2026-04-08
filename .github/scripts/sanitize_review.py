#!/usr/bin/env python3
"""Sanitize a CodeRabbit review body for appending to S&P.md.

Reads REVIEW_BODY from the environment and writes the sanitized text to stdout.
Changes made:
  - Bare fence openers (``` or ````) gain a 'text' language tag (satisfies MD040).
    Closing fences are left unchanged so the block still closes correctly.
"""
import os

body = os.environ.get("REVIEW_BODY", "")
lines = body.split("\n")
result = []
fence_stack = []

for line in lines:
    stripped = line.rstrip()

    # Strip leading blockquote markers to inspect the raw fence token.
    content = stripped
    prefix = ""
    while content.startswith("> "):
        prefix += "> "
        content = content[2:]

    if content in ("```", "````"):
        if fence_stack and fence_stack[-1] == content:
            # Closing fence — emit unchanged.
            fence_stack.pop()
            result.append(stripped)
        else:
            # Opening fence with no language — add 'text'.
            fence_stack.append(content)
            result.append(prefix + content + "text")
    else:
        result.append(stripped if stripped else line)

print("\n".join(result))
