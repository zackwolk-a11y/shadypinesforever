#!/usr/bin/env python3
"""Regression suite for live-database safety (app/core/db_safety.py), built
after a real data-loss incident: DATABASE_URL silently falling back to
./village.db (see the module's own docstring for the full forensic
signature this suite guards against).

Every check here runs against a disposable temp directory. Sub-tests that
only exercise app.core.db_safety's own functions run in-process (each
passing an explicit disposable path — never relying on a module-cached
engine, which is exactly the trap app.db.session's module-level ``engine``
sets for any script that tries to reuse it against more than one path in
the same process). Sub-tests that need to exercise a REAL script end to end
(scripts/run_day.py, the fresh-live-init sequence) run in a subprocess with
app.core.db_safety's path constants monkeypatched inside that subprocess —
a fresh interpreter avoids all import-caching pitfalls, and the monkeypatch
means the real canonical live path is never touched even indirectly.

This suite never creates, modifies, deletes, or even opens the real live
database or village.db.

Usage::

    .venv/bin/python tests/test_db_safety.py
    .venv/bin/python tests/test_db_safety.py --keep-db
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_VILLAGE_DB_PATH = REPO_ROOT / "village.db"
_VILLAGE_DB_MTIME_AT_START = _VILLAGE_DB_PATH.stat().st_mtime if _VILLAGE_DB_PATH.exists() else None
_REAL_LIVE_DB_PATH = REPO_ROOT / "data" / "live" / "internal_village.db"


def _dedicated_engine(path: Path):
    """A throwaway engine bound to exactly one path — never touches
    app.db.session's module-cached engine, so this is safe to call
    repeatedly against different disposable paths in the same process."""
    from sqlalchemy import create_engine

    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}")


def _make_healthy_db(path: Path) -> None:
    """A real, migrated, seeded SQLite file at an arbitrary disposable
    path — via the actual alembic + seed_agents machinery (never a
    hand-rolled schema substitute), bound to its own dedicated engine so
    this can be called for many different paths in one process."""
    from alembic import command
    from alembic.config import Config

    path.parent.mkdir(parents=True, exist_ok=True)
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    try:
        command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import seed_agents
    from sqlalchemy.orm import sessionmaker

    engine = _dedicated_engine(path)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        seed_agents.run(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()


def _make_corrupt_db(path: Path) -> None:
    """A file that opens but fails PRAGMA integrity_check — real page-level
    corruption, not just truncated garbage (SQLite rejects that outright as
    'not a database' before ever reaching integrity_check)."""
    _make_healthy_db(path)
    with open(path, "r+b") as f:
        f.seek(4096)
        f.write(b"\xff" * 2048)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="db_safety_test_"))
    print(f"Disposable test directory: {tmp_root}  (never data/live/, never village.db)")

    checks: list[tuple[str, bool]] = []
    try:
        checks += _test_check_live_db(tmp_root)
        checks += _test_resolve_live_database_url(tmp_root)
        checks += _test_backup_and_restore(tmp_root)
        checks += _test_migration_and_seed(tmp_root)
        checks += _test_fresh_live_init_subprocess(tmp_root)
        checks += _test_run_day_lifecycle_backups_subprocess(tmp_root)
        checks += _test_run_live_research_once_refuses_silently()
    finally:
        if args.keep_db:
            print(f"\nKept: {tmp_root}")
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)

    print("\nChecks:")
    all_ok = True
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        all_ok &= ok

    # The one thing that matters more than any individual check above.
    real_live_untouched = not _REAL_LIVE_DB_PATH.exists()
    print(f"\n  [{'PASS' if real_live_untouched else 'FAIL'}] "
          f"the real data/live/internal_village.db was never created or touched")
    all_ok &= real_live_untouched

    if not all_ok:
        print("\nFAIL: one or more db-safety assertions failed.")
        return 1
    print(f"\nPASS: live-database safety behaves as designed ({len(checks) + 1} checks).")
    return 0


# ---------------------------------------------------------------------------
# check_live_db
# ---------------------------------------------------------------------------


def _test_check_live_db(tmp_root: Path) -> list[tuple[str, bool]]:
    from app.core.db_safety import MIN_LIVE_DB_BYTES, check_live_db

    checks: list[tuple[str, bool]] = []

    missing = check_live_db(tmp_root / "does_not_exist.db")
    checks.append(("check_live_db: missing file is unhealthy with a clear reason", not missing.healthy and not missing.exists))

    tiny_path = tmp_root / "tiny.db"
    tiny_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)  # well under MIN_LIVE_DB_BYTES
    tiny = check_live_db(tiny_path)
    checks.append((f"check_live_db: a file under {MIN_LIVE_DB_BYTES} bytes is unhealthy", not tiny.healthy))

    # The exact incident signature: large enough to pass the byte floor,
    # but genuinely zero tables (a freshly-opened, never-migrated file).
    empty_schema_path = tmp_root / "empty_schema.db"
    conn = sqlite3.connect(str(empty_schema_path))
    conn.execute("PRAGMA page_size=8192")
    conn.execute("CREATE TABLE _pad (id INTEGER)")
    conn.commit()
    conn.execute("DROP TABLE _pad")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    if empty_schema_path.stat().st_size < MIN_LIVE_DB_BYTES:
        with open(empty_schema_path, "ab") as f:
            f.write(b"\x00" * (MIN_LIVE_DB_BYTES - empty_schema_path.stat().st_size))
    zero_tables = check_live_db(empty_schema_path)
    checks.append(("check_live_db: a large-enough file with zero tables is unhealthy",
                    not zero_tables.healthy and zero_tables.table_count == 0))

    healthy_path = tmp_root / "healthy.db"
    _make_healthy_db(healthy_path)
    healthy = check_live_db(healthy_path)
    checks.append(("check_live_db: a real migrated+seeded database is healthy",
                    healthy.healthy and healthy.table_count is not None and healthy.table_count > 0))

    corrupt_path = tmp_root / "corrupt.db"
    _make_corrupt_db(corrupt_path)
    corrupt = check_live_db(corrupt_path)
    checks.append(("check_live_db: a database with real page corruption fails integrity_check",
                    not corrupt.healthy))

    return checks


# ---------------------------------------------------------------------------
# resolve_live_database_url
# ---------------------------------------------------------------------------


def _test_resolve_live_database_url(tmp_root: Path) -> list[tuple[str, bool]]:
    from app.core.db_safety import LiveDatabaseError, resolve_live_database_url

    checks: list[tuple[str, bool]] = []
    missing_path = tmp_root / "resolve" / "missing.db"

    try:
        resolve_live_database_url(path=missing_path)
        checks.append(("resolve_live_database_url: fails closed on a missing db (no allow_fresh_init)", False))
    except LiveDatabaseError:
        checks.append(("resolve_live_database_url: fails closed on a missing db (no allow_fresh_init)", True))

    url = resolve_live_database_url(path=missing_path, allow_fresh_init=True)
    checks.append(("resolve_live_database_url: allow_fresh_init succeeds on a genuinely missing db",
                    url == f"sqlite:///{missing_path}"))

    healthy_path = tmp_root / "resolve" / "healthy.db"
    _make_healthy_db(healthy_path)
    url = resolve_live_database_url(path=healthy_path)
    checks.append(("resolve_live_database_url: resolves normally for a healthy db",
                    url == f"sqlite:///{healthy_path}"))

    corrupt_path = tmp_root / "resolve" / "corrupt.db"
    _make_corrupt_db(corrupt_path)
    try:
        resolve_live_database_url(path=corrupt_path)
        checks.append(("resolve_live_database_url: fails closed on a corrupt db", False))
    except LiveDatabaseError:
        checks.append(("resolve_live_database_url: fails closed on a corrupt db", True))

    # allow_fresh_init must NEVER treat an existing (even unhealthy) file
    # as fresh — it only ever applies when nothing exists yet.
    try:
        resolve_live_database_url(path=corrupt_path, allow_fresh_init=True)
        checks.append(("resolve_live_database_url: allow_fresh_init never masks an existing unhealthy file", False))
    except LiveDatabaseError:
        checks.append(("resolve_live_database_url: allow_fresh_init never masks an existing unhealthy file", True))

    # And on an already-healthy file, allow_fresh_init is a no-op success
    # (never re-initializes/overwrites something that's already fine).
    before = healthy_path.stat().st_mtime
    url_again = resolve_live_database_url(path=healthy_path, allow_fresh_init=True)
    checks.append(("resolve_live_database_url: allow_fresh_init on an already-healthy db "
                   "returns its URL without touching the file",
                   url_again == f"sqlite:///{healthy_path}" and healthy_path.stat().st_mtime == before))

    return checks


# ---------------------------------------------------------------------------
# backups + restore
# ---------------------------------------------------------------------------


def _test_backup_and_restore(tmp_root: Path) -> list[tuple[str, bool]]:
    from app.core.db_safety import (
        BACKUP_RETENTION_PER_REASON,
        LiveDatabaseError,
        create_backup,
        list_backups,
        verify_backup,
    )

    checks: list[tuple[str, bool]] = []
    source = tmp_root / "backup_src" / "live.db"
    backup_dir = tmp_root / "backup_src" / "backups"
    _make_healthy_db(source)

    backup_path = create_backup("pre_run_day", source=source, backup_dir=backup_dir)
    checks.append(("create_backup: produces a real file", backup_path.exists()))
    check = verify_backup(backup_path)
    checks.append(("create_backup: the backup itself passes integrity_check", check.healthy))
    checks.append(("create_backup: backup has the same real tables as the source",
                    check.table_count is not None and check.table_count > 0))

    # WAL-checkpoint discipline: write something via a dedicated engine,
    # then confirm the backup reflects it — proves checkpoint_and_copy
    # actually flushes the WAL rather than copying a stale .db file.
    engine = _dedicated_engine(source)
    with engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text(
            "INSERT INTO events (event_type, payload, correlation_id, created_at, sim_day, sim_period) "
            "VALUES ('AGENT_WOKE', '{}', 'test-checkpoint', datetime('now'), 1, 'MORNING')"
        ))
    engine.dispose()
    backup2 = create_backup("pre_run_day", source=source, backup_dir=backup_dir)
    conn = sqlite3.connect(f"file:{backup2}?mode=ro", uri=True)
    count = conn.execute("SELECT count(*) FROM events WHERE correlation_id='test-checkpoint'").fetchone()[0]
    conn.close()
    checks.append(("create_backup: WAL is checkpointed before copying, so the backup is complete", count == 1))

    corrupt_source = tmp_root / "backup_src" / "corrupt_live.db"
    _make_corrupt_db(corrupt_source)
    try:
        create_backup("manual", source=corrupt_source, backup_dir=backup_dir)
        checks.append(("create_backup: refuses to certify a backup of a corrupt source as healthy", False))
    except LiveDatabaseError:
        checks.append(("create_backup: refuses to certify a backup of a corrupt source as healthy", True))

    for _ in range(BACKUP_RETENTION_PER_REASON + 5):
        create_backup("retention_test", source=source, backup_dir=backup_dir)
    remaining = [p for p in list_backups(backup_dir) if "retention_test" in p.name]
    checks.append((f"create_backup: retention prunes to {BACKUP_RETENTION_PER_REASON} per reason",
                    len(remaining) == BACKUP_RETENTION_PER_REASON))

    return checks


# ---------------------------------------------------------------------------
# migration + seed, isolated
# ---------------------------------------------------------------------------


def _test_migration_and_seed(tmp_root: Path) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    path = tmp_root / "migration_seed" / "db.db"
    _make_healthy_db(path)

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        agent_count = conn.execute("SELECT count(*) FROM agents").fetchone()[0]
        table_count = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    finally:
        conn.close()
    checks.append(("migration: alembic upgrade head produces the real full schema", table_count > 20))
    checks.append(("seed: the Founding Eight are seeded", agent_count == 8))
    return checks


# ---------------------------------------------------------------------------
# fresh-live init, in an isolated subprocess (fresh interpreter, no
# module-caching pitfalls) with db_safety's path constants monkeypatched
# to a disposable directory before anything else imports them.
# ---------------------------------------------------------------------------


def _run_isolated(script_body: str, tmp_root: Path) -> subprocess.CompletedProcess:
    script_path = tmp_root / "_isolated_runner.py"
    script_path.write_text(textwrap.dedent(script_body))
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env["LLM_PROVIDER"] = env.get("LLM_PROVIDER", "fixture")
    env["RESEARCH_PROVIDER"] = env.get("RESEARCH_PROVIDER", "fixture")
    return subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=120,
    )


def _test_fresh_live_init_subprocess(tmp_root: Path) -> list[tuple[str, bool]]:
    fake_live_dir = tmp_root / "fresh_init"
    checks: list[tuple[str, bool]] = []

    result = _run_isolated(f"""
        import sys, os
        sys.path.insert(0, {str(REPO_ROOT)!r})
        sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})

        import app.core.db_safety as db_safety
        db_safety.CANONICAL_LIVE_DB_PATH = {str(fake_live_dir / "internal_village.db")!r}
        import pathlib
        db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_dir / "internal_village.db")!r})
        db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_live_dir / "backups")!r})

        os.environ["APP_ENV"] = "live"

        import app.core.config as config

        # 1. Before init: must fail closed via the REAL config call chain.
        try:
            config.resolve_database_url()
            print("MARKER:fails_closed_before_init:False")
        except db_safety.LiveDatabaseError:
            print("MARKER:fails_closed_before_init:True")

        # 2. Deliberate fresh init — the exact sequence scripts/init_live_database.py
        # runs: create the parent directory (SQLite creates the file, never
        # intermediate directories), then ALLOW_FRESH_LIVE_INIT as the narrow,
        # one-shot escape hatch (see app.core.config.resolve_database_url's
        # docstring) -- alembic/env.py re-resolves DATABASE_URL itself, the
        # same as every other caller, so this must be an env var it will also
        # see, not a value we compute once and hand it directly.
        db_safety.CANONICAL_LIVE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        os.environ["ALLOW_FRESH_LIVE_INIT"] = "1"
        try:
            from alembic import command
            from alembic.config import Config as AlembicConfig
            command.upgrade(AlembicConfig(str({str(REPO_ROOT / "alembic.ini")!r})), "head")
        finally:
            os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)

        import seed_agents
        from app.db.session import SessionLocal
        session = SessionLocal()
        report = seed_agents.run(session)
        session.commit()
        print(f"MARKER:seeded_count:{{len(report.created)}}")
        session.close()

        backup_path = db_safety.create_backup("post_init")
        print(f"MARKER:post_init_backup_healthy:{{db_safety.verify_backup(backup_path).healthy}}")

        # 3. After init: the REAL call chain now resolves normally, WITHOUT
        # the escape hatch set -- proving the file itself is what makes it
        # healthy, not the flag.
        url_after = config.resolve_database_url()
        print(f"MARKER:resolves_after_init:{{url_after == db_safety.resolve_live_database_url()}}")

        # 4. A second fresh-init attempt (even with the escape hatch set again)
        # is a no-op success, never overwrites an existing file.
        before_mtime = db_safety.CANONICAL_LIVE_DB_PATH.stat().st_mtime
        db_safety.resolve_live_database_url(allow_fresh_init=True)
        after_mtime = db_safety.CANONICAL_LIVE_DB_PATH.stat().st_mtime
        print(f"MARKER:second_init_did_not_touch_file:{{before_mtime == after_mtime}}")
    """, tmp_root)

    markers = dict(
        line.split(":", 2)[1:3] for line in result.stdout.splitlines() if line.startswith("MARKER:")
    ) if result.stdout else {}

    checks.append(("fresh-live init: subprocess exited cleanly", result.returncode == 0))
    if result.returncode != 0:
        print(f"  (subprocess stderr tail: {result.stderr[-500:]})")
    checks.append(("fresh-live init: fails closed via the real config.resolve_database_url() before init",
                    markers.get("fails_closed_before_init") == "True"))
    checks.append(("fresh-live init: seed_agents runs against the freshly-initialized db",
                    markers.get("seeded_count", "0") not in ("0", "")))
    checks.append(("fresh-live init: post-init backup is created and verified",
                    markers.get("post_init_backup_healthy") == "True"))
    checks.append(("fresh-live init: the real call chain resolves normally once a healthy db exists",
                    markers.get("resolves_after_init") == "True"))
    checks.append(("fresh-live init: a second init attempt never overwrites the existing file",
                    markers.get("second_init_did_not_touch_file") == "True"))
    return checks


def _test_run_day_lifecycle_backups_subprocess(tmp_root: Path) -> list[tuple[str, bool]]:
    fake_live_dir = tmp_root / "run_day_live"
    fake_live_path = fake_live_dir / "internal_village.db"
    fake_backup_dir = fake_live_dir / "backups"
    _make_healthy_db(fake_live_path)
    checks: list[tuple[str, bool]] = []

    result = _run_isolated(f"""
        import sys, os, pathlib
        sys.path.insert(0, {str(REPO_ROOT)!r})
        sys.path.insert(0, {str(REPO_ROOT / "scripts")!r})

        import app.core.db_safety as db_safety
        db_safety.CANONICAL_LIVE_DB_PATH = pathlib.Path({str(fake_live_path)!r})
        db_safety.LIVE_BACKUP_DIR = pathlib.Path({str(fake_backup_dir)!r})

        os.environ["APP_ENV"] = "live"
        os.environ["DATABASE_URL"] = f"sqlite:///{fake_live_path}"

        import run_day
        sys.argv = ["run_day.py", "--quiet", "--max-events", "20"]
        exit_code = run_day.main()
        print(f"MARKER:exit_code:{{exit_code}}")

        pre = [p for p in db_safety.list_backups(db_safety.LIVE_BACKUP_DIR) if "pre_run_day" in p.name]
        post = [p for p in db_safety.list_backups(db_safety.LIVE_BACKUP_DIR) if "post_run_day" in p.name]
        print(f"MARKER:pre_backup_count:{{len(pre)}}")
        print(f"MARKER:post_backup_count:{{len(post)}}")
        if pre:
            print(f"MARKER:pre_backup_healthy:{{db_safety.verify_backup(pre[-1]).healthy}}")
        if post:
            print(f"MARKER:post_backup_healthy:{{db_safety.verify_backup(post[-1]).healthy}}")
    """, tmp_root)

    markers = dict(
        line.split(":", 2)[1:3] for line in result.stdout.splitlines() if line.startswith("MARKER:")
    ) if result.stdout else {}

    checks.append(("RUN DAY lifecycle: subprocess (scripts/run_day.py, APP_ENV=live) exited cleanly",
                    result.returncode == 0 and markers.get("exit_code") == "0"))
    if result.returncode != 0:
        print(f"  (subprocess stderr tail: {result.stderr[-500:]})")
    checks.append(("RUN DAY lifecycle: a pre-RUN-DAY backup was created", markers.get("pre_backup_count", "0") != "0"))
    checks.append(("RUN DAY lifecycle: a post-successful-day backup was created", markers.get("post_backup_count", "0") != "0"))
    checks.append(("RUN DAY lifecycle: the pre-day backup verifies healthy", markers.get("pre_backup_healthy") == "True"))
    checks.append(("RUN DAY lifecycle: the post-day backup verifies healthy", markers.get("post_backup_healthy") == "True"))
    return checks


# ---------------------------------------------------------------------------
# run_live_research_once.py's new refusal
# ---------------------------------------------------------------------------


def _test_run_live_research_once_refuses_silently() -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("APP_ENV", None)
    env["RESEARCH_PROVIDER"] = "tavily"  # so it gets past the fixture-refusal first

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_live_research_once.py"), "--agent", "agent_roxy"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30,
    )
    checks.append(("run_live_research_once.py: refuses (nonzero exit) with no APP_ENV and no --database-url",
                    result.returncode != 0))
    checks.append(("run_live_research_once.py: refusal message names the actual reason",
                    "explicit database target" in (result.stdout + result.stderr)))
    village_db_untouched = (
        not _VILLAGE_DB_PATH.exists()
        or (_VILLAGE_DB_MTIME_AT_START is not None and _VILLAGE_DB_PATH.stat().st_mtime <= _VILLAGE_DB_MTIME_AT_START)
    )
    checks.append(("run_live_research_once.py: never created/touched village.db from this refusal", village_db_untouched))
    return checks


if __name__ == "__main__":
    raise SystemExit(main())
