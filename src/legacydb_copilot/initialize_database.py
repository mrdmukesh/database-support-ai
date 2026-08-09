from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from legacydb_copilot.db import models  # noqa: F401
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import create_db_engine, settings


def initialize_database() -> str:
    """Initialize a fresh database or upgrade an established Alembic database."""
    engine = create_db_engine(settings.database_url)
    config = Config("alembic.ini")
    try:
        if not inspect(engine).has_table("alembic_version"):
            Base.metadata.create_all(bind=engine)
            command.stamp(config, "head")
            return "initialized"
        command.upgrade(config, "head")
        return "upgraded"
    finally:
        engine.dispose()


if __name__ == "__main__":
    initialize_database()
