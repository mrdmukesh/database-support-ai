import pytest

from legacydb_copilot.services.evidence_gate_service import (
    EvidenceGateCheckResult,
    combine_evidence_gate_checks,
)


def check(name: str, passed: bool) -> EvidenceGateCheckResult:
    return EvidenceGateCheckResult(
        check=name,
        status="PASS" if passed else "FAIL",
        reason=f"{name} {'passed' if passed else 'failed'}.",
    )


@pytest.mark.parametrize(
    ("entity_passed", "object_passed", "expected_status", "expected_passed", "expected_failed"),
    [
        (True, True, "PASS", ["primary_entity_found", "relevant_object_inspected"], []),
        (True, False, "PARTIAL", ["primary_entity_found"], ["relevant_object_inspected"]),
        (False, True, "PARTIAL", ["relevant_object_inspected"], ["primary_entity_found"]),
        (False, False, "FAIL", [], ["primary_entity_found", "relevant_object_inspected"]),
    ],
)
def test_combines_two_evidence_gate_checks(
    entity_passed: bool,
    object_passed: bool,
    expected_status: str,
    expected_passed: list[str],
    expected_failed: list[str],
) -> None:
    result = combine_evidence_gate_checks(
        check("primary_entity_found", entity_passed),
        check("relevant_object_inspected", object_passed),
    )

    assert result.status == expected_status
    assert result.passed_checks == expected_passed
    assert result.failed_checks == expected_failed
    assert len(result.reasons) == 2
