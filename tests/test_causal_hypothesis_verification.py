import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.reasoning_agent import RootCauseSupportStatus
from legacydb_copilot.services.attribute_lineage_service import AttributeLineageCandidate
from legacydb_copilot.services.causal_hypothesis_service import (
    CausalCandidate,
    CausalVerificationStatus,
    causal_reasoning,
    evaluate_causal_candidates,
    generate_causal_candidates,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.stored_procedure_intelligence import analyze_stored_procedures


class Connector:
    def __init__(self, definition: str):
        self.definition = definition

    def get_procedure_definition(self, _name: str) -> str:
        return self.definition


def procedure(expression: str):
    definition = (
        "CREATE PROCEDURE ops.usp_Derived @WorkItemId int AS "
        f"SELECT {expression} AS DerivedValue FROM ops.WorkItems w "
        "WHERE w.WorkItemId = @WorkItemId"
    )
    return analyze_stored_procedures(Connector(definition), ["ops.usp_Derived"])[0]


def lineage(expression: str, sources=("SourceValue",)) -> list[AttributeLineageCandidate]:
    return [
        AttributeLineageCandidate(
            "DerivedValue", "ops.usp_Derived", "STORED_PROCEDURE",
            "ops.WorkItems", "WorkItemId", sources, expression,
            "definition_output_expression", 91.0, selected=True,
        )
    ]


def generate(expression: str, sources=("SourceValue",)):
    entities = extract_entities("Why is DerivedValue NULL for WorkItemId 2?")
    return generate_causal_candidates(
        entities=entities,
        lineage=lineage(expression, sources),
        procedures=[procedure(expression)],
    )


def result(candidate: CausalCandidate, matched: int, evidence_id="SQL-2") -> EvidenceResult:
    return EvidenceResult(
        f"Causal verification {candidate.candidate_id} for DerivedValue",
        candidate.verification_query,
        [{"WorkItemId": 2, "SourceValue": None, "causal_condition_met": matched}],
        evidence_id=evidence_id,
        parameters=candidate.verification_parameters,
        row_scope="exact_identifier_causal_verification",
    )


def test_case_branch_is_verified_with_exact_parameterized_evidence() -> None:
    expression = "CASE WHEN w.SourceValue IS NULL THEN NULL ELSE w.SourceValue END"
    candidates, queries = generate(expression)

    assert candidates[0].candidate_condition == "SourceValue IS NULL"
    assert queries[0].parameters == {"causal_entity_value_1": 2}
    assert queries[0].sql.endswith("WHERE WorkItemId = :causal_entity_value_1")

    evaluated = evaluate_causal_candidates(
        candidates,
        [
            result(candidates[0], 1),
            EvidenceResult(
                "Inspect calculation logic in ops.usp_Derived", "", [{"definition": expression}],
                evidence_id="PROC-1",
            ),
        ],
    )
    assert evaluated[0].status is CausalVerificationStatus.VERIFIED
    assert evaluated[0].supporting_evidence_ids == ("SQL-2", "PROC-1")
    reasoning = causal_reasoning(evaluated, [result(candidates[0], 1), EvidenceResult(
        "Inspect calculation logic in ops.usp_Derived", "", [{"definition": expression}], evidence_id="PROC-1"
    )])
    assert reasoning is not None
    assert reasoning.likely_root_causes[0].status is RootCauseSupportStatus.VERIFIED


def test_false_branch_is_rejected_and_persists_rejecting_evidence() -> None:
    candidates, _ = generate(
        "CASE WHEN w.SourceValue IS NULL THEN NULL ELSE w.SourceValue END"
    )
    evaluated = evaluate_causal_candidates(candidates, [result(candidates[0], 0)])

    assert evaluated[0].status is CausalVerificationStatus.REJECTED
    assert evaluated[0].rejecting_evidence_ids == ("SQL-2",)
    assert causal_reasoning(evaluated, [result(candidates[0], 0)]) is None


def test_multiple_case_branches_are_independently_verified_or_rejected() -> None:
    expression = (
        "CASE WHEN w.SourceValue IS NULL THEN NULL "
        "WHEN w.OtherValue IS NULL THEN NULL ELSE w.SourceValue END"
    )
    candidates, _ = generate(expression, ("SourceValue", "OtherValue"))
    evidence = [result(candidates[0], 0, "SQL-2"), result(candidates[1], 1, "SQL-3")]
    evaluated = evaluate_causal_candidates(candidates, evidence)

    assert [item.status for item in evaluated] == [
        CausalVerificationStatus.REJECTED,
        CausalVerificationStatus.VERIFIED,
    ]


@pytest.mark.parametrize(
    "expression,expected_fragment",
    [
        ("NULLIF(w.SourceValue, w.OtherValue)", "SourceValue = OtherValue"),
        ("COALESCE(w.SourceValue, w.OtherValue)", "SourceValue IS NULL"),
        ("w.SourceValue + w.OtherValue", "SourceValue IS NULL"),
        ("CAST(w.SourceValue AS int)", "SourceValue IS NULL"),
    ],
)
def test_generic_null_capable_expressions_create_conditions(
    expression: str, expected_fragment: str
) -> None:
    candidates, _ = generate(expression, ("SourceValue", "OtherValue"))
    assert candidates
    assert expected_fragment in candidates[0].candidate_condition


def test_unrepresentable_condition_remains_insufficient_not_verified() -> None:
    candidate = CausalCandidate(
        "CAUSE-1", "ops.usp_Derived", "DerivedValue", "external_fn(SourceValue)",
        ("SourceValue",), "external_fn(SourceValue) = 1", "NULL",
        {"field": "WorkItemId", "value": 2}, "", {},
        CausalVerificationStatus.INSUFFICIENT_EVIDENCE,
    )
    evaluated = evaluate_causal_candidates([candidate], [])
    assert evaluated[0].status is CausalVerificationStatus.INSUFFICIENT_EVIDENCE
    assert causal_reasoning(evaluated, []) is None


def test_supported_or_generated_candidate_cannot_become_root_cause_by_confidence() -> None:
    candidates, _ = generate(
        "CASE WHEN w.SourceValue IS NULL THEN NULL ELSE w.SourceValue END"
    )
    supported = [
        CausalCandidate(**{**candidates[0].__dict__, "status": CausalVerificationStatus.SUPPORTED})
    ]
    assert causal_reasoning(supported, []) is None
    assert causal_reasoning(candidates, []) is None
