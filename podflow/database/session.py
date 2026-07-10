"""
SQLAlchemy engine and session factory.

Uses the database URL from :mod:`podflow.config.settings`.
"""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from podflow.config.settings import settings
from podflow.database.models import Base

engine_args: dict[str, Any] = {"echo": False}

if settings.db_backend == "sqlite":
    engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_args)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def init_db() -> None:
    """Create all tables defined in the ORM models if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Yield a database session, ensuring it is closed after use.

    Intended as a FastAPI-style dependency or context-managed generator::

        with next(get_db()) as session:
            ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
