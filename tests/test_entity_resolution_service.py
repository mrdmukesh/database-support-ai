from dataclasses import dataclass

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.services.entity_resolution_service import (
    metadata_with_resolved_tables,
    resolution_metadata_for_schema,
    resolve_entities,
)
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

    def get_table_schema(self, table: str):
        if table == "eval.shipments":
            return {"columns": [{"name": "BusinessKey"}, {"name": "Status"}], "primary_key": [], "foreign_keys": [], "indexes": []}
        raise KeyError(table)


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


def test_camel_case_business_key_is_used_for_sql_server_lookup() -> None:
    table = TableMetadata(
        "eval.shipments",
        ["ShipmentsId", "BusinessKey", "Status"],
        10,
        ["ShipmentsId"],
        [],
        [],
    )
    result = resolve_entities(
        FakeConnector({"BusinessKey AS NVARCHAR(MAX)) = 'SHP-5001'": [
            {"BusinessKey": "SHP-5001", "Status": "Delivered"}
        ]}),
        metadata(table),
        extract_entities("Investigate SHP-5001"),
    )

    assert result.status == "resolved"
    assert result.resolutions[0].matched_value == "SHP-5001"


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


def test_direct_suffix_completion_outranks_prefixed_related_identifiers() -> None:
    result = resolve_entities(
        FakeConnector({"LIKE '%BNK-2026-0002%'": [
            {"record_id": "BNK-2026-0002-A"},
            {"record_id": "MSG-BNK-2026-0002-A"},
            {"record_id": "EX-BNK-2026-0002-A"},
        ]}),
        metadata(business_table()),
        extract_entities("Investigate BNK-2026-0002"),
    )
    assert result.status == "resolved"
    assert result.resolutions[0].matched_value == "BNK-2026-0002-A"
    assert len(result.resolutions[0].candidates) == 3


def test_multiple_direct_suffix_completions_remain_ambiguous() -> None:
    result = resolve_entities(
        FakeConnector({"LIKE '%ORD-42%'": [{"record_id": "ORD-42-A"}, {"record_id": "ORD-42-B"}]}),
        metadata(business_table()),
        extract_entities("Investigate ORD-42"),
    )
    assert result.status == "ambiguous"
    assert result.resolutions[0].matched_value is None


def test_exact_suffixed_identifier_and_base_identifier_remain_distinct() -> None:
    connector = FakeConnector({
        "= 'CLN-17-A'": [{"record_id": "CLN-17-A"}],
        "= 'CLN-17'": [{"record_id": "CLN-17"}],
    })
    suffixed = resolve_entities(connector, metadata(business_table()), extract_entities("Investigate CLN-17-A"))
    base = resolve_entities(connector, metadata(business_table()), extract_entities("Investigate CLN-17"))
    assert suffixed.resolutions[0].matched_value == "CLN-17-A"
    assert base.resolutions[0].matched_value == "CLN-17"


def test_identifier_without_suffix_does_not_acquire_one_without_database_proof() -> None:
    result = resolve_entities(FakeConnector({}), metadata(business_table()), extract_entities("Investigate SHP-88"))
    assert result.status == "not_found"
    assert result.resolutions[0].matched_value is None


def test_active_schema_exact_entity_is_available_outside_ranked_metadata() -> None:
    expanded = resolution_metadata_for_schema(
        FakeConnector({}), metadata(business_table()), ["eval.shipments"]
    )
    assert "eval.shipments" in {table.name for table in expanded.tables}


def test_database_proven_entity_table_is_promoted_for_evidence_planning() -> None:
    connector = FakeConnector({"BusinessKey AS NVARCHAR(MAX)) = 'SHP-004-A'": [{"BusinessKey": "SHP-004-A"}]})
    ranked = metadata(business_table("eval.unrelated"))
    expanded = resolution_metadata_for_schema(connector, ranked, ["eval.shipments"])
    result = resolve_entities(connector, expanded, extract_entities("Investigate SHP-004-A"))
    promoted = metadata_with_resolved_tables(ranked, expanded, result)
    assert promoted.tables[0].name == "eval.shipments"


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
