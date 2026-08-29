#!/usr/bin/env python3
"""Print every table and column in the database, for eyeballing against §17.

Reads the live database by default (``DATABASE_URL``, default
``sqlite:///./village.db``), which is what you want after ``alembic upgrade head``.
Pass ``--from-models`` to print the ORM metadata instead, without touching a
database at all.

Usage::

    python scripts/inspect_schema.py
    python scripts/inspect_schema.py --from-models
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect  # noqa: E402

import app.models  # noqa: E402,F401  (registers tables on Base.metadata)
from app.db import Base, engine, get_database_url  # noqa: E402


def _fmt_column(name: str, type_: str, nullable: bool, primary_key: bool) -> str:
    flags = []
    if primary_key:
        flags.append("PK")
    flags.append("NULL" if nullable else "NOT NULL")
    return f"    {name:<24} {type_:<28} {', '.join(flags)}"


def dump_from_database() -> int:
    """Print the schema as it actually exists in the database."""
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    if not table_names:
        print("No tables found. Run `alembic upgrade head` first.")
        return 1

    print(f"Database: {get_database_url()}")
    print(f"{len(table_names)} tables\n")

    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        print(f"{table_name}  ({len(columns)} columns)")
        for column in columns:
            print(
                _fmt_column(
                    column["name"],
                    str(column["type"]),
                    column["nullable"],
                    bool(column.get("primary_key")),
                )
            )
        for fk in inspector.get_foreign_keys(table_name):
            local = ", ".join(fk["constrained_columns"])
            remote = ", ".join(fk["referred_columns"])
            print(f"    -> FK {local} references {fk['referred_table']}({remote})")
        for index in inspector.get_indexes(table_name):
            kind = "UNIQUE INDEX" if index["unique"] else "INDEX"
            print(f"    -> {kind} {index['name']} on {', '.join(index['column_names'])}")
        print()
    return 0


def dump_from_models() -> int:
    """Print the schema the ORM models declare, with no database involved."""
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    print(f"ORM metadata: {len(tables)} tables\n")
    for table in tables:
        print(f"{table.name}  ({len(table.columns)} columns)")
        for column in table.columns:
            print(
                _fmt_column(
                    column.name, str(column.type), column.nullable, column.primary_key
                )
            )
        for fk in table.foreign_keys:
            print(f"    -> FK {fk.parent.name} references {fk.target_fullname}")
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-models",
        action="store_true",
        help="print declared ORM metadata instead of reading the database",
    )
    args = parser.parse_args()
    return dump_from_models() if args.from_models else dump_from_database()


if __name__ == "__main__":
    # Die quietly when piped into `head` rather than dumping a BrokenPipeError.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
