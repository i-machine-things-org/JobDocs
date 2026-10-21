#!/usr/bin/env python3
"""
Build the local cache of real JobBOSS employee identifiers used by the
pre-commit hook (tools/githooks/pre-commit) to block real HR data from
ever landing in a commit.

Background: an earlier session used real employee names/codes/hours as
worked examples while reverse-engineering the Employee Efficiency formula
(modules/reporting/reports/employee_efficiency.py), and committed and
pushed them to this public repo across ~20 commits before anyone noticed.
Nothing stops the same mistake recurring the next time someone (human or
Claude) needs a concrete example while debugging against the real
database -- except catching it mechanically before the commit happens.

Output: .claude/sensitive_identifiers.txt, one identifier per line
(Employee code + First_Name + Last_Name, deduplicated, blank/short/generic
entries dropped). Gitignored -- this file is itself real HR data and must
never be committed. Regenerate any time (cheap, ~250 rows): the DB is the
source of truth, not this cache.

Usage:
    python tools/generate_sensitive_identifiers.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experimental.db_integration import connect  # noqa: E402
from shared.utils import get_config_dir  # noqa: E402

import json  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / '.claude' / 'sensitive_identifiers.txt'

# Dropped as too short/common to check safely -- would false-positive on
# ordinary English words or short variable names in unrelated code (e.g. a
# 2-3 letter employee code or first name). The hook is a safety net, not a
# guarantee; real names below this length need a human to catch them.
_MIN_LENGTH = 4

_QUERY = """
SELECT Employee, First_Name, Last_Name
FROM Employee
"""


def main() -> int:
    settings_path = get_config_dir() / 'settings.json'
    if not settings_path.exists():
        print(f"No settings.json at {settings_path} -- nothing to do.", file=sys.stderr)
        return 1
    settings = json.loads(settings_path.read_text())

    identifiers = set()
    with connect(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(_QUERY)
            for row in cur.fetchall():
                for value in (row.get('Employee'), row.get('First_Name'), row.get('Last_Name')):
                    token = (value or '').strip()
                    if len(token) >= _MIN_LENGTH:
                        identifiers.add(token)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text('\n'.join(sorted(identifiers)) + '\n', encoding='utf-8')
    print(f"Wrote {len(identifiers)} identifiers to {OUTPUT_PATH}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
