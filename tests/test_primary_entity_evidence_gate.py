from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import primary_entity_found


def test_primary_entity_found_when_entity_exists() -> None:
    evidence = [EvidenceResult("Inspect employee", "SELECT employee_id FROM employees", [{"employee_id": "E001"}])]

    result = primary_entity_found("E001", evidence)

    assert result.status == "PASS"
    assert "found" in result.reason


def test_primary_entity_fails_when_entity_is_not_found() -> None:
    evidence = [EvidenceResult("Inspect employee", "SELECT employee_id FROM employees", [{"employee_id": "E002"}])]

    result = primary_entity_found("E001", evidence)

    assert result.status == "FAIL"
    assert "not found" in result.reason


def test_primary_entity_passes_with_multiple_matches() -> None:
    evidence = [
        EvidenceResult("Inspect employees", "SELECT employee_id FROM employees", [{"employee_id": "E001"}, {"employee_id": "e001"}])
    ]

    result = primary_entity_found("E001", evidence)

    assert result.status == "PASS"
    assert "2 match(es)" in result.reason


def test_primary_entity_fails_when_entity_is_empty() -> None:
    result = primary_entity_found("  ", [])

    assert result.status == "FAIL"
    assert "empty" in result.reason


def test_primary_entity_fails_when_evidence_package_is_missing() -> None:
    result = primary_entity_found("E001", None)

    assert result.status == "FAIL"
    assert "missing" in result.reason
