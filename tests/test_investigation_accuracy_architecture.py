from types import SimpleNamespace

from legacydb_copilot.agents.report_composer_agent import _evidence_only_summary
from legacydb_copilot.routers.chat import _evidence_to_json
from legacydb_copilot.services.claim_verification_service import (
    EvidenceReference,
    parse_structured_claim,
    verify_claim,
)
from legacydb_copilot.services.confidence_scoring_service import score_confidence
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult


def _evidence(evidence_id: str, rows: list[dict], **overrides) -> EvidenceResult:
    values = {
        "evidence_id": evidence_id,
        "evidence_semantics": "positive_rows",
        "supports_claim": "Verified result.",
        "evidence_relevance": "relevant",
    }
    values.update(overrides)
    return EvidenceResult("Inspect entity", "SELECT value FROM Entity", rows, **values)


def test_persisted_evidence_preserves_every_bounded_row() -> None:
    import json

    rows = [{"value": index} for index in range(15)]
    payload = json.loads(_evidence_to_json([_evidence("SQL-1", rows)]))[0]

    assert payload["rows"] == rows
    assert payload["sample_rows"] == rows[:10]
    assert payload["rows_truncated"] is False
    assert payload["evidence_relevance"] == "relevant"


def test_evidence_only_summary_does_not_drop_later_evidence() -> None:
    bundle = SimpleNamespace(
        evidence=[_evidence(f"SQL-{index}", [{"value": index}]) for index in range(1, 9)],
        procedure_analysis=[],
    )

    summary = _evidence_only_summary(bundle)

    assert "8 row(s)" not in summary
    assert summary.count("Inspect entity returned 1 row(s)") == 8


def test_unverified_empty_result_is_not_correlated_as_absence() -> None:
    result = _evidence(
        "SQL-1",
        [],
        evidence_semantics="not_applicable",
        supports_claim="",
        evidence_relevance="unverified",
    )

    correlated = correlate_evidence(evidence=[result], procedure_analysis=[], documents=[])

    assert correlated[0].confidence == "Low"
    assert "not verified" in correlated[0].finding


def test_confidence_does_not_reward_irrelevant_rows_or_unverified_absence() -> None:
    metadata = MetadataSearchResult([], [], [], "test")
    irrelevant = _evidence(
        "SQL-1", [{"value": "x"}], supports_claim="", evidence_relevance="irrelevant"
    )
    unverified_empty = _evidence(
        "SQL-2",
        [],
        evidence_semantics="not_applicable",
        supports_claim="",
        evidence_relevance="unverified",
    )

    assert score_confidence(metadata, [irrelevant, unverified_empty], []) == 0.2


def test_claim_cannot_ignore_conflicting_uncited_collected_evidence() -> None:
    refs = [
        EvidenceReference(
            evidence_id="SQL-1",
            type="SQL_RESULT",
            title="First read",
            columns=("Status",),
            rows=({"Status": "Ready"},),
            row_count=1,
        ),
        EvidenceReference(
            evidence_id="SQL-2",
            type="SQL_RESULT",
            title="Second read",
            columns=("Status",),
            rows=({"Status": "Blocked"},),
            row_count=1,
        ),
    ]
    claim = parse_structured_claim({"statement": "Status is Ready.", "evidence_ids": ["SQL-1"]})
    assert claim is not None

    result = verify_claim(claim, refs)

    assert result.verification_result == "REJECTED"
    assert result.rejection_code == "CONTRADICTORY_EVIDENCE"
    assert result.contradictory_evidence_ids == ("SQL-2",)
