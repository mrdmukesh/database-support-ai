from types import SimpleNamespace

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import RootCauseSupportStatus
from legacydb_copilot.services.authoritative_source_proof_service import (
    ExactCardinality,
    build_primary_proof_query,
    classify_authoritative_proof,
    infer_dependency_contract,
    reasoning_from_authoritative_proof,
    resolved_identifier_from_metadata,
    should_stop_after_proof,
)
from legacydb_copilot.services.claim_verification_service import (
    build_evidence_registry,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.llm_reasoning_service import _payload_summary
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)


def metadata() -> MetadataSearchResult:
    return MetadataSearchResult(
        tables=[
            TableMetadata(
                "ops.Asset",
                ["AssetId", "AssetCode", "RequiredInput"],
                1.0,
                primary_key=["AssetId"],
                column_types={"AssetId": "int", "AssetCode": "nvarchar"},
            )
        ],
        views=[],
        procedures=[],
        version="test",
        engine_type="sql_server",
    )


def analysis() -> SimpleNamespace:
    return SimpleNamespace(
        name="ops.calculate_output",
        definition=(
            "SELECT CASE WHEN RequiredInput IS NULL THEN NULL "
            "ELSE 1 END AS DerivedOutput FROM ops.Asset"
        ),
        definition_available=True,
        tables_read=["ops.Asset"],
        tables_written=[],
        business_rules=[],
        complexity="low",
        locking_risk="low",
        referenced_columns=["RequiredInput"],
        definition_excerpt="",
    )


def test_dependency_proof_preserves_null_and_verifies_cited_claim() -> None:
    contract = infer_dependency_contract(metadata(), [analysis()], "Why is output unavailable?")
    assert contract is not None
    identifier = resolved_identifier_from_metadata(
        {
            "resolved_table": "ops.Asset",
            "resolved_column": "AssetCode",
            "matched_value": "AST-2042",
        },
        metadata(),
    )
    assert identifier is not None
    query = build_primary_proof_query(identifier, contract)
    assert query.sql == (
        "SELECT AssetId, AssetCode, RequiredInput FROM ops.Asset "
        "WHERE AssetCode = :resolved_identifier"
    )
    assert query.parameters == {"resolved_identifier": "AST-2042"}
    assert query.entity_table == "ops.Asset"
    assert query.identifier_column == "AssetCode"
    assert query.identifier_value == "AST-2042"
    assert query.row_scope == "exact_entity"
    assert "CAST(" not in query.sql and " OR " not in query.sql and "TOP" not in query.sql
    evidence = EvidenceResult(
        query.purpose,
        query.sql,
        [{"AssetId": 8, "AssetCode": "AST-2042", "RequiredInput": None}],
        evidence_id="SQL-1",
        evidence_semantics="null_value",
        supports_claim="The exact entity exists and its required source is explicitly NULL.",
        evidence_relevance="relevant",
        parameters=query.parameters,
        column_types=query.column_types,
        nullable_columns=query.nullable_columns,
        exact_cardinality_result="ENTITY_RESOLVED",
        entity_table=query.entity_table,
        identifier_column=query.identifier_column,
        identifier_value=query.identifier_value,
        row_scope=query.row_scope,
    )
    proof = classify_authoritative_proof(evidence, identifier, contract)
    assert proof.cardinality is ExactCardinality.RESOLVED
    assert proof.deterministic_cause_confirmed
    assert proof.stop_reason == "DETERMINISTIC_REQUIRED_SOURCE_NULL_CONFIRMED"
    assert should_stop_after_proof(proof)
    reasoning = reasoning_from_authoritative_proof(proof)
    claim = reasoning.likely_root_causes[0]
    assert claim.status is RootCauseSupportStatus.VERIFIED
    assert claim.evidence_refs == ["SQL-1"]
    assert reasoning.missing_evidence
    parsed = parse_structured_claim(
        {"statement": claim.conclusion, "evidence_ids": claim.evidence_refs}
    )
    assert parsed is not None
    decision = verify_claim(parsed, build_evidence_registry([evidence]))
    assert decision.verification_result == "VERIFIED"

    correlated = correlate_evidence(
        evidence=[evidence], procedure_analysis=[], documents=[]
    )
    assert correlated[0].finding == "AssetCode = AST-2042; RequiredInput = NULL"
    assert "Row count: 1" in correlated[0].support

    unsupported = parse_structured_claim(
        {
            "statement": "RequiredInput became NULL because an external process corrupted it.",
            "evidence_ids": ["SQL-1"],
        }
    )
    assert unsupported is not None
    rejected = verify_claim(unsupported, build_evidence_registry([evidence]))
    assert rejected.verification_result == "REJECTED"


def test_cardinality_and_non_null_source_continue_investigation() -> None:
    contract = infer_dependency_contract(metadata(), [analysis()], "Check output")
    identifier = resolved_identifier_from_metadata(
        {"resolved_table": "ops.Asset", "resolved_column": "AssetCode", "matched_value": "X"},
        metadata(),
    )
    assert contract is not None and identifier is not None
    for rows, expected in [
        ([], ExactCardinality.NOT_FOUND),
        ([{"RequiredInput": "ready"}], ExactCardinality.RESOLVED),
        ([{"RequiredInput": None}, {"RequiredInput": None}], ExactCardinality.AMBIGUOUS),
    ]:
        evidence = EvidenceResult("proof", "SELECT", rows, evidence_id="SQL-1")
        proof = classify_authoritative_proof(evidence, identifier, contract)
        assert proof.cardinality is expected
        assert not proof.deterministic_cause_confirmed or (
            len(rows) == 1 and rows[0]["RequiredInput"] is None
        )
        if rows == [{"RequiredInput": "ready"}]:
            assert not should_stop_after_proof(proof)


def test_explicit_upstream_origin_request_allows_deeper_investigation() -> None:
    contract = infer_dependency_contract(
        metadata(),
        [analysis()],
        "Why did the required source become missing?",
    )
    identifier = resolved_identifier_from_metadata(
        {"resolved_table": "ops.Asset", "resolved_column": "AssetCode", "matched_value": "X"},
        metadata(),
    )
    assert contract is not None and identifier is not None
    evidence = EvidenceResult(
        "proof",
        "SELECT",
        [{"RequiredInput": None}],
        evidence_id="SQL-1",
    )
    proof = classify_authoritative_proof(evidence, identifier, contract)
    assert proof.deterministic_cause_confirmed
    assert contract.upstream_origin_requested
    assert not should_stop_after_proof(proof)


def test_negated_and_conditional_upstream_guidance_does_not_request_exploration() -> None:
    contract = infer_dependency_contract(
        metadata(),
        [analysis()],
        (
            "Determine why the derived value cannot be calculated. "
            "Do not infer why RequiredSource is NULL unless evidence proves it. "
            "4. If RequiredSource is populated, inspect the calculation. "
            "Trace the related procedure. 5. Report verified findings."
        ),
    )

    assert contract is not None
    assert not contract.upstream_origin_requested
    assert not contract.calculation_validation_requested


def test_payload_summary_distinguishes_null_blank_and_missing() -> None:
    summary = _payload_summary(
        {
            "evidence_refs": {
                "sql": [
                    {
                        "ref": "SQL-1",
                        "purpose": "authoritative proof",
                        "row_count": 1,
                        "columns": ["ExplicitNull", "Blank", "Present"],
                        "sample_rows": [
                            {"ExplicitNull": None, "Blank": "", "Present": "value"}
                        ],
                        "evidence_semantics": "null_value",
                    }
                ]
            }
        }
    )
    facts = summary["sql_evidence"][0]["typed_facts"]
    states = {item["column"]: item["value_state"] for item in facts}
    assert states == {
        "ExplicitNull": "explicit_null",
        "Blank": "blank",
        "Present": "present",
    }
    assert "Missing" not in states
    assert summary["contains_raw_rows"] is False


def test_evidence_focus_reuses_resolved_identifier_instead_of_name_heuristic() -> None:
    focus = build_evidence_focus(
        question="Investigate asset AST-2042",
        intent=InvestigationIntent.MISSING_DATA,
        entities=EntityExtractionResult(
            entities=[], suspected_issue=None, likely_module=None
        ),
        metadata=metadata(),
        evidence=[],
        correlated_evidence=[],
        procedure_analysis=[],
        documents=[],
        resolved_identifier_column="AssetCode",
        resolved_identifier_value="AST-2042",
    )

    assert focus.inferred_business_key == "AssetCode"
    assert focus.selected_business_key_value == "AST-2042"
    assert "resolved typed identifier" in focus.business_key_reason
