from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from legacydb_copilot.db.models import (
    ExecutionPathTraceModel,
    FixReadinessAssessmentModel,
    InvestigationAgenticStepModel,
    InvestigationModel,
    RootCauseHypothesisVerificationModel,
)
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.schemas import (
    ExecutionPathTraceRead,
    FixReadinessAssessmentRead,
    InvestigationAgenticStepRead,
    InvestigationProgressRead,
    InvestigationStateHistoryRead,
    InvestigationStateTransitionRead,
)
from legacydb_copilot.security.access_control import require_resource_owner_workspace
from legacydb_copilot.services.investigation_state_machine import (
    TERMINAL_STATES,
    InvestigationStateService,
    StateTransition,
    TerminalInvestigationState,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _investigation(
    db: Session,
    investigation_id: str,
    current_user,
) -> InvestigationModel:
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_resource_owner_workspace(db, current_user, investigation, action="read")
    return investigation


def _read(transition: StateTransition) -> InvestigationStateTransitionRead:
    return InvestigationStateTransitionRead(
        investigation_id=transition.investigation_id,
        previous_state=transition.previous_state.value if transition.previous_state else None,
        current_state=transition.current_state.value,
        transitioned_at=transition.transitioned_at,
        reason=transition.reason,
        iteration_number=transition.iteration_number,
    )


@router.get("/{investigation_id}/state", response_model=InvestigationStateTransitionRead)
def current_investigation_state(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationStateTransitionRead:
    _investigation(db, investigation_id, current_user)
    current = InvestigationStateService(db).current(investigation_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Agentic state is not initialized")
    return _read(current)


@router.get(
    "/{investigation_id}/state/history",
    response_model=InvestigationStateHistoryRead,
)
def investigation_state_history(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationStateHistoryRead:
    _investigation(db, investigation_id, current_user)
    transitions = InvestigationStateService(db).history(investigation_id)
    return InvestigationStateHistoryRead(
        investigation_id=investigation_id,
        current=_read(transitions[-1]) if transitions else None,
        transitions=[_read(item) for item in transitions],
    )


@router.get(
    "/{investigation_id}/agentic-steps",
    response_model=list[InvestigationAgenticStepRead],
)
def investigation_agentic_steps(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> list[InvestigationAgenticStepModel]:
    _investigation(db, investigation_id, current_user)
    return (
        db.query(InvestigationAgenticStepModel)
        .filter(InvestigationAgenticStepModel.investigation_id == investigation_id)
        .order_by(
            InvestigationAgenticStepModel.iteration_number.asc(),
            InvestigationAgenticStepModel.created_at.asc(),
        )
        .all()
    )


@router.get(
    "/{investigation_id}/execution-path",
    response_model=ExecutionPathTraceRead,
)
def investigation_execution_path(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> ExecutionPathTraceModel:
    _investigation(db, investigation_id, current_user)
    trace = (
        db.query(ExecutionPathTraceModel)
        .filter(ExecutionPathTraceModel.investigation_id == investigation_id)
        .order_by(ExecutionPathTraceModel.created_at.desc())
        .first()
    )
    if trace is None:
        raise HTTPException(status_code=404, detail="Execution path trace is not available")
    return trace


@router.get(
    "/{investigation_id}/fix-readiness",
    response_model=FixReadinessAssessmentRead,
)
def investigation_fix_readiness(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> FixReadinessAssessmentModel:
    _investigation(db, investigation_id, current_user)
    assessment = (
        db.query(FixReadinessAssessmentModel)
        .filter(FixReadinessAssessmentModel.investigation_id == investigation_id)
        .order_by(FixReadinessAssessmentModel.created_at.desc())
        .first()
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Fix readiness assessment is not available")
    return assessment


def _json(value: str, fallback):
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _safe_evidence(items: list[dict]) -> list[dict]:
    safe = []
    for item in items:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                "evidence_id": str(item.get("evidence_id") or ""),
                "purpose": str(item.get("purpose") or ""),
                "execution_status": str(item.get("execution_status") or ""),
                "evidence_semantics": str(item.get("evidence_semantics") or ""),
                "row_count": int(item.get("row_count") or 0),
                "supports_claim": str(item.get("supports_claim") or ""),
            }
        )
    return safe


@router.get(
    "/{investigation_id}/progress",
    response_model=InvestigationProgressRead,
)
def investigation_progress(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationProgressRead:
    investigation = _investigation(db, investigation_id, current_user)
    state_service = InvestigationStateService(db)
    current = state_service.current(investigation_id)
    steps = (
        db.query(InvestigationAgenticStepModel)
        .filter(InvestigationAgenticStepModel.investigation_id == investigation_id)
        .order_by(
            InvestigationAgenticStepModel.iteration_number.asc(),
            InvestigationAgenticStepModel.created_at.asc(),
        )
        .all()
    )
    latest_step = steps[-1] if steps else None
    latest_gap = _json(
        latest_step.gap_analysis_json
        if latest_step
        else investigation.evidence_gap_analysis_json,
        {},
    )
    questions = latest_gap.get("gaps", []) if isinstance(latest_gap, dict) else []
    questions = [item for item in questions if isinstance(item, dict)]
    counts = {"open": 0, "answered": 0, "partial": 0, "blocked": 0}
    answered_questions = (
        latest_gap.get("answered_questions", [])
        if isinstance(latest_gap, dict)
        else []
    )
    counts["answered"] = len(answered_questions)
    for question in questions:
        status = str(question.get("status") or "open").lower()
        if status in {"policy_blocked", "query_failed", "blocked_by_missing_source"}:
            key = "blocked"
        elif status == "contradicted":
            key = "partial"
        else:
            key = status if status in counts else "open"
        counts[key] += 1

    completed_steps = []
    failed_actions = []
    verified_absence = []
    source_badges = set()
    for step in steps:
        request = _json(step.evidence_request_json, {})
        evidence = _safe_evidence(_json(step.evidence_json, []))
        entry = {
            "iteration": step.iteration_number,
            "state": step.state,
            "action": str(
                request.get("request_type")
                or request.get("evidence_type")
                or request.get("type")
                or "No action selected"
            ),
            "reason": step.reason,
            "result": step.outcome,
            "created_evidence": evidence,
            "created_at": step.created_at.isoformat(),
        }
        completed_steps.append(entry)
        if step.outcome.lower() in {"failed", "blocked", "policy_blocked"}:
            failed_actions.append(entry)
        for item in evidence:
            semantics = item["evidence_semantics"].lower()
            if semantics == "verified_absence":
                verified_absence.append(item)
            if item["execution_status"].lower() == "succeeded":
                source_badges.add("Deterministic Evidence")
    if questions:
        source_badges.add("Evidence Gap")

    root_rows = (
        db.query(RootCauseHypothesisVerificationModel)
        .filter(
            RootCauseHypothesisVerificationModel.investigation_id
            == investigation_id
        )
        .all()
    )
    root_status = "NOT_ASSESSED"
    if any(row.status == "CONFIRMED" and row.visible_in_report for row in root_rows):
        root_status = "CONFIRMED"
        if any(
            row.status == "CONFIRMED"
            and row.visible_in_report
            and row.origin == "LLM"
            for row in root_rows
        ):
            source_badges.add("Verified AI Reasoning")
        else:
            source_badges.add("Deterministic Evidence")
    elif any(row.status == "PARTIALLY_SUPPORTED" for row in root_rows):
        root_status = "CANDIDATE"
    elif root_rows:
        root_status = "NOT_CONFIRMED"

    readiness = (
        db.query(FixReadinessAssessmentModel)
        .filter(FixReadinessAssessmentModel.investigation_id == investigation_id)
        .order_by(FixReadinessAssessmentModel.created_at.desc())
        .first()
    )
    terminal = bool(current and current.current_state in TERMINAL_STATES)
    if not current:
        source_badges.add("Deterministic Fallback")
    entities = _json(investigation.extracted_entities_json, [])
    safe_entities = [
        {
            "entity_type": str(item.get("entity_type") or item.get("type") or "Entity"),
            "value": str(item.get("value") or ""),
            "status": str(item.get("status") or "recorded"),
            "confidence": item.get("confidence"),
            "evidence_refs": item.get("evidence_refs") or [],
        }
        for item in entities
        if isinstance(item, dict)
    ]
    return InvestigationProgressRead(
        investigation_id=investigation_id,
        agentic=current is not None,
        current_state=(
            current.current_state.value if current else investigation.status
        ),
        iteration_number=current.iteration_number if current else 0,
        terminal=terminal,
        stop_reason=current.reason if terminal and current else "",
        budget=_json(latest_step.budget_json, {}) if latest_step else {},
        resolved_entities=safe_entities,
        question_counts=counts,
        questions=questions,
        completed_steps=completed_steps,
        failed_actions=failed_actions,
        verified_absence=verified_absence,
        root_cause_status=root_status,
        fix_readiness_state=readiness.state if readiness else "NOT_ASSESSED",
        source_badges=sorted(source_badges),
        can_cancel=bool(current and not terminal),
    )


@router.post(
    "/{investigation_id}/cancel",
    response_model=InvestigationStateTransitionRead,
)
def cancel_investigation(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> InvestigationStateTransitionRead:
    investigation = _investigation(db, investigation_id, current_user)
    service = InvestigationStateService(db)
    current = service.current(investigation_id)
    if current is None:
        raise HTTPException(
            status_code=409,
            detail="Older non-agentic investigations cannot be cancelled.",
        )
    try:
        transition = service.cancel(
            investigation,
            reason="Cancellation requested by an authorized user.",
        )
    except TerminalInvestigationState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return _read(transition)
