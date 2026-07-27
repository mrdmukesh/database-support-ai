from pathlib import Path


def test_state_machine_migration_contains_required_ledger_fields() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0013_investigation_state_machine.py"
    ).read_text(encoding="utf-8")

    for field in (
        "investigation_id",
        "previous_state",
        "current_state",
        "transitioned_at",
        "reason",
        "iteration_number",
    ):
        assert field in migration
