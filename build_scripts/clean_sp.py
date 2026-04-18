# ruff: noqa: RUF001, RUF002
"""
Strip raw CodeRabbit HTML noise from .claude/S&P.md.

Two modes:
  python build_scripts/clean_sp.py          — clean .claude/S&P.md in place
  python build_scripts/clean_sp.py --stdin  — read review body from stdin, write cleaned to stdout

The script handles:
  - </blockquote></details> on a single line (multiple closers per line)
  - Inline text before </details> is preserved (not dropped with the tag)
  - Counters reset only at genuine S&P top-level entry headings (## YYYY-MM-DD ...)
  - Noise blocks fully removed: 🤖 Prompt, 🪄 Autofix, ℹ️ Review info, etc.
  - Kept blocks flattened: <details> tags stripped, content preserved
"""
import re
import sys
from pathlib import Path

SP = Path('.claude/S&P.md')

# Summaries whose entire <details> block (including nested content) should be dropped.
NOISE_RE = re.compile(
    r'(🤖|🪄\s*Autofix|ℹ️\s*Review info|⚙️\s*Run configuration'
    r'|📥\s*Commits|⛔\s*Files ignored|📒\s*Files selected)',
    re.IGNORECASE,
)

# Dated S&P entry headings always reset depth/skip (they are always top-level).
_ENTRY_HEADING = re.compile(r'^## \d{4}-\d{2}-\d{2}')
# File-level H1 only resets counters when no block state is active.
_FILE_H1 = re.compile(r'^# (?!#)')


def strip_noise(text: str) -> str:
    lines = text.split('\n')
    out: list[str] = []
    skip = 0    # nesting depth while inside a noise block
    depth = 0   # nesting depth while inside a kept (flattened) block

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # ── S&P dated entry heading → always top-level, reset counters ─────────
        if _ENTRY_HEADING.match(s):
            skip = 0
            depth = 0
            out.append(line)
            i += 1
            continue

        # ── File H1 → only reset when not inside any block ───────────────────
        if _FILE_H1.match(s) and skip == 0 and depth == 0:
            out.append(line)
            i += 1
            continue

        # ── Lines containing </details> closers ───────────────────────────────
        # Process each </details> in order; emit text segments that are outside
        # noise blocks (do not drop the entire line when closers are inline).
        # After processing all closers, fall through to the opener branch in
        # case the same line also contains a <details> opener.
        if re.search(r'</details>', s, re.IGNORECASE):
            parts = re.split(r'(?i)</details>', line)
            kept = []
            for k, part in enumerate(parts):
                # Strip structural closing tags from this text segment
                seg = re.sub(r'(?i)</?blockquote>', '', part).strip()
                if seg and skip == 0 and not re.match(r'\s*<!--.*?-->\s*$', seg):
                    kept.append(seg)
                # Each split point represents one </details> closer
                if k < len(parts) - 1:
                    if skip > 0:
                        skip -= 1
                    elif depth > 0:
                        depth -= 1
            if kept:
                out.append(' '.join(kept))
            # If the last segment of the line contains an opener, handle it now
            # rather than continuing past it.
            last_seg = parts[-1] if parts else ''
            if re.search(r'<details>', last_seg, re.IGNORECASE):
                line = last_seg   # reprocess only the tail after the last closer
                s = line.strip()
                # fall through to the opener branch below
            else:
                i += 1
                continue

        # ── Opening <details> ─────────────────────────────────────────────────
        if re.search(r'<details>', s, re.IGNORECASE):
            if skip > 0:          # already inside a noise block
                skip += 1
                i += 1
                continue

            # Collect the <summary>...</summary> — may be on the same line or next
            combined = s
            j = i
            if '</summary>' not in combined.lower():
                j += 1
                while j < len(lines):
                    combined += '\n' + lines[j]
                    if '</summary>' in lines[j].lower():
                        break
                    j += 1

            sm = re.search(r'<summary>(.*?)</summary>', combined,
                           re.IGNORECASE | re.DOTALL)
            if sm and NOISE_RE.search(sm.group(1)):
                skip = 1          # enter noise block
                i = j + 1
                continue

            # Kept block: flatten — emit summary text, skip the tags
            depth += 1
            i = j + 1
            if sm:
                txt = re.sub(r'<[^>]+>', '', sm.group(1)).strip()
                if txt:
                    out.append(f'**{txt}**')
            continue

        # ── Inside a noise block → discard ───────────────────────────────────
        if skip > 0:
            i += 1
            continue

        # ── Regular line: strip residual HTML structural tags ─────────────────
        line = re.sub(r'</?blockquote>', '', line, flags=re.IGNORECASE)
        line = re.sub(r'</?summary[^>]*>', '', line, flags=re.IGNORECASE)

        # Remove HTML comment lines
        if re.match(r'\s*<!--.*?-->\s*$', line):
            i += 1
            continue

        out.append(line)
        i += 1

    # Collapse runs of 3+ blank lines to 2
    result = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
    return result.rstrip() + '\n'


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == '--stdin':
        # Review-body mode: read from stdin, write cleaned text to stdout.
        body = sys.stdin.read()
        sys.stdout.write(strip_noise(body).rstrip() + '\n')
        return

    # S&P.md in-place cleaning mode.
    original = SP.read_text(encoding='utf-8')
    cleaned = strip_noise(original)

    details_before = original.count('<details>')
    details_after  = cleaned.count('<details>')
    lines_before   = len(original.splitlines())
    lines_after    = len(cleaned.splitlines())

    SP.write_text(cleaned, encoding='utf-8')

    print('Done.')
    print(f'  <details> blocks: {details_before} -> {details_after}')
    print(f'  File size:        {len(original):,} -> {len(cleaned):,} chars')
    print(f'  Lines:            {lines_before:,} -> {lines_after:,}')


if __name__ == '__main__':
    main()
