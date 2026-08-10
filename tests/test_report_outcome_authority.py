from legacydb_copilot.agents.reasoning_agent import (
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
)
from legacydb_copilot.services.report_outcome_service import compose_report_outcome


def _reasoning(*, verified: bool) -> ReasoningResult:
    claim = RootCauseClaim(
        conclusion=(
            "For the exact entity RecordId = 2, dbo.usp_GetValue evaluates "
            "SourceDate IS NULL and produces value = NULL."
        ),
        evidence_refs=["SQL-3", "PROC-2"],
        status=(
            RootCauseSupportStatus.VERIFIED
            if verified
            else RootCauseSupportStatus.NOT_EVALUATED
        ),
    )
    return ReasoningResult(
        summary="Deterministic verified root cause." if verified else "Evidence summary.",
        likely_root_causes=[claim] if verified else [],
        supporting_evidence=["SQL-3 exact condition", "PROC-2 producer definition"],
        missing_evidence=[],
        recommended_fix=(
            ["Decide whether the verified NULL source date should be corrected."]
            if verified
            else []
        ),
        test_cases=[],
        proof_of_fix=[],
        rollback_plan=[],
        risks=[],
        confirmed_facts=(
            ["RecordId 2 has SourceDate = NULL.", "The producer returns NULL for that condition."]
            if verified
            else []
        ),
        response_type="confirmed_root_cause" if verified else "insufficient_evidence",
    )


def test_verified_root_cause_renders_positive_authoritative_outcome() -> None:
    outcome = compose_report_outcome(_reasoning(verified=True))

    assert outcome.root_cause_verified is True
    assert "SourceDate IS NULL" in outcome.root_cause_items[0]
    assert not any("not established" in item.lower() for item in outcome.root_cause_items)


def test_verified_why_it_happened_uses_causal_chain() -> None:
    outcome = compose_report_outcome(_reasoning(verified=True))

    rendered = " ".join(outcome.why_it_happened_items)
    assert "RecordId = 2" in rendered
    assert "SourceDate IS NULL" in rendered
    assert "producer returns NULL" in rendered


def test_verified_recommendation_agrees_with_known_cause() -> None:
    outcome = compose_report_outcome(_reasoning(verified=True))

    rendered = " ".join(outcome.recommendation_items).lower()
    assert "verified null source date" in rendered
    assert "cause is not established" not in rendered


def test_verified_evidence_ids_survive_composition() -> None:
    outcome = compose_report_outcome(_reasoning(verified=True))

    assert "SQL-3" in outcome.root_cause_items[0]
    assert "PROC-2" in outcome.root_cause_items[0]
    assert outcome.supporting_evidence_items == (
        "SQL-3 exact condition",
        "PROC-2 producer definition",
    )


def test_generated_fallback_prose_cannot_override_verified_claim() -> None:
    reasoning = _reasoning(verified=True)
    reasoning = ReasoningResult(
        **{
            **reasoning.__dict__,
            "summary": "Root cause not established from generated prose.",
        }
    )

    outcome = compose_report_outcome(reasoning)

    assert outcome.root_cause_verified is True
    assert all("not established" not in item.lower() for item in outcome.root_cause_items)


def test_unverified_investigation_keeps_conservative_fallback() -> None:
    outcome = compose_report_outcome(_reasoning(verified=False))

    assert outcome.root_cause_verified is False
    assert "not established" in outcome.root_cause_items[0].lower()
    assert "no causal event chain" in outcome.why_it_happened_items[0].lower()
    assert "not established" in outcome.recommendation_items[0].lower()


def test_verified_status_has_authority_even_if_response_type_is_stale() -> None:
    reasoning = _reasoning(verified=True)
    reasoning = ReasoningResult(**{**reasoning.__dict__, "response_type": "insufficient_evidence"})

    assert compose_report_outcome(reasoning).root_cause_verified is True
