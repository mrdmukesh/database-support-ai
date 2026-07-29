from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def _migration_module():
    path = Path("alembic/versions/0021_investigation_transition_sequence.py")
    spec = importlib.util.spec_from_file_location("transition_sequence_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "investigation_state_transitions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("investigation_id", sa.String(36), nullable=False),
        sa.Column("previous_state", sa.String(80), nullable=False),
        sa.Column("current_state", sa.String(80), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("iteration_number", sa.Integer(), nullable=False),
    )


def _run_upgrade(connection) -> object:
    migration = _migration_module()
    migration.op = Operations(MigrationContext.configure(connection))
    migration.upgrade()
    return migration


def _rows(
    investigation_id: str,
    *,
    timestamp: datetime,
    prefix: str = "a",
) -> list[dict[str, object]]:
    return [
        {
            "id": f"{prefix}0000000-0000-0000-0000-000000000001",
            "investigation_id": investigation_id,
            "previous_state": "",
            "current_state": "INITIALIZATION",
            "transitioned_at": timestamp,
            "iteration_number": 0,
        },
        {
            "id": f"{prefix}0000000-0000-0000-0000-000000000002",
            "investigation_id": investigation_id,
            "previous_state": "INITIALIZATION",
            "current_state": "EVIDENCE_ASSESSMENT",
            "transitioned_at": timestamp,
            "iteration_number": 0,
        },
        {
            "id": f"{prefix}0000000-0000-0000-0000-000000000003",
            "investigation_id": investigation_id,
            "previous_state": "EVIDENCE_ASSESSMENT",
            "current_state": "ROOT_CAUSE_CONFIRMED",
            "transitioned_at": timestamp,
            "iteration_number": 0,
        },
    ]


def test_empty_table_upgrade_adds_non_null_sequence_and_unique_constraint() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    _base_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        _run_upgrade(connection)
        inspector = inspect(connection)
        sequence = next(
            column
            for column in inspector.get_columns("investigation_state_transitions")
            if column["name"] == "sequence_number"
        )
        constraints = inspector.get_unique_constraints(
            "investigation_state_transitions"
        )

        assert sequence["nullable"] is False
        assert any(
            item["name"] == "uq_investigation_state_transition_sequence"
            and item["column_names"] == ["investigation_id", "sequence_number"]
            for item in constraints
        )


def test_ordinary_history_is_backfilled_in_logical_order() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    table = _base_table(metadata)
    metadata.create_all(engine)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    rows = _rows("investigation-1", timestamp=timestamp)
    rows[1]["transitioned_at"] = timestamp + timedelta(seconds=1)
    rows[2]["transitioned_at"] = timestamp + timedelta(seconds=2)

    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
        _run_upgrade(connection)
        result = connection.execute(
            sa.text(
                "SELECT current_state, sequence_number "
                "FROM investigation_state_transitions "
                "ORDER BY sequence_number"
            )
        ).all()

    assert result == [
        ("INITIALIZATION", 1),
        ("EVIDENCE_ASSESSMENT", 2),
        ("ROOT_CAUSE_CONFIRMED", 3),
    ]


def test_same_timestamp_linear_chain_is_backfilled_without_uuid_ordering() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    table = _base_table(metadata)
    metadata.create_all(engine)
    rows = _rows(
        "investigation-tied",
        timestamp=datetime(2026, 2, 2, tzinfo=UTC),
    )
    rows[0]["id"] = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    rows[2]["id"] = "00000000-0000-0000-0000-000000000001"

    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
        _run_upgrade(connection)
        result = connection.execute(
            sa.text(
                "SELECT current_state, sequence_number "
                "FROM investigation_state_transitions "
                "ORDER BY sequence_number"
            )
        ).all()

    assert result == [
        ("INITIALIZATION", 1),
        ("EVIDENCE_ASSESSMENT", 2),
        ("ROOT_CAUSE_CONFIRMED", 3),
    ]


def test_multiple_investigations_each_start_at_one() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    table = _base_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                *_rows(
                    "investigation-a",
                    timestamp=datetime(2026, 3, 3, tzinfo=UTC),
                    prefix="a",
                ),
                *_rows(
                    "investigation-b",
                    timestamp=datetime(2026, 3, 3, tzinfo=UTC),
                    prefix="b",
                ),
            ],
        )
        _run_upgrade(connection)
        result = connection.execute(
            sa.text(
                "SELECT investigation_id, MIN(sequence_number), MAX(sequence_number) "
                "FROM investigation_state_transitions "
                "GROUP BY investigation_id ORDER BY investigation_id"
            )
        ).all()

    assert result == [
        ("investigation-a", 1, 3),
        ("investigation-b", 1, 3),
    ]


def test_ambiguous_history_fails_with_investigation_id() -> None:
    migration = _migration_module()
    timestamp = datetime(2026, 4, 4, tzinfo=UTC)
    rows = _rows("investigation-ambiguous", timestamp=timestamp)
    rows.append(
        {
            "id": "d0000000-0000-0000-0000-000000000004",
            "investigation_id": "investigation-ambiguous",
            "previous_state": "INITIALIZATION",
            "current_state": "GAP_IDENTIFICATION",
            "transitioned_at": timestamp,
            "iteration_number": 0,
        }
    )

    with pytest.raises(RuntimeError, match="investigation-ambiguous"):
        migration._ordered_transition_ids("investigation-ambiguous", rows)


def test_unique_investigation_sequence_is_enforced() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    table = _base_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            _rows("investigation-unique", timestamp=datetime(2026, 5, 5, tzinfo=UTC)),
        )
        _run_upgrade(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO investigation_state_transitions "
                    "(id, investigation_id, previous_state, current_state, "
                    "transitioned_at, iteration_number, sequence_number) "
                    "VALUES ('duplicate', 'investigation-unique', "
                    "'ROOT_CAUSE_CONFIRMED', 'FAILED', "
                    "'2026-05-05 00:00:00', 0, 3)"
                )
            )


def test_downgrade_preserves_rows_and_removes_sequence_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    table = _base_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            _rows(
                "investigation-downgrade",
                timestamp=datetime(2026, 6, 6, tzinfo=UTC),
            ),
        )
        migration = _run_upgrade(connection)
        migration.downgrade()
        inspector = inspect(connection)
        columns = {
            column["name"]
            for column in inspector.get_columns("investigation_state_transitions")
        }
        count = connection.scalar(
            sa.text("SELECT COUNT(*) FROM investigation_state_transitions")
        )

    assert "sequence_number" not in columns
    assert count == 3
