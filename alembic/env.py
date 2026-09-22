"""Alembic environment.

The URL comes from ``DATABASE_URL`` (see :mod:`app.db`), never from alembic.ini,
and ``target_metadata`` is the app's own metadata so ``--autogenerate`` sees
every model. ``render_as_batch`` is on because SQLite cannot ALTER in place.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_database_url
from app.core.db_safety import CANONICAL_LIVE_DB_PATH, create_backup
from app.db.base import Base

# Importing the models package is what registers the tables on Base.metadata.
import app.db.models  # noqa: F401  (side-effecting import)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_resolved_url = get_database_url()
config.set_main_option("sqlalchemy.url", _resolved_url)

target_metadata = Base.metadata

# Pre-migration backup: only when this migration is actually about to run
# against the real canonical live database (never against a dev/test URL,
# which every disposable script already isolates itself into), and only
# when there is an existing file to back up — a genuinely fresh live init
# (ALLOW_FRESH_LIVE_INIT, see app.core.config.resolve_database_url) has
# nothing to back up yet, and that is not an error. Built after a real
# incident where a live database ended up empty with no schema at all —
# see app.core.db_safety's module docstring.
if _resolved_url == f"sqlite:///{CANONICAL_LIVE_DB_PATH}" and CANONICAL_LIVE_DB_PATH.exists():
    create_backup("pre_migration")


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
