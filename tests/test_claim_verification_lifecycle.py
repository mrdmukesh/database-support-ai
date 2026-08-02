from __future__ import annotations

import json

import pytest

from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.claim_verification_service import (
    EvidenceReference,
    build_evidence_registry,
    normalize_evidence_id,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.llm_reasoning_service import (
    _build_llm_payload_unmasked,
    _merge_llm_reasoning,
)


def reference(
    evidence_id: str = "SQL-1",
    *,
    rows=({"EmployeeNumber": "EMP-1001", "PayrollStatus": "Ready"},),
    row_count: int | None = None,
    zero: bool = False,
    truncated: bool = False,
    evidence_semantics: str = "",
    entity_table: str = "dbo.Employee",
    identifier_column: str = "BusinessKey",
    identifier_value: str = "EMP-1001",
    row_scope: str = "exact_entity",
) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=evidence_id,
        type="SQL_RESULT",
        title="Employee profile for EMP-1001",
        sql="SELECT EmployeeNumber, PayrollStatus FROM Employee",
        columns=("EmployeeNumber", "PayrollStatus"),
        rows=tuple(rows),
        row_count=len(rows) if row_count is None else row_count,
        zero_row_result=zero,
        truncated=truncated,
        evidence_semantics=evidence_semantics,
        entity_table=entity_table,
        identifier_column=identifier_column,
        identifier_value=identifier_value,
        row_scope=row_scope,
    )


def claim(value: dict):
    parsed = parse_structured_claim(value)
    assert parsed is not None
    return parsed


def base_reasoning() -> ReasoningResult:
    return ReasoningResult(
        summary="Deterministic summary.",
        likely_root_causes=[],
        supporting_evidence=[],
        missing_evidence=[],
        recommended_fix=[],
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=[],
    )


def evidence(evidence_id: str, rows: list[dict]) -> EvidenceResult:
    return EvidenceResult(
        "Employee profile for EMP-1001",
        "SELECT EmployeeNumber, PayrollStatus FROM Employee",
        rows,
        evidence_id=evidence_id,
        execution_status="succeeded",
        evidence_semantics="positive_rows",
    )


def test_valid_claim_with_one_or_multiple_evidence_ids_passes() -> None:
    second = EvidenceReference(
        **{
            **reference("SQL-2").__dict__,
            "title": "Employment status",
            "rows": ({"EmployeeNumber": "EMP-1001", "EmploymentStatus": "Active"},),
            "columns": ("EmployeeNumber", "EmploymentStatus"),
        }
    )
    one = verify_claim(
        claim({"statement": "EMP-1001 has PayrollStatus Ready.", "evidence_ids": ["SQL-1"]}),
        [reference()],
    )
    multiple = verify_claim(
        claim(
            {
                "statement": "EMP-1001 is Ready and Active.",
                "evidence_ids": ["SQL-1", "SQL-2"],
            }
        ),
        [reference(), second],
    )
    assert one.verification_result == "VERIFIED"
    assert multiple.verification_result == "VERIFIED"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ({"statement": "EMP-1001 is Ready.", "evidence_ids": ["SQL-999"]}, "EVIDENCE_ID_NOT_FOUND"),
        ({"statement": "EMP-1001 is Ready."}, "MISSING_CITATIONS"),
    ],
)
def test_missing_or_nonexistent_citations_fail_precisely(raw: dict, code: str) -> None:
    result = verify_claim(claim(raw), [reference()])
    assert result.verification_result == "REJECTED"
    assert result.rejection_code == code


def test_evidence_gap_without_factual_claim_is_allowed() -> None:
    result = verify_claim(
        claim(
            {
                "claim_type": "EVIDENCE_GAP",
                "evidence_gap": "No deduction query was available.",
                "evidence_ids": ["SQL-1"],
            }
        ),
        [reference()],
    )
    assert result.verification_result == "EVIDENCE_GAP"


def test_contradictory_value_claim_fails() -> None:
    result = verify_claim(
        claim(
            {
                "statement": "EMP-1001 has PayrollStatus Blocked.",
                "evidence_ids": ["SQL-1"],
            }
        ),
        [reference()],
    )
    assert result.verification_result == "REJECTED"
    assert result.rejection_code == "CONTRADICTORY_EVIDENCE"


def test_other_entity_and_broad_rows_do_not_contradict_scoped_null_claim() -> None:
    scoped = reference(
        rows=({"BusinessKey": "EMP-1001", "DateOfBirth": None},),
    )
    other_entity = reference(
        "SQL-2",
        rows=({"BusinessKey": "EMP-1002", "DateOfBirth": "1990-01-01"},),
        identifier_value="EMP-1002",
    )
    broad_department = reference(
        "SQL-3",
        rows=(
            {"BusinessKey": "EMP-1002", "DateOfBirth": "1990-01-01"},
            {"BusinessKey": "EMP-1003", "DateOfBirth": "1988-02-02"},
        ),
        identifier_column="DepartmentId",
        identifier_value="2",
        row_scope="broad",
    )
    result = verify_claim(
        claim(
            {
                "statement": "Employee EMP-1001 has DateOfBirth NULL.",
                "evidence_ids": ["SQL-1"],
            }
        ),
        [scoped, other_entity, broad_department],
    )
    assert result.verification_result == "VERIFIED"
    assert result.contradictory_evidence_ids == ()

    cited_broad = verify_claim(
        claim(
            {
                "statement": "Employee EMP-1001 has DateOfBirth NULL.",
                "evidence_ids": ["SQL-1", "SQL-3"],
            }
        ),
        [scoped, broad_department],
    )
    assert cited_broad.verification_result == "VERIFIED"


def test_same_entity_conflicting_value_rejects_scoped_null_claim() -> None:
    scoped_null = reference(
        rows=({"BusinessKey": "EMP-1001", "DateOfBirth": None},),
    )
    same_entity_conflict = reference(
        "SQL-2",
        rows=({"BusinessKey": "EMP-1001", "DateOfBirth": "1990-01-01"},),
    )
    result = verify_claim(
        claim(
            {
                "statement": "Employee EMP-1001 has DateOfBirth NULL.",
                "evidence_ids": ["SQL-1"],
            }
        ),
        [scoped_null, same_entity_conflict],
    )
    assert result.verification_result == "REJECTED"
    assert result.rejection_code == "CONTRADICTORY_EVIDENCE"
    assert result.contradictory_evidence_ids == ("SQL-2",)


def test_second_entity_type_uses_the_same_scoped_null_rules() -> None:
    source = reference(
        rows=({"AssetCode": "AST-2042", "RequiredInput": None},),
        entity_table="ops.Asset",
        identifier_column="AssetCode",
        identifier_value="AST-2042",
    )
    sibling = reference(
        "SQL-2",
        rows=({"AssetCode": "AST-2043", "RequiredInput": "ready"},),
        entity_table="ops.Asset",
        identifier_column="AssetCode",
        identifier_value="AST-2043",
    )
    result = verify_claim(
        claim(
            {
                "statement": "Asset AST-2042 has RequiredInput NULL.",
                "evidence_ids": ["SQL-1"],
            }
        ),
        [source, sibling],
    )
    assert result.verification_result == "VERIFIED"


def test_row_count_only_cannot_verify_value_but_zero_rows_verify_tested_absence() -> None:
    count_only = reference(rows=(), row_count=1)
    assert verify_claim(
        claim({"statement": "PayrollStatus is Ready.", "evidence_ids": ["SQL-1"]}),
        [count_only],
    ).rejection_code == "INSUFFICIENT_EVIDENCE_CONTENT"
    zero = reference(
        rows=(),
        row_count=0,
        zero=True,
        evidence_semantics="verified_absence",
    )
    assert verify_claim(
        claim({"statement": "No matching deduction record was found.", "evidence_ids": ["SQL-1"]}),
        [zero],
    ).verification_result == "VERIFIED"


def test_truncated_evidence_cannot_be_cited() -> None:
    result = verify_claim(
        claim({"statement": "EMP-1001 is Ready.", "evidence_ids": ["SQL-1"]}),
        [reference(truncated=True)],
    )
    assert result.rejection_code == "EVIDENCE_NOT_IN_PROMPT"


def test_alias_fields_and_integer_ids_are_preserved_or_normalized() -> None:
    parsed = claim({"conclusion": "EMP-1001 is Ready.", "citations": ["sql_001"]})
    assert parsed.evidence_ids == ("SQL-1",)
    assert normalize_evidence_id(1) == "1"
    encoded = json.loads(json.dumps(parsed.raw_claim))
    assert parse_structured_claim(encoded).evidence_ids == ("SQL-1",)


def test_provider_parser_preserves_evidence_ids_and_partial_claims() -> None:
    records = [evidence("SQL-1", [{"EmployeeNumber": "EMP-1001", "PayrollStatus": "Ready"}])]
    trace: dict = {}
    result = _merge_llm_reasoning(
        base_reasoning(),
        {
            "claims": [
                {
                    "claim_id": "CL-001",
                    "statement": "EMP-1001 has PayrollStatus Ready.",
                    "evidence_ids": ["SQL-1"],
                },
                {
                    "claim_id": "CL-002",
                    "statement": "EMP-1001 has PayrollStatus Blocked.",
                    "evidence_ids": ["SQL-1"],
                },
            ]
        },
        evidence_records=records,
        debug_trace=trace,
    )
    assert [item.conclusion for item in result.likely_root_causes] == [
        "EMP-1001 has PayrollStatus Ready."
    ]
    assert trace["invocation_status"] == "completed_partial_verification"
    assert trace["claims_verified"] == 1
    assert trace["claims_rejected"] == 1


def test_evidence_id_survives_registry_and_prompt_without_renumbering() -> None:
    records = [
        evidence("SQL-1", [{"EmployeeNumber": "EMP-1001"}]),
        evidence("SQL-15", [{"PayrollStatus": "Ready"}]),
    ]
    registry = build_evidence_registry(records)
    assert [item.evidence_id for item in registry] == ["SQL-1", "SQL-15"]
    payload = _build_llm_payload_unmasked(
        question="Investigate EMP-1001",
        intent=IntentResult(InvestigationIntent.MISSING_DATA, 1.0, "test"),
        deterministic_reasoning=base_reasoning(),
        evidence=records,
        correlated_evidence=[],
        procedure_analysis=[],
        documents=[],
        evidence_focus=None,
    )
    prompt_ids = [item["evidence_id"] for item in payload["evidence_refs"]["canonical"]]
    assert prompt_ids == ["SQL-1", "SQL-15"]
    assert payload["evidence_refs"]["sql"][1]["ref"] == "SQL-15"
    assert payload["evidence_refs"]["sql"][1]["rows"] == [{"PayrollStatus": "Ready"}]
