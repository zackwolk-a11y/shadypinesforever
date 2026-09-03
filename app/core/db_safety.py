"""Live-database safety: fail-closed resolution, integrity checks, backups.

Built after a real data-loss incident: the live database silently defaulted
to ``./village.db`` (app.core.config.DEFAULT_DATABASE_URL) whenever
``DATABASE_URL`` wasn't exported in the exact process that touched it — no
``.env`` auto-loading exists, so this could and did happen invisibly. SQLite
itself makes it worse: connecting to any path that doesn't exist yet silently
manufactures a fresh, empty, schema-less database rather than erroring — the
forensic signature (~4KB file, zero tables, empty WAL, freshly-allocated SHM)
of that exact failure mode.

The fix is not "remember to export the variable correctly" — it's that
``APP_ENV=live`` must resolve to the canonical live path unconditionally,
must never silently manufacture a replacement for a missing/broken database,
and must never let a broken database look healthy enough to keep running
against.

Every function here takes its target path(s) as an explicit parameter with
the real canonical location as the default — so tests can point them at a
disposable temp path and never come near the real live database, while
production code (app.core.config, alembic/env.py, scripts/run_day.py,
app/web/control.py) gets the real path for free by not overriding it.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CANONICAL_LIVE_DB_PATH = REPO_ROOT / "data" / "live" / "internal_village.db"
LIVE_BACKUP_DIR = REPO_ROOT / "data" / "live" / "backups"

#: A schema-less/near-empty file is exactly the corruption signature the
#: real incident produced (SQLite's default page size is 4096 bytes; an
#: empty, no-tables database is exactly one page) — reject anything at or
#: below this outright, before even trying to open it.
MIN_LIVE_DB_BYTES = 8192

#: How many backups to retain per reason category (pre_run_day,
#: post_run_day, pre_migration, post_init, manual, ...) — oldest pruned
#: first. Applied per category, not globally, so a burst of one kind of
#: backup can never crowd out the only copy of another kind.
BACKUP_RETENTION_PER_REASON = 20


class LiveDatabaseError(Exception):
    """APP_ENV=live refuses to proceed. Always actionable — the message
    says what's wrong and what to do about it, never just "error"."""


@dataclass(frozen=True)
class LiveDbCheck:
    """The result of inspecting one SQLite file, read-only."""

    path: Path
    exists: bool
    size_bytes: int
    table_count: int | None
    integrity_ok: bool | None
    problem: str | None

    @property
    def healthy(self) -> bool:
        return self.problem is None


def check_live_db(path: Path) -> LiveDbCheck:
    """Read-only inspection. Uses SQLite's own read-only URI mode
    (``mode=ro``), which errors on a missing file instead of the default
    connect-creates-it behavior — the exact silent-creation failure mode
    this module exists to close off never happens here, even accidentally.
    """
    if not path.exists():
        return LiveDbCheck(path, False, 0, None, None, "does not exist")
    size = path.stat().st_size
    if size < MIN_LIVE_DB_BYTES:
        return LiveDbCheck(
            path, True, size, None, None,
            f"only {size} bytes (< {MIN_LIVE_DB_BYTES} minimum) — looks empty or corrupt",
        )
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            table_count = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            if table_count == 0:
                return LiveDbCheck(path, True, size, 0, None, "file exists but has zero tables")
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return LiveDbCheck(
                    path, True, size, table_count, False,
                    f"PRAGMA integrity_check failed: {integrity}",
                )
            return LiveDbCheck(path, True, size, table_count, True, None)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return LiveDbCheck(path, True, size, None, None, f"could not open: {exc}")


def resolve_live_database_url(*, allow_fresh_init: bool = False, path: Path | None = None) -> str:
    """The only function that may resolve APP_ENV=live to a real database
    URL. Never consults DATABASE_URL — that is the whole point: no missing
    or stale environment variable can substitute a different file. Fails
    closed (raises) unless the database is healthy, or the caller explicitly
    asked to initialize a fresh one AND no file exists yet — this function
    never overwrites an existing file, healthy or not; that is always a
    human decision (restore a backup, or deliberately move the bad file
    aside first).

    ``path`` defaults to ``None``, resolved to ``CANONICAL_LIVE_DB_PATH`` at
    call time rather than bound as a parameter default — this is what lets
    a test monkeypatch the module attribute and exercise the real call
    chain (app.core.config -> here -> scripts/run_day.py) against a
    disposable path, instead of only unit-testing this function in
    isolation.
    """
    if path is None:
        path = CANONICAL_LIVE_DB_PATH
    check = check_live_db(path)
    if not check.exists:
        if allow_fresh_init:
            return f"sqlite:///{path}"
        raise LiveDatabaseError(
            f"APP_ENV=live but no database exists at {path}. Refusing to silently "
            "create one. Run scripts/init_live_database.py --confirm to deliberately "
            "initialize a fresh live database, or restore one from "
            f"{LIVE_BACKUP_DIR} first."
        )
    if not check.healthy:
        raise LiveDatabaseError(
            f"APP_ENV=live database at {check.path} failed its safety check: "
            f"{check.problem}. Refusing to run against a database in this state. "
            f"Restore from {LIVE_BACKUP_DIR}, or investigate before continuing — "
            "this is the exact signature a real data-loss incident produced."
        )
    return f"sqlite:///{path}"


def checkpoint_and_copy(src: Path, dest: Path) -> None:
    """Force a full WAL checkpoint before copying, so the copy is a
    complete, self-contained snapshot. Copying the ``.db`` file alone while
    its ``-wal`` sibling still holds unflushed writes would silently
    produce an incomplete backup — the same "looks fine, isn't" trap this
    whole module exists to close off."""
    conn = sqlite3.connect(str(src))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
    finally:
        conn.close()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def create_backup(reason: str, *, source: Path | None = None, backup_dir: Path | None = None) -> Path:
    """Checkpoint + copy + verify, in that order. Raises LiveDatabaseError
    if the backup itself fails its own integrity check immediately after
    creation — a backup nobody can actually restore from is worse than no
    backup, because it hides that there is a problem until the moment you
    need it most.

    ``source``/``backup_dir`` default to ``None``, resolved to the module
    constants at call time — see ``resolve_live_database_url``'s docstring
    for why."""
    if source is None:
        source = CANONICAL_LIVE_DB_PATH
    if backup_dir is None:
        backup_dir = LIVE_BACKUP_DIR
    if not source.exists():
        raise LiveDatabaseError(f"cannot back up {source}: it does not exist")
    # Microsecond precision, not just seconds: RUN DAY can plausibly back up
    # twice in the same wall-clock second (a very short day), and a second
    # backup silently overwriting the first because their names collided
    # would be exactly the kind of quiet data loss this module exists to
    # prevent.
    timestamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + f".{time.time() % 1:.6f}"[2:] + "Z"
    dest = backup_dir / f"internal_village_{reason}_{timestamp}.db"
    checkpoint_and_copy(source, dest)
    check = check_live_db(dest)
    if not check.healthy:
        raise LiveDatabaseError(
            f"backup at {dest} failed verification immediately after creation: "
            f"{check.problem} — the source database may itself be unhealthy. "
            "The backup file was left in place for inspection, not deleted."
        )
    _prune_old_backups(reason, backup_dir)
    return dest


def _prune_old_backups(reason: str, backup_dir: Path) -> None:
    if not backup_dir.exists():
        return
    matches = sorted(backup_dir.glob(f"internal_village_{reason}_*.db"))
    excess = len(matches) - BACKUP_RETENTION_PER_REASON
    for stale in matches[: max(0, excess)]:
        stale.unlink(missing_ok=True)


def verify_backup(path: Path) -> LiveDbCheck:
    """Same check a live database gets — a backup that wouldn't pass this
    is not a usable backup."""
    return check_live_db(path)


def list_backups(backup_dir: Path | None = None) -> list[Path]:
    if backup_dir is None:
        backup_dir = LIVE_BACKUP_DIR
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("internal_village_*.db"))
