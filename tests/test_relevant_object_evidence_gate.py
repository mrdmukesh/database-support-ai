from legacydb_copilot.services.evidence_gate_service import relevant_object_inspected


def test_relevant_table_inspected() -> None:
    result = relevant_object_inspected([{"object_type": "table", "name": "employees"}])

    assert result.status == "PASS"
    assert result.inspected_objects == ["employees"]


def test_relevant_stored_procedure_inspected() -> None:
    result = relevant_object_inspected([{"object_type": "stored_procedure", "name": "hr.refresh_employees"}])

    assert result.status == "PASS"
    assert result.inspected_objects == ["hr.refresh_employees"]


def test_multiple_relevant_objects_inspected() -> None:
    result = relevant_object_inspected(
        [
            {"object_type": "table", "name": "employees"},
            {"object_type": "view", "name": "active_employees"},
            {"object_type": "job", "name": "employee_sync"},
        ]
    )

    assert result.status == "PASS"
    assert result.inspected_objects == ["employees", "active_employees", "employee_sync"]


def test_no_relevant_object_inspected() -> None:
    result = relevant_object_inspected([])

    assert result.status == "FAIL"
    assert result.inspected_objects == []
    assert result.reason == "No relevant object was inspected."


def test_invalid_object_reference_fails() -> None:
    result = relevant_object_inspected([{"object_type": "queue", "name": "invalid name!"}])

    assert result.status == "FAIL"
    assert result.inspected_objects == []
    assert "invalid" in result.reason
