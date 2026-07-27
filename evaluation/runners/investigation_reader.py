from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from legacydb_copilot.db.models import (
    FixReadinessAssessmentModel,
    InvestigationAgenticStepModel,
    InvestigationModel,
    InvestigationStateTransitionModel,
    RootCauseHypothesisVerificationModel,
)


def _json(value: str, fallback):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


class InvestigationPersistenceReader:
    """Read persisted outputs after public API completion; never invokes reasoning code."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def read(
        self, investigation_id: str, *, organization_id: str, workspace_id: str
    ) -> dict[str, Any]:
        with self.session_factory() as db:
            record = (
                db.query(InvestigationModel)
                .filter(
                    InvestigationModel.id == investigation_id,
                    InvestigationModel.organization_id == organization_id,
                    InvestigationModel.workspace_id == workspace_id,
                )
                .one()
            )
            steps = (
                db.query(InvestigationAgenticStepModel)
                .filter(InvestigationAgenticStepModel.investigation_id == record.id)
                .order_by(
                    InvestigationAgenticStepModel.iteration_number.asc(),
                    InvestigationAgenticStepModel.created_at.asc(),
                )
                .all()
            )
            state = (
                db.query(InvestigationStateTransitionModel)
                .filter(InvestigationStateTransitionModel.investigation_id == record.id)
                .order_by(
                    InvestigationStateTransitionModel.transitioned_at.desc(),
                    InvestigationStateTransitionModel.id.desc(),
                )
                .first()
            )
            hypotheses = (
                db.query(RootCauseHypothesisVerificationModel)
                .filter(
                    RootCauseHypothesisVerificationModel.investigation_id == record.id
                )
                .all()
            )
            readiness = (
                db.query(FixReadinessAssessmentModel)
                .filter(FixReadinessAssessmentModel.investigation_id == record.id)
                .order_by(FixReadinessAssessmentModel.created_at.desc())
                .first()
            )
            return {
                "identified_entities": _json(record.extracted_entities_json, []),
                "evidence": _json(record.evidence_json, []),
                "generated_sql": _json(record.sql_queries_json, []),
                "executed_sql": _json(record.sql_queries_json, []),
                "report_snapshot": _json(record.report_snapshot_json, {}),
                "debug_trace": _json(record.ai_debug_trace_json, {}),
                "terminal_state": state.current_state if state else record.status,
                "stop_reason": state.reason if state else "",
                "agentic_steps": [
                    {
                        "iteration": item.iteration_number,
                        "state": item.state,
                        "action_fingerprint": item.action_fingerprint,
                        "evidence_request": _json(item.evidence_request_json, {}),
                        "evidence": _json(item.evidence_json, []),
                        "budget": _json(item.budget_json, {}),
                        "outcome": item.outcome,
                        "reason": item.reason,
                        "duration_ms": item.duration_ms,
                    }
                    for item in steps
                ],
                "root_cause_verifications": [
                    {
                        "hypothesis_id": item.hypothesis_id,
                        "origin": item.origin,
                        "status": item.status,
                        "valid_evidence_refs": _json(
                            item.valid_evidence_refs_json, []
                        ),
                        "visible_in_report": item.visible_in_report,
                    }
                    for item in hypotheses
                ],
                "fix_readiness_state": readiness.state if readiness else "NOT_ASSESSED",
                "report_json": _json(record.report_snapshot_json, {}),
                "report_artifacts": _json(record.report_storage_json, {}),
            }
