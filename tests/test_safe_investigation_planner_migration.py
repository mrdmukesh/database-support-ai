from pathlib import Path


def test_safe_planner_migration_follows_evidence_gap_migration() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0015_safe_investigation_planner.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0015_safe_planner"' in migration
    assert 'down_revision = "0014_evidence_gaps"' in migration
    assert '"investigation_planner_selections"' in migration
    assert '"selection_reason"' in migration
    assert '"expected_information_gain"' in migration
