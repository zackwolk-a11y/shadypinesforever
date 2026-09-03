#!/usr/bin/env python3
"""List or restore a live-database backup.

Restoring is deliberately not the default path of any other script — this
is the one place it happens, and only with ``--restore <path> --confirm``.
The current file at the canonical live path (if any) is itself backed up
first (reason ``pre_restore``), so a restore is never a one-way door.

Usage::

    .venv/bin/python scripts/restore_live_backup.py --list
    .venv/bin/python scripts/restore_live_backup.py --restore data/live/backups/internal_village_pre_run_day_20260101T000000Z.db --confirm
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="list available backups, newest last")
    parser.add_argument("--restore", metavar="PATH", default=None, help="backup file to restore")
    parser.add_argument("--confirm", action="store_true", help="required to actually restore")
    args = parser.parse_args()

    from app.core.db_safety import CANONICAL_LIVE_DB_PATH, check_live_db, create_backup, list_backups, verify_backup

    if args.list or not args.restore:
        backups = list_backups()
        if not backups:
            print("No backups found in data/live/backups/.")
            return 0
        print(f"{len(backups)} backup(s):")
        for b in backups:
            check = verify_backup(b)
            status = "ok" if check.healthy else f"UNHEALTHY: {check.problem}"
            print(f"  {b.name}  ({b.stat().st_size} bytes, {status})")
        if not args.restore:
            return 0

    restore_path = Path(args.restore)
    if not restore_path.exists():
        print(f"{restore_path} does not exist.")
        return 1

    check = verify_backup(restore_path)
    if not check.healthy:
        print(f"Refusing to restore from an unhealthy backup: {check.problem}")
        return 1

    if not args.confirm:
        print(f"Would restore {restore_path} -> {CANONICAL_LIVE_DB_PATH}.")
        print(f"Backup verified healthy ({check.table_count} tables, integrity_check ok).")
        print("Pass --confirm to actually do it.")
        return 0

    current = check_live_db(CANONICAL_LIVE_DB_PATH)
    if current.exists:
        pre_restore_backup = create_backup("pre_restore")
        print(f"Backed up the current file first: {pre_restore_backup}")

    CANONICAL_LIVE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        sibling = Path(f"{CANONICAL_LIVE_DB_PATH}{suffix}")
        if sibling.exists():
            sibling.unlink()
    shutil.copy2(restore_path, CANONICAL_LIVE_DB_PATH)

    post = check_live_db(CANONICAL_LIVE_DB_PATH)
    if not post.healthy:
        print(f"Restore completed but the result failed verification: {post.problem}")
        return 1
    print(f"Restored {restore_path} -> {CANONICAL_LIVE_DB_PATH} ({post.table_count} tables, verified healthy).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
