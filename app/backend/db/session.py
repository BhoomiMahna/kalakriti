"""SQLAlchemy engine, session factory, and Base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# For a file-backed SQLite URL, make sure the parent directory exists (e.g. a
# mounted persistent volume like /data) before SQLite tries to open the file.
if settings.database_url.startswith("sqlite:///"):
    from pathlib import Path as _Path

    _db_path = settings.database_url.replace("sqlite:///", "", 1)
    if _db_path and _db_path != ":memory:":
        _Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models so they register on Base.metadata."""
    import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)
