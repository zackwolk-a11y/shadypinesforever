"""Engine and session factory.

SQLite runs in WAL mode: readers no longer block on the single writer, which
matters once the Founder dashboard reads state while the simulation runner is
mid-event. Writes are still serialized by SQLite, which is why Phase 1 has
exactly one authoritative simulation writer.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url

DATABASE_URL = get_database_url()

# SQLite refuses connections shared across threads unless told otherwise, and
# FastAPI serves requests from a thread pool.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, connection_record) -> None:
    """Foreign keys are off by default in SQLite, and the journal is not WAL."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
