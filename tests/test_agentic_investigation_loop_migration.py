from pathlib import Path


def test_agentic_loop_migration_follows_safe_planner() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0016_agentic_investigation_loop.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0016_agentic_loop"' in migration
    assert 'down_revision = "0015_safe_planner"' in migration
    assert '"investigation_agentic_steps"' in migration
    assert '"budget_json"' in migration
    assert '"evidence_json"' in migration
