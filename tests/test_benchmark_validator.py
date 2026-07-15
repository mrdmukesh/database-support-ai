from dataclasses import replace

from evaluation.framework.benchmark_validator import validate_benchmark
from tests.test_evaluation_foundation import scenario


def test_validator_detects_duplicate_ids_and_questions(tmp_path):
    valid = scenario(
        business_description="A payment support incident.",
        expected_relationships=("payments -> messages",),
        unsafe_recommendations=("edit production rows",),
        expected_citations=("EV-1",),
        tags=("payment",),
    )
    for name in ("baseline.sql", "setup.sql", "verify.sql", "cleanup.sql"):
        (tmp_path / name).write_text("SELECT 1;", encoding="utf-8")
    issues = validate_benchmark([valid, replace(valid)], tmp_path, enforce_distribution=False)
    assert {issue.code for issue in issues} >= {"duplicate_id", "duplicate_question"}


def test_validator_rejects_unsafe_fixture_sql(tmp_path):
    item = scenario(
        scenario_id="payroll-benchmark-999",
        business_description="A payment support incident.",
        expected_relationships=("payments -> messages",),
        unsafe_recommendations=("edit production rows",),
        expected_citations=("EV-1",),
        tags=("payment",),
    )
    for name in ("baseline.sql", "verify.sql", "cleanup.sql"):
        (tmp_path / name).write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "setup.sql").write_text("DROP TABLE payments;", encoding="utf-8")
    assert "unsafe_sql" in {issue.code for issue in validate_benchmark([item], tmp_path, enforce_distribution=False)}
