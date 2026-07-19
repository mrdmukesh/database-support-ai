from pathlib import Path

import pytest

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("domain,prefix,table", [
    ("banking", "BNK", "cards"),
    ("shipping", "SHP", "voyages"),
])
def test_exception_handling_fixture_reproduces_reported_processing_status(
    domain: str, prefix: str, table: str
) -> None:
    scenario = ROOT / "evaluation_scenarios" / domain / f"{domain}-benchmark-007"
    injection = (scenario / "inject.sql").read_text(encoding="utf-8")
    verification = (scenario / "verify.sql").read_text(encoding="utf-8")

    assert f"eval.[{table}]" in injection
    assert f"{prefix}-2026-0007-A" in injection
    assert "N'Processing'" in injection
    assert "e.Status=N'Processing'" in verification
    assert "JOIN eval.exceptions" in verification


def test_banking_batch_fixture_reproduces_reported_running_status() -> None:
    scenario = ROOT / "evaluation_scenarios" / "banking" / "banking-pilot-004"
    injection = (scenario / "inject.sql").read_text(encoding="utf-8")
    verification = (scenario / "verify.sql").read_text(encoding="utf-8")

    assert "N'BAT-3104',Status=N'Running'" in injection
    assert "BusinessKey=N'BAT-3104' AND Status=N'Running'" in verification
    assert "JOIN eval.exceptions" in verification


@pytest.mark.parametrize(
    "question,proven_table,distractor",
    [
        (
            "Investigate why workflow procedure processing left payment BNK-2026-0013-A in the wrong status.",
            "eval.beneficiaries",
            "eval.payment_instructions",
        ),
        (
            "Investigate why exception handling left shipment SHP-2026-0007-A in Processing.",
            "eval.voyages",
            "eval.shipment_milestones",
        ),
    ],
)
def test_database_proven_entity_table_precedes_generic_question_noun(
    question: str, proven_table: str, distractor: str
) -> None:
    metadata = MetadataSearchResult(
        tables=[
            TableMetadata(proven_table, ["BusinessKey", "Status"], 0),
            TableMetadata(distractor, ["BusinessKey", "Status"], 20),
        ],
        views=[], procedures=[], version="test",
    )
    entity = next(value for value in question.split() if "2026" in value).rstrip(".")
    evidence = [
        EvidenceResult(
            f"Prove requested entity exists in {proven_table}",
            f"SELECT BusinessKey, Status FROM {proven_table} WHERE BusinessKey = '{entity}'",
            [{"BusinessKey": entity, "Status": "Failed"}],
        )
    ]

    focus = build_evidence_focus(
        question=question,
        intent=InvestigationIntent.PROCESS_FLOW_BREAK,
        entities=extract_entities(question),
        metadata=metadata,
        evidence=evidence,
        correlated_evidence=[], procedure_analysis=[], documents=[],
    )

    assert focus.affected_object == proven_table
