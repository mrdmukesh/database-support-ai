import json
from pathlib import Path
from types import SimpleNamespace

from legacydb_copilot.agents.report_composer_agent import (
    _structured_evidence_gap_section,
)
from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.routers.learning import _evidence_gap_analysis
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gap_detection_service import (
    detect_evidence_gaps,
)
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult


def _gate() -> EvidenceGateResult:
    return EvidenceGateResult(
        required=True,
        reproduced=False,
        business_key_exists=True,
        reported_condition_exists=False,
        affected_rows_exist=True,
        parent_child_relationship_exists=False,
        confirmed_facts=[],
        blocking_reasons=["Condition not reproduced."],
        missing_evidence=["Runtime history"],
        status_interpretation=[],
    )


def test_gap_analysis_round_trips_from_persisted_investigation_json() -> None:
    analysis = detect_evidence_gaps(
        evidence=[
            EvidenceResult(
                "Inspect metadata",
                "",
                [{"object": "dbo.Target"}],
                evidence_id="META-1",
                evidence_semantics="metadata",
            )
        ],
        evidence_gate=_gate(),
    )
    investigation = InvestigationModel(
        evidence_gap_analysis_json=json.dumps(
            {
                "status": analysis.status,
                "gaps": [
                    {
                        "gap_id": item.gap_id,
                        "question_type": item.question_type,
                    }
                    for item in analysis.gaps
                ],
            },
            default=str,
        )
    )
    restored = _evidence_gap_analysis(investigation)
    assert restored["status"] == "GAPS_IDENTIFIED"
    assert restored["gaps"]


def test_report_section_exposes_structured_gap_fields() -> None:
    analysis = detect_evidence_gaps(evidence=[], evidence_gate=_gate())
    section = _structured_evidence_gap_section(SimpleNamespace(evidence_gap_analysis=analysis))
    assert section.title == "Structured Evidence Gap Analysis"
    assert section.tables[0].rows
    assert {
        "Gap ID",
        "Question",
        "Priority",
        "Required",
        "Status",
        "Source",
        "Evidence Refs",
        "Recommended Next Evidence",
        "Reason",
    } == set(section.tables[0].rows[0])


def test_gap_migration_adds_non_null_json_column_after_state_machine() -> None:
    migration = (
        Path(__file__).parents[1] / "alembic" / "versions" / "0014_evidence_gap_analysis.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "0013_investigation_state"' in migration
    assert '"evidence_gap_analysis_json"' in migration
    assert "nullable=False" in migration
