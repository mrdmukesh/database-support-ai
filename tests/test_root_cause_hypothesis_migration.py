from pathlib import Path


def test_hypothesis_verification_migration_follows_agentic_loop() -> None:
    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "0018_root_cause_hypothesis_verification.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0018_hypothesis_verify"' in migration
    assert 'down_revision = "0017_execution_trace"' in migration
    assert '"root_cause_hypothesis_verifications"' in migration
    assert '"verification_matrix_json"' in migration
    assert '"visible_in_report"' in migration
