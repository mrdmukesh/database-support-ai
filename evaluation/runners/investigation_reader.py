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
from legacydb_copilot.services.investigation_state_machine import TERMINAL_STATES
from legacydb_copilot.services.terminal_outcome_service import (
    resolve_legacy_terminal_outcome,
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
                    InvestigationStateTransitionModel.sequence_number.desc(),
                )
                .first()
            )
            terminal_state_values = {item.value for item in TERMINAL_STATES}
            canonical_transition = (
                db.query(InvestigationStateTransitionModel)
                .filter(
                    InvestigationStateTransitionModel.investigation_id == record.id,
                    InvestigationStateTransitionModel.current_state.in_(
                        terminal_state_values
                    ),
                )
                .order_by(
                    InvestigationStateTransitionModel.sequence_number.desc(),
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
            debug_trace = _json(record.ai_debug_trace_json, {})
            canonical_state = (
                canonical_transition.current_state
                if canonical_transition
                else ""
            )
            legacy_state = resolve_legacy_terminal_outcome(
                record.status,
                debug_trace,
            )
            return {
                "lifecycle_diagnostics": {
                    "created_at": str(record.created_at),
                    "updated_at": str(record.updated_at),
                    "execution_mode": "synchronous_public_api",
                    "queue_time": None,
                    "worker_claim_time": None,
                    "state_transitions": [
                        {
                            "previous_state": item.previous_state,
                            "current_state": item.current_state,
                            "transitioned_at": str(item.transitioned_at),
                            "reason": item.reason,
                            "iteration_number": item.iteration_number,
                            "sequence_number": item.sequence_number,
                        }
                        for item in sorted(
                            record.state_transitions,
                            key=lambda transition: transition.sequence_number,
                        )
                    ],
                },
                "identified_entities": _json(record.extracted_entities_json, []),
                "evidence": _json(record.evidence_json, []),
                "generated_sql": _json(record.sql_queries_json, []),
                "executed_sql": _json(record.sql_queries_json, []),
                "report_snapshot": _json(record.report_snapshot_json, {}),
                "debug_trace": debug_trace,
                "terminal_state": (
                    canonical_state
                    or (legacy_state.value if legacy_state else record.status)
                ),
                "stop_reason": (
                    canonical_transition.reason
                    if canonical_transition
                    else state.reason if state else ""
                ),
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
