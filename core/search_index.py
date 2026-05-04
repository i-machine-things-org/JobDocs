"""
SQLite-backed search index for job folders and blueprint files.

Stored in the user's app data dir (per-machine). WAL mode allows concurrent
reads during background writes. Incremental updates only re-index directories
whose mtime has changed since the last run.
"""

import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY,
    prefix      TEXT    NOT NULL DEFAULT '',
    customer    TEXT    NOT NULL,
    job_number  TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    drawings    TEXT    NOT NULL DEFAULT '',
    path        TEXT    NOT NULL,
    mtime       REAL    NOT NULL,
    UNIQUE(prefix, path)
);

CREATE TABLE IF NOT EXISTS bp_files (
    id          INTEGER PRIMARY KEY,
    prefix      TEXT    NOT NULL,
    customer    TEXT    NOT NULL,
    filename    TEXT    NOT NULL,
    name_no_ext TEXT    NOT NULL,
    dir_path    TEXT    NOT NULL,
    rel_path    TEXT    NOT NULL,
    mtime       REAL    NOT NULL,
    UNIQUE(prefix, dir_path, filename)
);

CREATE TABLE IF NOT EXISTS indexed_dirs (
    dir_path    TEXT    NOT NULL,
    prefix      TEXT    NOT NULL DEFAULT '',
    kind        TEXT    NOT NULL DEFAULT '',
    mtime       REAL    NOT NULL,
    indexed_at  REAL    NOT NULL,
    PRIMARY KEY (dir_path, prefix, kind)
);

CREATE INDEX IF NOT EXISTS idx_jobs_number      ON jobs(job_number  COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_cust        ON jobs(customer    COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_desc        ON jobs(description COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_draw        ON jobs(drawings    COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_cust_prefix ON jobs(customer, prefix);
CREATE INDEX IF NOT EXISTS idx_bp_filename      ON bp_files(filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_bp_cust          ON bp_files(customer COLLATE NOCASE);
"""

_MIGRATION_V1 = """
BEGIN;
CREATE TABLE jobs_v1 (
    id          INTEGER PRIMARY KEY,
    prefix      TEXT    NOT NULL DEFAULT '',
    customer    TEXT    NOT NULL,
    job_number  TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    drawings    TEXT    NOT NULL DEFAULT '',
    path        TEXT    NOT NULL,
    mtime       REAL    NOT NULL,
    UNIQUE(prefix, path)
);
INSERT OR IGNORE INTO jobs_v1
    SELECT id, prefix, customer, job_number, description, drawings, path, mtime
    FROM jobs;
DROP TABLE jobs;
ALTER TABLE jobs_v1 RENAME TO jobs;

CREATE TABLE bp_files_v1 (
    id          INTEGER PRIMARY KEY,
    prefix      TEXT    NOT NULL,
    customer    TEXT    NOT NULL,
    filename    TEXT    NOT NULL,
    name_no_ext TEXT    NOT NULL,
    dir_path    TEXT    NOT NULL,
    rel_path    TEXT    NOT NULL,
    mtime       REAL    NOT NULL,
    UNIQUE(prefix, dir_path, filename)
);
INSERT OR IGNORE INTO bp_files_v1
    SELECT id, prefix, customer, filename, name_no_ext, dir_path, rel_path, mtime
    FROM bp_files;
DROP TABLE bp_files;
ALTER TABLE bp_files_v1 RENAME TO bp_files;

CREATE INDEX IF NOT EXISTS idx_jobs_number      ON jobs(job_number  COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_cust        ON jobs(customer    COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_desc        ON jobs(description COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_draw        ON jobs(drawings    COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_jobs_cust_prefix ON jobs(customer, prefix);
CREATE INDEX IF NOT EXISTS idx_bp_filename      ON bp_files(filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_bp_cust          ON bp_files(customer COLLATE NOCASE);

PRAGMA user_version = 1;
COMMIT;
"""

_MIGRATION_V2 = """
BEGIN;
DROP TABLE IF EXISTS indexed_dirs;
CREATE TABLE indexed_dirs (
    dir_path    TEXT    NOT NULL,
    prefix      TEXT    NOT NULL DEFAULT '',
    kind        TEXT    NOT NULL DEFAULT '',
    mtime       REAL    NOT NULL,
    indexed_at  REAL    NOT NULL,
    PRIMARY KEY (dir_path, prefix, kind)
);
PRAGMA user_version = 2;
COMMIT;
"""

_MAX_RESULTS = 500


def _escape_like(term: str) -> str:
    """Escape SQL LIKE special characters so literal underscores and percent signs match.

    Uses backslash as the escape character — pair with ESCAPE '\\' in SQL.
    (_like_prefix uses '!' instead so Windows backslashes in paths are treated as literals.)
    """
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _like_prefix(path: str) -> str:
    """Return a LIKE pattern (ESCAPE '!') matching path and all paths beneath it.

    Uses '!' as the escape character rather than '\\' because Windows paths
    contain backslashes that SQLite would otherwise consume as LIKE escape
    sequences, silently corrupting the match.
    """
    return path.replace('!', '!!').replace('%', '!%').replace('_', '!_') + os.sep + '%'


def _parse_job_folder(dir_name: str) -> Tuple[str, str, List[str]]:
    """Extract (job_number, description, drawings) from a folder name.

    Handles underscore-separated names (12345_Desc_DWG-A) and free-form names
    that start with a job number but use spaces, dashes, or no separator
    (e.g. '12345 Bracket Assembly', '12345-Shaft').
    """
    m = re.match(r'^(\d+)', dir_name)
    if not m:
        return '', dir_name, []
    job_number = m.group(1)
    remainder = dir_name[m.end():].lstrip('_- ')

    if not remainder:
        return job_number, '', []

    if '_' in remainder:
        parts = remainder.split('_')
        if '-' in parts[-1]:
            drawings = [d.strip() for d in parts[-1].split('-') if d.strip()]
            desc = ' '.join(parts[:-1])
        else:
            drawings = []
            desc = ' '.join(parts)
    else:
        drawings = []
        desc = remainder

    return job_number, desc, drawings


class SearchIndex:
    """Persistent search index over job folders and blueprint files."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self, timeout: float = 10.0) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=timeout)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        try:
            with closing(self._connect()) as conn:
                with conn:
                    conn.executescript(_SCHEMA)
                    self._migrate(conn)
        except sqlite3.Error as exc:
            logger.error("search_index: failed to initialise DB: %s", exc)
            raise

    def _migrate(self, conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version >= 2:
            return
        if version < 1:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone()
            if row and 'UNIQUE(path)' in (row[0] or ''):
                logger.info("search_index: migrating schema to v1 (prefix-aware UNIQUE constraints)")
                conn.executescript(_MIGRATION_V1)
            else:
                conn.execute("PRAGMA user_version = 1")
        logger.info("search_index: migrating schema to v2 (kind-aware indexed_dirs)")
        conn.executescript(_MIGRATION_V2)

    def _dir_mtime(self, path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    def _subtree_mtime(self, path: str) -> float:
        """Return the max mtime of path and all descendant directories (not files)."""
        try:
            result = os.path.getmtime(path)
            for root, dirs, _ in os.walk(path):
                for d in dirs:
                    try:
                        result = max(result, os.path.getmtime(os.path.join(root, d)))
                    except OSError:
                        pass
            return result
        except OSError:
            return 0.0

    def _is_stale(
        self, conn: sqlite3.Connection, dir_path: str, prefix: str, kind: str, *, recursive: bool = False
    ) -> bool:
        if recursive:
            return self._is_stale_recursive(conn, dir_path, prefix, kind)
        current = self._dir_mtime(dir_path)
        row = conn.execute(
            "SELECT mtime FROM indexed_dirs WHERE dir_path=? AND prefix=? AND kind=?",
            (dir_path, prefix, kind),
        ).fetchone()
        return row is None or current != row['mtime']

    def _is_stale_recursive(self, conn: sqlite3.Connection, dir_path: str, prefix: str, kind: str) -> bool:
        """Walk the subtree and short-circuit on the first directory modified after
        indexed_at.  Avoids computing a global max-mtime on every launch.
        """
        row = conn.execute(
            "SELECT indexed_at FROM indexed_dirs WHERE dir_path=? AND prefix=? AND kind=?",
            (dir_path, prefix, kind),
        ).fetchone()
        if row is None:
            return True
        indexed_at: float = row['indexed_at']
        try:
            if os.path.getmtime(dir_path) > indexed_at:
                return True
            for root, dirs, _ in os.walk(dir_path):
                for d in dirs:
                    try:
                        if os.path.getmtime(os.path.join(root, d)) > indexed_at:
                            return True
                    except OSError:
                        pass
            return False
        except OSError:
            return True

    def _mark_indexed(
        self, conn: sqlite3.Connection, dir_path: str, prefix: str, kind: str, *, recursive: bool = False
    ) -> None:
        # For recursive dirs, store wall-clock time as mtime so the _is_stale
        # non-recursive path still has a sensible value if the same row is ever
        # reused.  _is_stale_recursive uses indexed_at directly, not mtime.
        mtime = time.time() if recursive else self._dir_mtime(dir_path)
        conn.execute(
            """INSERT INTO indexed_dirs(dir_path, prefix, kind, mtime, indexed_at)
               VALUES(?,?,?,?,?)
               ON CONFLICT(dir_path, prefix, kind)
               DO UPDATE SET mtime=excluded.mtime, indexed_at=excluded.indexed_at""",
            (dir_path, prefix, kind, mtime, time.time()),
        )

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def update(
        self,
        cf_dirs: List[Tuple[str, str]],
        bp_dirs: List[Tuple[str, str]],
        app_context,
        progress: Optional[Callable[[str], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Incrementally update the index. Only stale directories are re-indexed."""

        def _emit(msg: str) -> None:
            if progress:
                progress(msg)

        def _cancelled() -> bool:
            return bool(cancelled and cancelled())

        # Duplicate prefixes within cf_dirs or bp_dirs would cause DELETE
        # statements scoped by prefix to silently wipe rows from the other root.
        cf_prefixes_seen: set = set()
        for prefix, _ in cf_dirs:
            if prefix in cf_prefixes_seen:
                logger.error(
                    "search_index: duplicate cf prefix %r in cf_dirs — aborting update to prevent data loss",
                    prefix,
                )
                return
            cf_prefixes_seen.add(prefix)
        bp_prefixes_seen: set = set()
        for prefix, _ in bp_dirs:
            if prefix in bp_prefixes_seen:
                logger.error(
                    "search_index: duplicate bp prefix %r in bp_dirs — aborting update to prevent data loss",
                    prefix,
                )
                return
            bp_prefixes_seen.add(prefix)

        try:
            with closing(self._connect()) as conn, conn:
                # Purge rows for prefixes that are no longer in config so stale
                # data from removed directories does not persist indefinitely.
                all_cf_prefixes = cf_prefixes_seen
                all_bp_prefixes = bp_prefixes_seen

                if all_cf_prefixes:
                    _ph = ','.join('?' * len(all_cf_prefixes))
                    conn.execute(  # nosec B608
                        f"DELETE FROM jobs WHERE prefix NOT IN ({_ph})",
                        tuple(all_cf_prefixes),
                    )
                    conn.execute(  # nosec B608
                        f"DELETE FROM indexed_dirs WHERE kind='cf' AND prefix NOT IN ({_ph})",
                        tuple(all_cf_prefixes),
                    )
                else:
                    conn.execute("DELETE FROM jobs")
                    conn.execute("DELETE FROM indexed_dirs WHERE kind='cf'")

                if all_bp_prefixes:
                    _ph = ','.join('?' * len(all_bp_prefixes))
                    conn.execute(  # nosec B608
                        f"DELETE FROM bp_files WHERE prefix NOT IN ({_ph})",
                        tuple(all_bp_prefixes),
                    )
                    conn.execute(  # nosec B608
                        f"DELETE FROM indexed_dirs WHERE kind='bp' AND prefix NOT IN ({_ph})",
                        tuple(all_bp_prefixes),
                    )
                else:
                    conn.execute("DELETE FROM bp_files")
                    conn.execute("DELETE FROM indexed_dirs WHERE kind='bp'")

                # --- Customer files dirs ---
                for prefix, base_dir in cf_dirs:
                    if _cancelled():
                        return
                    try:
                        customers = [
                            d for d in os.listdir(base_dir)
                            if os.path.isdir(os.path.join(base_dir, d))
                        ]
                    except OSError:
                        continue

                    # Purge rows for customers that no longer exist on disk.
                    if not _cancelled():
                        customer_set = set(customers)
                        if customer_set:
                            placeholders = ','.join('?' * len(customer_set))
                            conn.execute(
                                f"DELETE FROM jobs WHERE prefix=? AND customer NOT IN ({placeholders})",  # nosec B608
                                (prefix, *customer_set),
                            )
                        else:
                            conn.execute("DELETE FROM jobs WHERE prefix=?", (prefix,))

                    for customer in customers:
                        if _cancelled():
                            return
                        customer_path = os.path.join(base_dir, customer)

                        # Cheap precheck using previously indexed container dirs
                        # before calling the expensive find_job_folders.
                        prev_containers = {
                            row[0] for row in conn.execute(
                                "SELECT dir_path FROM indexed_dirs"
                                " WHERE prefix=? AND kind=? AND dir_path LIKE ? ESCAPE '!'",
                                (prefix, 'cf', _like_prefix(customer_path)),
                            )
                        }
                        if not any(self._is_stale(conn, d, prefix, 'cf') for d in prev_containers | {customer_path}):
                            continue

                        # Discover jobs to get the actual container dirs (the subdirs
                        # that hold job folders). Checking these — not just the customer
                        # root — detects new/deleted jobs inside existing subdirs.
                        scan_errors: List[Exception] = []
                        try:
                            jobs = app_context.find_job_folders(customer_path, errors=scan_errors)
                        except OSError as exc:
                            logger.warning("search_index: find_job_folders(%s): %s", customer_path, exc)
                            continue  # preserve existing rows on scan failure
                        if scan_errors:
                            logger.warning(
                                "search_index: find_job_folders(%s) partial scan"
                                " (%d error(s)); preserving existing rows",
                                customer_path, len(scan_errors),
                            )
                            continue

                        # Track customer_path itself plus all ancestor dirs between
                        # it and each job_docs_path so PO-level dirs are recorded
                        # in indexed_dirs. customer_path must be included so the
                        # precheck can confirm it was indexed and avoid calling
                        # find_job_folders every run.
                        customer_p = Path(customer_path)
                        container_dirs: set = {customer_path}
                        for _, job_docs_path in jobs:
                            for p in Path(job_docs_path).parents:
                                if p == customer_p:
                                    break
                                container_dirs.add(str(p))
                        all_containers = container_dirs | prev_containers

                        if not any(self._is_stale(conn, d, prefix, 'cf') for d in all_containers):
                            continue

                        _emit(f"Indexing {customer}…")

                        # Accumulate new rows before touching the DB so a cancelled
                        # fallback scan never leaves the customer with zero rows.
                        new_job_rows = []
                        scan_cancelled = False
                        scan_failed = False

                        for dir_name, job_docs_path in jobs:
                            if not dir_name or not dir_name[0].isdigit():
                                continue
                            job_number, desc, drawings = _parse_job_folder(dir_name)
                            try:
                                mtime = os.path.getmtime(job_docs_path)
                            except OSError:
                                continue
                            new_job_rows.append((
                                prefix, customer, job_number, desc,
                                ','.join(drawings), job_docs_path, mtime,
                            ))

                        if not jobs:
                            # find_job_folders requires a specific subfolder structure.
                            # When none is found, scan the customer directory directly so
                            # customers with non-standard layouts are still indexed.
                            try:
                                for item in os.listdir(customer_path):
                                    if _cancelled():
                                        scan_cancelled = True
                                        break
                                    if not item or not item[0].isdigit():
                                        continue
                                    item_path = os.path.join(customer_path, item)
                                    if not os.path.isdir(item_path):
                                        continue
                                    job_number, desc, drawings = _parse_job_folder(item)
                                    try:
                                        mtime = os.path.getmtime(item_path)
                                    except OSError:
                                        continue
                                    new_job_rows.append((
                                        prefix, customer, job_number, desc,
                                        ','.join(drawings), item_path, mtime,
                                    ))
                            except OSError as exc:
                                scan_failed = True
                                logger.warning("search_index: fallback scan(%s): %s", customer_path, exc)

                        if not scan_cancelled and not scan_failed:
                            conn.execute(
                                "DELETE FROM jobs WHERE customer=? AND prefix=?",
                                (customer, prefix),
                            )
                            conn.executemany(
                                """INSERT OR REPLACE INTO jobs
                                   (prefix, customer, job_number, description, drawings, path, mtime)
                                   VALUES(?,?,?,?,?,?,?)""",
                                new_job_rows,
                            )
                            for d in container_dirs:
                                self._mark_indexed(conn, d, prefix, 'cf')

                            # Prune indexed_dirs rows for containers that no longer
                            # exist (deleted job folders). Without this, _is_stale()
                            # returns True for the missing path forever and the
                            # customer is re-indexed on every launch.
                            stale_containers = prev_containers - container_dirs
                            for d in stale_containers:
                                conn.execute(
                                    "DELETE FROM indexed_dirs WHERE dir_path=? AND prefix=? AND kind=?",
                                    (d, prefix, 'cf'),
                                )

                # --- Blueprint / IR dirs ---
                for prefix, base_dir in bp_dirs:
                    if _cancelled():
                        return
                    try:
                        customers = [
                            d for d in os.listdir(base_dir)
                            if os.path.isdir(os.path.join(base_dir, d))
                        ]
                    except OSError:
                        continue

                    # Purge rows for customers that no longer exist on disk.
                    if not _cancelled():
                        customer_set = set(customers)
                        if customer_set:
                            placeholders = ','.join('?' * len(customer_set))
                            conn.execute(
                                f"DELETE FROM bp_files WHERE prefix=? AND customer NOT IN ({placeholders})",  # nosec B608
                                (prefix, *customer_set),
                            )
                        else:
                            conn.execute("DELETE FROM bp_files WHERE prefix=?", (prefix,))

                        # Prune indexed_dirs rows for customer paths that disappeared.
                        prev_indexed = {
                            row[0] for row in conn.execute(
                                "SELECT dir_path FROM indexed_dirs"
                                " WHERE prefix=? AND kind=? AND dir_path LIKE ? ESCAPE '!'",
                                (prefix, 'bp', _like_prefix(base_dir)),
                            )
                        }
                        valid_paths = {os.path.join(base_dir, c) for c in customer_set}
                        for stale_path in prev_indexed - valid_paths:
                            conn.execute(
                                "DELETE FROM indexed_dirs WHERE dir_path=? AND prefix=? AND kind=?",
                                (stale_path, prefix, 'bp'),
                            )

                    for customer in customers:
                        if _cancelled():
                            return
                        customer_path = os.path.join(base_dir, customer)

                        if not self._is_stale(conn, customer_path, prefix, 'bp', recursive=True):
                            continue

                        _emit(f"Indexing {prefix} files…")

                        # Collect rows before touching the DB so a cancelled walk
                        # never leaves the customer with zero indexed rows.
                        new_rows: List[Tuple] = []
                        completed = False
                        walk_failed = False

                        def _on_walk_error(err: OSError, _path: str = customer_path) -> None:
                            nonlocal walk_failed
                            walk_failed = True
                            logger.warning("search_index: os.walk(%s): %s", _path, err)

                        try:
                            for root, _dirs, files in os.walk(customer_path, onerror=_on_walk_error):
                                if _cancelled():
                                    break
                                rel_path = os.path.relpath(root, base_dir)
                                for filename in files:
                                    file_path = os.path.join(root, filename)
                                    try:
                                        mtime = os.path.getmtime(file_path)
                                    except OSError:
                                        continue
                                    new_rows.append((
                                        prefix, customer, filename,
                                        os.path.splitext(filename)[0],
                                        root, rel_path, mtime,
                                    ))
                            else:
                                completed = True
                        except OSError as exc:
                            walk_failed = True
                            logger.warning("search_index: os.walk(%s): %s", customer_path, exc)

                        completed = completed and not walk_failed

                        if completed:
                            conn.execute(
                                "DELETE FROM bp_files WHERE prefix=? AND customer=?",
                                (prefix, customer),
                            )
                            conn.executemany(
                                """INSERT OR REPLACE INTO bp_files
                                   (prefix, customer, filename, name_no_ext,
                                    dir_path, rel_path, mtime)
                                   VALUES(?,?,?,?,?,?,?)""",
                                new_rows,
                            )
                            self._mark_indexed(conn, customer_path, prefix, 'bp', recursive=True)

        except sqlite3.OperationalError as exc:
            if "database is locked" in str(exc).lower():
                # Another writer holds the lock — skip this update cycle.
                logger.warning("search_index: could not acquire write lock: %s", exc)
            else:
                logger.error("search_index: operational error during update: %s", exc)
                raise

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def is_populated(self) -> bool:
        """Return True if the index contains at least one job or blueprint file."""
        try:
            with closing(self._connect(timeout=2.0)) as conn:
                row = conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM jobs LIMIT 1)"
                    " OR EXISTS(SELECT 1 FROM bp_files LIMIT 1)"
                ).fetchone()
                return bool(row[0])
        except sqlite3.Error:
            return False

    def search_jobs(
        self,
        term: str,
        search_customer: bool = True,
        search_job: bool = True,
        search_desc: bool = True,
        search_drawing: bool = True,
    ) -> List[Dict]:
        """Search jobs table; returns up to _MAX_RESULTS results ordered by mtime."""
        escaped = _escape_like(term)
        like = f'%{escaped}%'
        conditions, params = [], []
        if search_customer:
            conditions.append("customer LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(like)
        if search_job:
            conditions.append("job_number LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(like)
        if search_desc:
            conditions.append("description LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(like)
        if search_drawing:
            conditions.append("drawings LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(like)
        if not conditions:
            return []

        sql = (
            f"SELECT * FROM jobs WHERE ({' OR '.join(conditions)}) "  # nosec B608
            f"ORDER BY mtime DESC LIMIT {_MAX_RESULTS}"
        )
        with closing(self._connect(timeout=5.0)) as conn:
            rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            drawings = [d for d in row['drawings'].split(',') if d]
            prefix = row['prefix']
            display_customer = f"[ITAR] {row['customer']}" if prefix == 'ITAR' else row['customer']
            results.append({
                'date': datetime.fromtimestamp(row['mtime']),
                'customer': display_customer,
                'job_number': row['job_number'],
                'description': row['description'],
                'drawings': drawings,
                'path': row['path'],
            })
        return results

    def search_bp(self, term: str) -> List[Dict]:
        """Search blueprint files by filename; returns up to _MAX_RESULTS results."""
        escaped = _escape_like(term)
        like = f'%{escaped}%'
        sql = (
            f"SELECT * FROM bp_files WHERE filename LIKE ? ESCAPE '\\' COLLATE NOCASE "  # nosec B608
            f"ORDER BY mtime DESC LIMIT {_MAX_RESULTS}"
        )
        with closing(self._connect(timeout=5.0)) as conn:
            rows = conn.execute(sql, (like,)).fetchall()

        results = []
        for row in rows:
            prefix = row['prefix']
            customer = row['customer']
            if prefix and customer:
                display_customer = f"[{prefix}] {customer}"
            elif prefix:
                display_customer = f"[{prefix}]"
            else:
                display_customer = customer or ''
            results.append({
                'date': datetime.fromtimestamp(row['mtime']),
                'customer': display_customer,
                'job_number': row['name_no_ext'],
                'description': row['rel_path'] if row['rel_path'] != '.' else '',
                'drawings': [],
                'path': row['dir_path'],
            })
        return results

    def job_count(self) -> int:
        """Return total number of indexed job rows."""
        try:
            with closing(self._connect(timeout=2.0)) as conn:
                return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        except sqlite3.Error:
            return 0
