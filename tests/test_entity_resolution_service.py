from dataclasses import dataclass

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.services.entity_resolution_service import resolve_entities
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


@dataclass
class FakeConnector:
    rows_by_fragment: dict[str, list[dict]]
    blocked_fragment: str = ""
    engine_type: str = "sql_server"

    def execute_read_only_query(self, sql: str, limit: int = 100):
        if self.blocked_fragment and self.blocked_fragment in sql:
            raise PermissionError("blocked by safety policy")
        for fragment, rows in self.rows_by_fragment.items():
            if fragment in sql:
                return rows[:limit]
        return []

    def estimate_table_rows(self, _table: str) -> int:
        return 10


def metadata(*tables: TableMetadata) -> MetadataSearchResult:
    return MetadataSearchResult(list(tables), [], [], "test", engine_type="sql_server")


def business_table(name="business_records") -> TableMetadata:
    return TableMetadata(name, ["record_id", "record_status", "created_at"], 10, ["record_id"], [], [])


def test_exact_entity_match_records_evidence() -> None:
    result = resolve_entities(
        FakeConnector({"= 'ORD-1005'": [{"record_id": "ORD-1005", "record_status": "OPEN"}]}),
        metadata(business_table()),
        extract_entities("Investigate ORD-1005"),
    )

    resolution = result.resolutions[0]
    assert (resolution.extracted_value, resolution.matched_value) == ("ORD-1005", "ORD-1005")
    assert resolution.match_type == "exact"
    assert resolution.confidence == 1.0
    assert resolution.evidence_id.startswith("ENTITY-")
    assert result.can_continue


def test_one_partial_candidate_is_resolved_and_recorded() -> None:
    result = resolve_entities(
        FakeConnector({"LIKE '%RUN-2026%'": [{"record_id": "RUN-2026-07-A", "record_status": "DONE"}]}),
        metadata(business_table()),
        extract_entities("Investigate RUN-2026"),
    )

    resolution = result.resolutions[0]
    assert resolution.match_type == "safe_partial"
    assert resolution.matched_value == "RUN-2026-07-A"
    assert resolution.confidence < 1
    assert resolution.candidates[0].identifier == "RUN-2026-07-A"


def test_multiple_partial_candidates_are_ambiguous() -> None:
    result = resolve_entities(
        FakeConnector({"LIKE '%RUN-2026%'": [
            {"record_id": "RUN-2026-07-A", "record_status": "DONE"},
            {"record_id": "RUN-2026-08-B", "record_status": "OPEN"},
        ]}),
        metadata(business_table()),
        extract_entities("Investigate RUN-2026"),
    )

    assert result.status == "ambiguous"
    assert not result.can_continue
    assert {item.identifier for item in result.resolutions[0].candidates} == {
        "RUN-2026-07-A", "RUN-2026-08-B"
    }


def test_no_matching_entity_blocks_investigation() -> None:
    result = resolve_entities(FakeConnector({}), metadata(business_table()), extract_entities("Investigate EMP-1042"))
    assert result.status == "not_found"
    assert not result.can_continue
    assert result.resolutions[0].matched_value is None


def test_candidate_lookup_blocked_by_safety_policy_is_distinct() -> None:
    result = resolve_entities(
        FakeConnector({}, blocked_fragment="LIKE"), metadata(business_table()), extract_entities("Investigate RUN-2026")
    )
    assert result.status == "blocked"
    assert result.resolutions[0].match_type == "blocked"
    assert "blocked" in result.resolutions[0].reason.lower()


@pytest.mark.parametrize("identifier", ["EMP-1042", "ORD-1005", "SHP-5001", "TRF-3101", "APT-2005"])
def test_resolution_is_generic_across_domain_identifier_shapes(identifier: str) -> None:
    result = resolve_entities(
        FakeConnector({f"= '{identifier}'": [{"record_id": identifier}]}),
        metadata(business_table("domain_records")),
        extract_entities(f"Investigate {identifier}"),
    )
    assert result.status == "resolved"
