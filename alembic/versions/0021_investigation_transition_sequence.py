"""Add deterministic per-investigation transition sequencing.

Revision ID: 0021
Revises: 0020_merge_heads
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020_merge_heads"
branch_labels = None
depends_on = None

TABLE_NAME = "investigation_state_transitions"
CONSTRAINT_NAME = "uq_investigation_state_transition_sequence"


def _ordered_transition_ids(
    investigation_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    if not rows:
        return []
    remaining = {str(row["id"]): row for row in rows}
    roots = [row for row in rows if not str(row["previous_state"] or "")]
    if len(roots) != 1:
        raise RuntimeError(
            "Ambiguous investigation transition history: "
            f"{investigation_id} has {len(roots)} initialization roots"
        )

    ordered: list[str] = []
    current = roots[0]
    while current is not None:
        current_id = str(current["id"])
        ordered.append(current_id)
        remaining.pop(current_id)
        if not remaining:
            break

        current_state = str(current["current_state"])
        current_iteration = int(current["iteration_number"] or 0)
        candidates = [
            row
            for row in remaining.values()
            if str(row["previous_state"] or "") == current_state
            and (
                int(row["iteration_number"] or 0) == current_iteration
                or (
                    current_state == "STOP_EVALUATION"
                    and int(row["iteration_number"] or 0) == current_iteration + 1
                )
            )
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                "Ambiguous investigation transition history: "
                f"{investigation_id} has {len(candidates)} successors after "
                f"{current_state}"
            )
        successor = candidates[0]
        if (
            current["transitioned_at"] is not None
            and successor["transitioned_at"] is not None
            and successor["transitioned_at"] < current["transitioned_at"]
        ):
            raise RuntimeError(
                "Ambiguous investigation transition history: "
                f"{investigation_id} has a successor timestamp before its predecessor"
            )
        current = successor
    return ordered


def _backfill_sequences(connection) -> None:
    transitions = sa.table(
        TABLE_NAME,
        sa.column("id", sa.String(36)),
        sa.column("investigation_id", sa.String(36)),
        sa.column("previous_state", sa.String(80)),
        sa.column("current_state", sa.String(80)),
        sa.column("transitioned_at", sa.DateTime(timezone=True)),
        sa.column("iteration_number", sa.Integer()),
        sa.column("sequence_number", sa.BigInteger()),
    )
    rows = connection.execute(
        sa.select(
            transitions.c.id,
            transitions.c.investigation_id,
            transitions.c.previous_state,
            transitions.c.current_state,
            transitions.c.transitioned_at,
            transitions.c.iteration_number,
        )
    ).mappings()
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["investigation_id"])].append(row)

    failures: list[str] = []
    ordered_by_investigation: dict[str, list[str]] = {}
    for investigation_id, history in grouped.items():
        try:
            ordered_by_investigation[investigation_id] = _ordered_transition_ids(
                investigation_id,
                history,
            )
        except RuntimeError:
            failures.append(investigation_id)
    if failures:
        raise RuntimeError(
            "Ambiguous investigation transition histories prevent sequence backfill: "
            + ", ".join(sorted(failures))
        )

    for ordered_ids in ordered_by_investigation.values():
        for sequence_number, transition_id in enumerate(ordered_ids, start=1):
            connection.execute(
                sa.update(transitions)
                .where(transitions.c.id == transition_id)
                .values(sequence_number=sequence_number)
            )

    validation = connection.execute(
        sa.select(
            transitions.c.investigation_id,
            sa.func.count().label("row_count"),
            sa.func.count(transitions.c.sequence_number).label("sequenced_count"),
            sa.func.count(sa.distinct(transitions.c.sequence_number)).label(
                "distinct_count"
            ),
            sa.func.min(transitions.c.sequence_number).label("minimum_sequence"),
            sa.func.max(transitions.c.sequence_number).label("maximum_sequence"),
        ).group_by(transitions.c.investigation_id)
    ).mappings()
    invalid = [
        str(row["investigation_id"])
        for row in validation
        if row["row_count"] != row["sequenced_count"]
        or row["row_count"] != row["distinct_count"]
        or row["minimum_sequence"] != 1
        or row["maximum_sequence"] != row["row_count"]
    ]
    if invalid:
        raise RuntimeError(
            "Invalid investigation transition sequence backfill: "
            + ", ".join(sorted(invalid))
        )


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
    )
    _backfill_sequences(op.get_bind())
    with op.batch_alter_table(TABLE_NAME) as batch:
        batch.alter_column(
            "sequence_number",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        batch.create_unique_constraint(
            CONSTRAINT_NAME,
            ["investigation_id", "sequence_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE_NAME) as batch:
        batch.drop_constraint(CONSTRAINT_NAME, type_="unique")
        batch.drop_column("sequence_number")
