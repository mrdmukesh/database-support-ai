from pathlib import Path


def test_connection_scan_policy_migration_defaults_existing_connections_to_production() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0010_connection_scan_policy.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "0009_llm_audit_outcomes"' in migration
    assert '"environment_type"' in migration
    assert 'server_default="production"' in migration
    assert '"max_scan_rows"' in migration
    assert 'server_default="500"' in migration
    assert "ck_database_connections_environment_type" in migration
    assert "ck_database_connections_max_scan_rows" in migration
