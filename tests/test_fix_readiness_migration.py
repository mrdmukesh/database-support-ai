from pathlib import Path


def test_fix_readiness_migration_follows_hypothesis_verification() -> None:
    migration = Path(
        "alembic/versions/0019_fix_readiness_assessment.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0019_fix_readiness"' in migration
    assert 'down_revision = "0018_hypothesis_verify"' in migration
    assert '"fix_readiness_assessments"' in migration
    assert '"criteria_json"' in migration
