from legacydb_copilot.services.llm_reasoning_service import (
    AI_REASONING_PROMPT_VERSION,
    SYSTEM_PROMPT,
    _build_llm_payload_unmasked,
)
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult


def test_reasoning_prompt_starts_after_deterministic_evidence_collection() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    assert "responsibility begins only after deterministic evidence collection" in prompt
    for completed_stage in (
        "intent analysis",
        "entity extraction",
        "metadata discovery",
        "relationship discovery",
        "safe sql planning",
        "sql validation",
        "sql execution",
        "evidence verification",
        "stored procedure analysis",
        "metadata analysis",
        "evidence gate evaluation",
    ):
        assert completed_stage in prompt
    assert AI_REASONING_PROMPT_VERSION == "evidence-grounded-v2-post-deterministic"


def test_reasoning_prompt_preserves_evidence_and_execution_boundaries() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    for required_rule in (
        "do not generate new sql",
        "do not request additional sql execution",
        "never override deterministic sql evidence",
        "only when its evidence_semantics is",
        "otherwise describe it as an evidence gap",
        "never fabricate a root cause",
        "root cause not established from available evidence",
        "semantic similarity as weak candidate evidence",
        "verify read paths and write paths separately",
        "multiple plausible hypotheses",
        "never contradict the deterministic investigation pipeline",
        "return only valid json matching the requested schema",
    ):
        assert required_rule in prompt


def test_reasoning_prompt_requires_governed_change_proposals_and_citations() -> None:
    prompt = SYSTEM_PROMPT.casefold()

    for required_control in (
        "controlled change proposal",
        "validated in non-production first",
        "backup and rollback plan",
        "required approvals",
        "authorized operator",
    ):
        assert required_control in prompt
    assert "every finding, root cause, recommendation, validation test, and proof-of-fix step" in prompt
    assert "one or more evidence_refs" in prompt


def test_payload_advertises_only_persisted_evidence_ids_as_citations() -> None:
    payload = _build_llm_payload_unmasked(
        question="Why did the workflow fail?",
        intent=IntentResult(InvestigationIntent.PROCESS_FLOW_BREAK, 0.9, "test"),
        deterministic_reasoning=ReasoningResult(
            summary="Evidence collected.",
            likely_root_causes=[],
            supporting_evidence=[],
            missing_evidence=[],
            recommended_fix=[],
            test_cases=[],
            proof_of_fix=[],
            rollback_plan=[],
            risks=[],
        ),
        evidence=[
            EvidenceResult(
                "Inspect workflow",
                "SELECT 1",
                [{"Status": "Exception"}],
                evidence_id="SQL-9",
            )
        ],
        correlated_evidence=[
            CorrelatedEvidence("SQL", "workflow", "one row", "Status=Exception", "High")
        ],
        procedure_analysis=[],
        documents=[],
        evidence_focus=None,
    )

    assert payload["citation_contract"]["valid_evidence_ids"] == ["SQL-9"]
    assert "ref" not in payload["evidence_refs"]["correlated"][0]
    assert "EV-1" not in str(payload["required_json_schema"])
