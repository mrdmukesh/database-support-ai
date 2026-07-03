import pytest

from legacydb_copilot.services.benchmark_runner import (
    BenchmarkCaseResult,
    assert_demo_database,
    load_expected_issues,
    _metrics,
)


class FakeConnector:
    def execute_read_only_query(self, sql: str, limit: int = 1000):
        if "FROM ai_expected_issues" in sql:
            return [
                {
                    "issue_id": "DEMO-DUP-001",
                    "question": "Appointment APT-2005 created two active lab orders.",
                    "business_key": "APT-2005",
                    "affected_object": "lab_orders",
                    "expected_root_cause": "Retry procedure lacks idempotency.",
                    "expected_procedure": "sp_retry_failed_lab_orders",
                    "expected_evidence": "Two active lab orders exist.",
                    "issue_type": "duplicate",
                }
            ]
        return []


def test_benchmark_runner_refuses_customer_database_names() -> None:
    with pytest.raises(ValueError, match="demo-only"):
        assert_demo_database("mysql://user:pass@example.com:3306/customer_prod")


def test_benchmark_runner_allows_demo_database_names() -> None:
    assert_demo_database("mysql://user:pass@example.com:3306/clinic_ops_ai_demo")


def test_load_expected_issues_from_ground_truth_table() -> None:
    issues = load_expected_issues(FakeConnector())

    assert len(issues) == 1
    assert issues[0].issue_id == "DEMO-DUP-001"
    assert issues[0].affected_object == "lab_orders"


def test_benchmark_metrics_are_calculated() -> None:
    metrics = _metrics(
        [
            BenchmarkCaseResult(
                issue_id="1",
                question="q",
                affected_object_match=True,
                procedure_match=True,
                evidence_verified=True,
                root_cause_score=0.8,
                verification_score=1.0,
                overall_score=0.95,
                notes=[],
            ),
            BenchmarkCaseResult(
                issue_id="2",
                question="q",
                affected_object_match=False,
                procedure_match=True,
                evidence_verified=False,
                root_cause_score=0.2,
                verification_score=0.5,
                overall_score=0.45,
                notes=[],
            ),
        ]
    )

    assert metrics["case_count"] == 2.0
    assert metrics["affected_object_accuracy"] == 0.5
    assert metrics["procedure_accuracy"] == 1.0
    assert metrics["evidence_verification_rate"] == 0.5
