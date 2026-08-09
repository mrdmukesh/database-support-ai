import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities


def business_identifiers(question: str) -> set[str]:
    return {
        entity.value
        for entity in extract_entities(question).entities
        if entity.entity_type == "business_identifier"
    }


def test_preserves_complete_multi_segment_business_identifiers() -> None:
    identifiers = business_identifiers(
        "Investigate RUN-2026-07-A, EMP-1042, ORD-1005, SHP-5001 and TRF-3101."
    )

    assert identifiers == {
        "RUN-2026-07-A",
        "EMP-1042",
        "ORD-1005",
        "SHP-5001",
        "TRF-3101",
    }
    assert "RUN-2026" not in identifiers


def test_preserves_supported_identifier_separators_and_case() -> None:
    identifiers = business_identifiers(
        "Compare Batch_2026_07_A, Case/2026/07/B, mixed-Case-42-x and JOB 2026 07 C."
    )

    assert {
        "Batch_2026_07_A",
        "Case/2026/07/B",
        "mixed-Case-42-x",
        "JOB 2026 07 C",
    } <= identifiers


def test_extracts_every_identifier_candidate_from_question() -> None:
    identifiers = business_identifiers(
        "Order ORD-1005 created shipment SHP-5001 after transfer TRF-3101."
    )

    assert identifiers == {"ORD-1005", "SHP-5001", "TRF-3101"}


@pytest.mark.parametrize(
    ("question", "field", "value", "value_type"),
    [
        ("Why is salary NULL for EmployeeId 7?", "EmployeeId", 7, "integer"),
        ("Why is total missing for OrderId 1?", "OrderId", 1, "integer"),
        ("Investigate FacilityId: 5", "FacilityId", 5, "integer"),
        ("Investigate ShipmentNumber ABC123", "ShipmentNumber", "ABC123", "string"),
        ("Investigate InvoiceNumber INV-1001", "InvoiceNumber", "INV-1001", "string"),
    ],
)
def test_extracts_typed_single_field_value_identifiers(
    question: str, field: str, value: object, value_type: str
) -> None:
    identifier = extract_entities(question).structured_identifiers[0]

    assert identifier.field_name == field
    assert identifier.value == value
    assert identifier.value_type == value_type
    assert identifier.confidence >= 0.95


def test_extracts_qualified_field_value_identifier() -> None:
    identifier = extract_entities(
        "Why is value missing for audit.SomeTable.SomeId = 2?"
    ).structured_identifiers[0]

    assert identifier.schema_name == "audit"
    assert identifier.table_name == "SomeTable"
    assert identifier.field_name == "SomeId"
    assert identifier.qualified_field_name == "audit.SomeTable.SomeId"
    assert identifier.value == 2


def test_null_is_a_symptom_not_a_business_identifier() -> None:
    extracted = extract_entities("Why is amount NULL for InvoiceId 9?")

    assert extracted.symptoms == ["NULL"]
    assert all(identifier.value != "NULL" for identifier in extracted.structured_identifiers)
