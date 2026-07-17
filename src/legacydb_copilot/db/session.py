from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from legacydb_copilot.config import Settings


def create_db_engine(database_url: str):
    is_sqlite = database_url.startswith("sqlite")
    connect_args = (
        {"check_same_thread": False, "timeout": 60}
        if is_sqlite
        else {}
    )
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=60000")
            finally:
                cursor.close()
    return engine


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_db_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


settings = Settings.from_env()
SessionLocal = create_session_factory(settings.database_url)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
