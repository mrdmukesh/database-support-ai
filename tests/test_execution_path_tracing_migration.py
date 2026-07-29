from pathlib import Path


def test_execution_path_migration_follows_agentic_loop() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0017_execution_path_tracing.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0017_execution_trace"' in migration
    assert 'down_revision = "0016_agentic_loop"' in migration
    assert '"execution_path_traces"' in migration
    assert '"nodes_json"' in migration
    assert '"edges_json"' in migration
