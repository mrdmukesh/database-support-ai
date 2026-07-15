from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, inspect

from legacydb_copilot.db.models import EvaluationJobModel


def _migration_module():
    path = Path("alembic/versions/0007_evaluation_jobs.py")
    spec = importlib.util.spec_from_file_location("evaluation_jobs_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adopts_existing_evaluation_jobs_table(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        EvaluationJobModel.__table__.create(connection)
        migration = _migration_module()
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        migration.upgrade()

        assert "evaluation_jobs" in inspect(connection).get_table_names()


def test_downgrade_is_safe_when_table_is_absent(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        migration = _migration_module()
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

        migration.downgrade()

        assert "evaluation_jobs" not in inspect(connection).get_table_names()
