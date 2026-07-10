from dataclasses import asdict
import json

from legacydb_copilot.agents.reasoning_agent import (
    MissingEvidence,
    ReasoningResult,
    RootCauseClaim,
    RootCauseSupportStatus,
)
from legacydb_copilot.agents.report_composer_agent import _missing_evidence_items


def reasoning(claims) -> ReasoningResult:
    return ReasoningResult("Summary", claims, [], [], [], [], [], [], [])


def missing(description: str = "Job history was not collected") -> MissingEvidence:
    return MissingEvidence(
        evidence_type="JOB_HISTORY",
        description=description,
        related_entity="retry_claims",
        reason_required="Required to confirm the triggering execution path",
    )


def test_missing_evidence_can_be_added_to_root_cause_claim() -> None:
    gap = missing()
    claim = RootCauseClaim("Possible retry cause", missing_evidence=[gap])

    assert claim.missing_evidence == [gap]


def test_multiple_missing_evidence_items_serialize_correctly() -> None:
    claim = RootCauseClaim(
        "Possible retry cause",
        missing_evidence=[missing("Job history missing"), missing("Audit trail missing")],
    )

    payload = json.loads(json.dumps(asdict(claim)))

    assert [item["description"] for item in payload["missing_evidence"]] == [
        "Job history missing",
        "Audit trail missing",
    ]
    assert payload["missing_evidence"][0]["evidence_type"] == "JOB_HISTORY"


def test_report_displays_missing_evidence_for_unconfirmed_claim() -> None:
    claim = RootCauseClaim(
        "Possible retry cause",
        status=RootCauseSupportStatus.UNSUPPORTED,
        missing_evidence=[missing()],
    )

    assert _missing_evidence_items(reasoning([claim])) == [
        "JOB_HISTORY: Job history was not collected (Related entity: retry_claims; Required because: Required to confirm the triggering execution path)"
    ]


def test_empty_missing_evidence_does_not_break_existing_reports() -> None:
    assert _missing_evidence_items(reasoning([RootCauseClaim("Legacy cause")])) == []


def test_report_hides_claim_missing_evidence_after_verification() -> None:
    claim = RootCauseClaim(
        "Confirmed cause",
        ["SQL-1"],
        RootCauseSupportStatus.VERIFIED,
        [missing()],
    )

    assert _missing_evidence_items(reasoning([claim])) == []
