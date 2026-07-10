from dataclasses import asdict
import json

from legacydb_copilot.agents.reasoning_agent import RootCauseClaim


def test_root_cause_claim_accepts_one_evidence_reference() -> None:
    claim = RootCauseClaim("A retry created the duplicate.", ["SQL-1"])

    assert claim.evidence_refs == ["SQL-1"]


def test_root_cause_claim_accepts_multiple_evidence_references() -> None:
    claim = RootCauseClaim("A retry created the duplicate.", ["SQL-1", "PROC-1"])

    assert claim.evidence_refs == ["SQL-1", "PROC-1"]


def test_root_cause_claim_accepts_empty_evidence_references() -> None:
    claim = RootCauseClaim("Root cause remains unconfirmed.")

    assert claim.evidence_refs == []


def test_root_cause_claim_serializes_and_deserializes() -> None:
    original = RootCauseClaim("A retry created the duplicate.", ["SQL-1"])

    payload = json.loads(json.dumps(asdict(original)))
    restored = RootCauseClaim(**payload)

    assert restored == original


def test_root_cause_claim_instances_do_not_share_evidence_references() -> None:
    first = RootCauseClaim("First")
    second = RootCauseClaim("Second")

    first.evidence_refs.append("SQL-1")

    assert first.evidence_refs == ["SQL-1"]
    assert second.evidence_refs == []
