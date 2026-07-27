from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import InvestigationModel, InvestigationPlannerSelectionModel
from legacydb_copilot.services.audit_service import record_audit_event


class EvidenceRequestType(StrEnum):
    ENTITY_LOOKUP = "ENTITY_LOOKUP"
    RELATED_RECORDS = "RELATED_RECORDS"
    STATUS_HISTORY = "STATUS_HISTORY"
    WORKFLOW_TRACE = "WORKFLOW_TRACE"
    EXCEPTION_LOOKUP = "EXCEPTION_LOOKUP"
    PROCEDURE_DEFINITION = "PROCEDURE_DEFINITION"
    FUNCTION_DEFINITION = "FUNCTION_DEFINITION"
    TRIGGER_DEFINITION = "TRIGGER_DEFINITION"
    DEPENDENCY_INSPECTION = "DEPENDENCY_INSPECTION"
    JOB_HISTORY = "JOB_HISTORY"
    TEMPORAL_CORRELATION = "TEMPORAL_CORRELATION"
    COUNT = "COUNT"
    VERIFIED_ABSENCE = "VERIFIED_ABSENCE"
    DUPLICATES = "DUPLICATES"
    REFERENTIAL_INTEGRITY = "REFERENTIAL_INTEGRITY"
    EXPECTED_STATE_CHECK = "EXPECTED_STATE_CHECK"


class EntityScope(StrEnum):
    EXACT_KEY = "EXACT_KEY"
    BOUNDED_RELATIONSHIP = "BOUNDED_RELATIONSHIP"
    BOUNDED_TIME_RANGE = "BOUNDED_TIME_RANGE"
    OBJECT_METADATA = "OBJECT_METADATA"
    BROAD = "BROAD"


class ActionOutcome(StrEnum):
    SELECTED = "SELECTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED_TRANSIENT = "FAILED_TRANSIENT"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class PlannerStatus(StrEnum):
    SELECTED = "SELECTED"
    NO_ELIGIBLE_ACTION = "NO_ELIGIBLE_ACTION"
    QUERY_BUDGET_EXHAUSTED = "QUERY_BUDGET_EXHAUSTED"
    ITERATION_BUDGET_EXHAUSTED = "ITERATION_BUDGET_EXHAUSTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"


@dataclass(frozen=True)
class EvidenceRequest:
    request_type: EvidenceRequestType
    unresolved_question: str
    entity_scope: EntityScope
    entity_type: str = ""
    entity_key: str = ""
    object_name: str = ""
    relationship_name: str = ""
    time_window: str = ""
    filters: tuple[tuple[str, str], ...] = ()
    supporting_evidence_refs: tuple[str, ...] = ()
    required_for_goal: bool = True
    expected_information_gain: float = 0.5
    estimated_query_cost: int = 1
    broad_scan: bool = False

    def __post_init__(self) -> None:
        if not self.unresolved_question.strip():
            raise ValueError("EvidenceRequest requires an unresolved question")
        if not 0 <= self.expected_information_gain <= 1:
            raise ValueError("expected_information_gain must be between 0 and 1")
        if self.estimated_query_cost < 0:
            raise ValueError("estimated_query_cost cannot be negative")
        if self.entity_scope is EntityScope.EXACT_KEY and not self.entity_key.strip():
            raise ValueError("EXACT_KEY requests require an entity key")


@dataclass(frozen=True)
class PreviousAction:
    fingerprint: str
    outcome: ActionOutcome
    attempts: int = 1


@dataclass(frozen=True)
class InvestigationBudget:
    queries_used: int
    query_limit: int
    iterations_used: int
    iteration_limit: int


@dataclass(frozen=True)
class EnvironmentPolicy:
    environment: str
    policy_name: str
    allow_broad_scans: bool = False
    max_query_cost: int = 10
    blocked_request_types: frozenset[EvidenceRequestType] = frozenset()


@dataclass(frozen=True)
class PlannerDecision:
    status: PlannerStatus
    selected_request: EvidenceRequest | None
    action_fingerprint: str
    selection_reason: str
    expected_information_gain: float
    suppressed_fingerprints: tuple[str, ...] = ()
    retry_number: int = 0
    ranking_audit: tuple[dict[str, Any], ...] = field(default_factory=tuple)


_QUESTION_ORDER = {
    "AFFECTED_ENTITY": 0,
    "EXPECTED_STATE": 1,
    "ACTUAL_STATE": 2,
    "RELATIONSHIPS": 3,
    "WORKFLOW": 4,
    "LAST_SUCCESSFUL_STEP": 5,
    "FIRST_FAILED_STEP": 6,
    "PROCEDURE_OWNERSHIP": 7,
    "DEPENDENCY_LOGIC": 7,
    "RUNTIME_EXECUTION": 8,
    "EXCEPTIONS": 9,
    "REPRODUCTION": 10,
    "EXTERNAL_EVIDENCE": 11,
}

_SCOPE_VALUE = {
    EntityScope.EXACT_KEY: 5,
    EntityScope.BOUNDED_RELATIONSHIP: 4,
    EntityScope.BOUNDED_TIME_RANGE: 3,
    EntityScope.OBJECT_METADATA: 2,
    EntityScope.BROAD: 0,
}


def action_fingerprint(request: EvidenceRequest) -> str:
    """Return a stable fingerprint for the logical action; it never includes SQL."""
    payload = {
        "request_type": request.request_type.value,
        "unresolved_question": request.unresolved_question.strip().upper(),
        "entity_scope": request.entity_scope.value,
        "entity_type": request.entity_type.strip().casefold(),
        "entity_key": request.entity_key.strip(),
        "object_name": request.object_name.strip().casefold(),
        "relationship_name": request.relationship_name.strip().casefold(),
        "time_window": request.time_window.strip(),
        "filters": sorted((str(key).casefold(), str(value)) for key, value in request.filters),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SafeInvestigationPlanner:
    """Ranks logical evidence requests without generating, validating, or executing SQL."""

    def select_next(
        self,
        *,
        candidates: list[EvidenceRequest] | tuple[EvidenceRequest, ...],
        previous_actions: list[PreviousAction] | tuple[PreviousAction, ...] = (),
        budget: InvestigationBudget,
        policy: EnvironmentPolicy,
    ) -> PlannerDecision:
        if budget.iterations_used >= budget.iteration_limit:
            return _blocked(PlannerStatus.ITERATION_BUDGET_EXHAUSTED, "Iteration budget exhausted.")
        if budget.queries_used >= budget.query_limit:
            return _blocked(PlannerStatus.QUERY_BUDGET_EXHAUSTED, "Query budget exhausted.")

        history: dict[str, list[PreviousAction]] = {}
        for action in previous_actions:
            history.setdefault(action.fingerprint, []).append(action)

        ranked: list[tuple[tuple[float, ...], str, EvidenceRequest, int, str]] = []
        suppressed: list[str] = []
        policy_rejections = 0
        audit: list[dict[str, Any]] = []
        for request in candidates:
            fingerprint = action_fingerprint(request)
            prior = history.get(fingerprint, [])
            retry_number, duplicate_reason = _retry_eligibility(prior)
            if duplicate_reason:
                suppressed.append(fingerprint)
                audit.append(
                    {
                        "fingerprint": fingerprint,
                        "eligible": False,
                        "reason": duplicate_reason,
                    }
                )
                continue
            policy_reason = _policy_rejection(request, policy)
            if policy_reason:
                policy_rejections += 1
                suppressed.append(fingerprint)
                audit.append(
                    {
                        "fingerprint": fingerprint,
                        "eligible": False,
                        "reason": policy_reason,
                    }
                )
                continue
            score = _score(request)
            reason = _selection_reason(request, retry_number, policy)
            ranked.append((score, fingerprint, request, retry_number, reason))
            audit.append(
                {
                    "fingerprint": fingerprint,
                    "eligible": True,
                    "score": list(score),
                    "expected_information_gain": request.expected_information_gain,
                }
            )

        if not ranked:
            status = (
                PlannerStatus.POLICY_BLOCKED
                if policy_rejections
                else PlannerStatus.NO_ELIGIBLE_ACTION
            )
            reason = (
                f"Environment policy {policy.policy_name} blocked every remaining action."
                if policy_rejections
                else "All candidate actions were already completed or exhausted."
            )
            return PlannerDecision(
                status=status,
                selected_request=None,
                action_fingerprint="",
                selection_reason=reason,
                expected_information_gain=0,
                suppressed_fingerprints=tuple(dict.fromkeys(suppressed)),
                ranking_audit=tuple(audit),
            )

        _, fingerprint, request, retry_number, reason = min(
            ranked,
            key=lambda item: (item[0], item[1]),
        )
        return PlannerDecision(
            status=PlannerStatus.SELECTED,
            selected_request=request,
            action_fingerprint=fingerprint,
            selection_reason=reason,
            expected_information_gain=request.expected_information_gain,
            suppressed_fingerprints=tuple(dict.fromkeys(suppressed)),
            retry_number=retry_number,
            ranking_audit=tuple(audit),
        )

    def persist(
        self,
        db: Session,
        *,
        investigation: InvestigationModel,
        decision: PlannerDecision,
    ) -> InvestigationPlannerSelectionModel:
        row = InvestigationPlannerSelectionModel(
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            status=decision.status.value,
            action_fingerprint=decision.action_fingerprint,
            evidence_request_json=json.dumps(
                asdict(decision.selected_request) if decision.selected_request else {},
                default=lambda value: value.value if isinstance(value, StrEnum) else str(value),
                sort_keys=True,
            ),
            selection_reason=decision.selection_reason,
            expected_information_gain=decision.expected_information_gain,
            retry_number=decision.retry_number,
            ranking_audit_json=json.dumps(decision.ranking_audit, sort_keys=True),
        )
        db.add(row)
        db.flush()
        record_audit_event(
            db,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            user_id=investigation.created_by_id,
            action="INVESTIGATION_EVIDENCE_ACTION_SELECTED",
            resource_type="investigation",
            resource_id=investigation.id,
            metadata={
                "status": decision.status.value,
                "action_fingerprint": decision.action_fingerprint,
                "selection_reason": decision.selection_reason,
                "expected_information_gain": decision.expected_information_gain,
            },
        )
        return row


def _score(request: EvidenceRequest) -> tuple[float, ...]:
    question = request.unresolved_question.strip().upper()
    return (
        0 if request.required_for_goal else 1,
        _QUESTION_ORDER.get(question, 99),
        -_SCOPE_VALUE[request.entity_scope],
        -request.expected_information_gain,
        request.estimated_query_cost,
        1 if request.broad_scan else 0,
        list(EvidenceRequestType).index(request.request_type),
    )


def _retry_eligibility(previous: list[PreviousAction]) -> tuple[int, str]:
    if not previous:
        return 0, ""
    if any(
        action.outcome in {ActionOutcome.SUCCEEDED, ActionOutcome.SELECTED}
        for action in previous
    ):
        return 0, "Duplicate action already selected or completed."
    if any(action.outcome is ActionOutcome.FAILED_PERMANENT for action in previous):
        return 0, "Action has a classified permanent failure; choose an alternative."
    transient_attempts = sum(
        max(action.attempts, 1)
        for action in previous
        if action.outcome is ActionOutcome.FAILED_TRANSIENT
    )
    if transient_attempts == 1:
        return 1, ""
    if transient_attempts > 1:
        return 0, "Controlled transient retry already consumed."
    return 0, "Previous action is not retryable."


def _policy_rejection(request: EvidenceRequest, policy: EnvironmentPolicy) -> str:
    if request.request_type in policy.blocked_request_types:
        return f"{policy.policy_name} blocks {request.request_type.value}."
    if request.estimated_query_cost > policy.max_query_cost:
        return f"Estimated query cost exceeds {policy.policy_name}."
    if (
        request.broad_scan or request.entity_scope is EntityScope.BROAD
    ) and not policy.allow_broad_scans:
        return f"{policy.policy_name} blocks broad scans."
    return ""


def _selection_reason(
    request: EvidenceRequest,
    retry_number: int,
    policy: EnvironmentPolicy,
) -> str:
    retry = " Controlled transient retry 1 of 1." if retry_number else ""
    return (
        f"Selected required question {request.unresolved_question}; "
        f"scope={request.entity_scope.value}, information_gain="
        f"{request.expected_information_gain:.2f}, cost={request.estimated_query_cost}, "
        f"policy={policy.policy_name}.{retry}"
    )


def _blocked(status: PlannerStatus, reason: str) -> PlannerDecision:
    return PlannerDecision(
        status=status,
        selected_request=None,
        action_fingerprint="",
        selection_reason=reason,
        expected_information_gain=0,
    )
