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
