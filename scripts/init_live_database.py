#!/usr/bin/env python3
"""The ONLY way a live Village database is ever created from nothing.

Refuses to run without ``--confirm``. Refuses if a file already exists at
the canonical live path (``data/live/internal_village.db``) — healthy or
not: overwriting an existing file, even a broken one, is a human decision
(restore a backup, or deliberately move/delete the bad file first), never
something this script does on your behalf. Takes an immediate post-init
backup so "freshly initialized" is itself a recoverable state from the
first moment it exists.

Built after a real data-loss incident where the live database silently
ended up replaced by an empty, schema-less file with no warning anywhere in
the chain — see app.core.db_safety's module docstring for the full forensic
signature. This script is the one deliberate, auditable place initialization
is allowed to happen; every other code path in this repo that could resolve
to the live database now fails closed instead.

Usage::

    .venv/bin/python scripts/init_live_database.py --confirm
    .venv/bin/python scripts/init_live_database.py --confirm --seed
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--confirm", action="store_true", help="required — this is not a dry run")
    parser.add_argument("--seed", action="store_true", help="also seed the Founding Eight agents")
    args = parser.parse_args()

    if not args.confirm:
        print("Refusing without --confirm. This deliberately initializes a brand-new")
        print("live Village database — pass --confirm if that's really what you mean.")
        return 1

    os.environ["APP_ENV"] = "live"

    from app.core.db_safety import CANONICAL_LIVE_DB_PATH, check_live_db, create_backup

    existing = check_live_db(CANONICAL_LIVE_DB_PATH)
    if existing.exists:
        print(f"{CANONICAL_LIVE_DB_PATH} already exists — refusing to initialize over it.")
        print(f"  size: {existing.size_bytes} bytes, healthy: {existing.healthy}"
              + (f", problem: {existing.problem}" if existing.problem else ""))
        print("If you really mean to start fresh: move or delete that file yourself first,")
        print("or restore a known-good backup from data/live/backups/.")
        return 1

    print(f"Initializing: {CANONICAL_LIVE_DB_PATH}")
    CANONICAL_LIVE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Narrow, one-shot escape hatch (see app.core.config.resolve_database_url's
    # docstring) — set only for the lifetime of this process, so alembic/env.py's
    # own DATABASE_URL resolution (re-run independently, like every other
    # caller) can create the schema against a genuinely-missing live path
    # without a second, parallel resolution path.
    os.environ["ALLOW_FRESH_LIVE_INIT"] = "1"
    try:
        from alembic import command
        from alembic.config import Config

        command.upgrade(Config(str(REPO_ROOT / "alembic.ini")), "head")
    finally:
        os.environ.pop("ALLOW_FRESH_LIVE_INIT", None)
    print("Schema migrated to head.")

    if args.seed:
        import seed_agents

        from app.db.session import SessionLocal

        session = SessionLocal()
        try:
            report = seed_agents.run(session)
            session.commit()
            print(f"Seeded: {len(report.created)} rows created.")
        finally:
            session.close()

    backup_path = create_backup("post_init")
    print(f"Post-init backup: {backup_path}")
    print("\nLive database ready. Launch with:")
    print("  APP_ENV=live .venv/bin/uvicorn app.main:app --reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
