from dataclasses import asdict
import json

import pytest

from legacydb_copilot.agents.reasoning_agent import RootCauseClaim, RootCauseSupportStatus


@pytest.mark.parametrize("status", list(RootCauseSupportStatus))
def test_root_cause_claim_accepts_every_support_status(status: RootCauseSupportStatus) -> None:
    claim = RootCauseClaim("Cause", status=status)

    assert claim.status is status


def test_root_cause_claim_rejects_invalid_support_status() -> None:
    with pytest.raises(ValueError):
        RootCauseClaim("Cause", status="INVALID")


def test_root_cause_claim_serialization_preserves_support_status() -> None:
    claim = RootCauseClaim("Cause", ["SQL-1"], RootCauseSupportStatus.VERIFIED)

    payload = json.loads(json.dumps(asdict(claim)))

    assert payload["status"] == "VERIFIED"


def test_root_cause_claim_deserialization_preserves_support_status() -> None:
    claim = RootCauseClaim(**{"conclusion": "Cause", "evidence_refs": ["SQL-1"], "status": "PARTIALLY_SUPPORTED"})

    assert claim.status is RootCauseSupportStatus.PARTIALLY_SUPPORTED


def test_existing_claim_defaults_to_not_evaluated() -> None:
    claim = RootCauseClaim("Cause")

    assert claim.status is RootCauseSupportStatus.NOT_EVALUATED


def test_existing_evidence_reference_behavior_is_unchanged() -> None:
    claim = RootCauseClaim("Cause", ["SQL-1", "SQL-2"])

    assert claim.evidence_refs == ["SQL-1", "SQL-2"]
