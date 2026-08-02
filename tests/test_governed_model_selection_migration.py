from pathlib import Path


def test_governed_model_selection_migration_is_single_chain_and_reversible():
    source = Path("alembic/versions/0024_governed_model_selection.py").read_text()
    assert 'revision = "0024"' in source
    assert 'down_revision = "0023"' in source
    for table in (
        "llm_model_catalog",
        "llm_model_policy",
        "llm_model_role_entitlement",
        "llm_model_user_entitlement",
        "llm_model_workspace_entitlement",
        "llm_model_selection_audit",
    ):
        assert f'"{table}"' in source
        assert f'op.drop_table("{table}")' in source
    assert "api_key" not in source
