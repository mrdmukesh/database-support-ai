from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import FixReadinessAssessmentModel, InvestigationModel
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.root_cause_hypothesis_service import (
    HypothesisStatus,
    RootCauseVerificationResult,
)


class FixReadinessState(StrEnum):
    TRIAGE_ONLY = "TRIAGE_ONLY"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    INVESTIGATION_INCOMPLETE = "INVESTIGATION_INCOMPLETE"
    ROOT_CAUSE_CANDIDATE = "ROOT_CAUSE_CANDIDATE"
    ROOT_CAUSE_CONFIRMED = "ROOT_CAUSE_CONFIRMED"
    FIX_PROPOSAL_READY = "FIX_PROPOSAL_READY"
    PROOF_OF_FIX_READY = "PROOF_OF_FIX_READY"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class CriterionStatus(StrEnum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class ReadinessCriterion:
    name: str
    status: CriterionStatus
    evidence_refs: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class ControlledFixProposal:
    description: str = ""
    risk_assessment: str = ""
    pre_change_checks: tuple[str, ...] = ()
    post_fix_validation: tuple[str, ...] = ()
    rollback_plan: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    controlled: bool = False


@dataclass(frozen=True)
class FixReadinessInputs:
    affected_entity_resolved: bool = False
    scope_defined: bool = False
    expected_state_established: bool = False
    actual_state_verified: bool = False
    relationships_traced: bool = False
    runtime_execution_required: bool = True
    runtime_execution_verified: bool = False
    last_successful_step_identified: bool = False
    first_failed_step_identified: bool = False
    contradictions_resolved: bool = False
    evidence_references_valid: bool = False
    evidence_refs_by_criterion: dict[str, tuple[str, ...]] | None = None
    root_cause_verification: RootCauseVerificationResult | None = None
    fix_proposal: ControlledFixProposal | None = None
    evidence_collected: bool = False
    blocked_reason: str = ""
    failed_reason: str = ""


@dataclass(frozen=True)
class FixReadinessAssessment:
    state: FixReadinessState
    score: int
    criteria: tuple[ReadinessCriterion, ...]
    blockers: tuple[str, ...]
    recommended_next_evidence: tuple[str, ...]
    confirmed_hypothesis_ids: tuple[str, ...]
    decision_reason: str

    @property
    def criteria_by_name(self) -> dict[str, ReadinessCriterion]:
        return {item.name: item for item in self.criteria}


_EVIDENCE_CRITERIA = (
    "affected_entity_resolved",
    "scope_defined",
    "expected_state_established",
    "actual_state_verified",
    "relationships_traced",
    "runtime_execution_verified",
    "last_successful_step_identified",
    "first_failed_step_identified",
    "causal_component_and_condition_verified",
    "contradictions_resolved",
    "evidence_references_valid",
)
_FIX_CRITERIA = (
    "controlled_fix_proposed",
    "risk_assessed",
    "pre_change_checks_defined",
    "post_fix_validation_defined",
    "rollback_defined",
)
_NEXT_EVIDENCE = {
    "affected_entity_resolved": (
        "Resolve the exact affected entity or explicitly define a bounded diagnostic scope."
    ),
    "scope_defined": "Define the affected entity set, workflow, and time boundary.",
    "expected_state_established": (
        "Collect an authoritative expected-state rule with an evidence reference."
    ),
    "actual_state_verified": "Verify the actual persisted state for the affected scope.",
    "relationships_traced": "Trace key-based relationships for the resolved entity.",
    "runtime_execution_verified": (
        "Collect runtime history proving whether the relevant component executed."
    ),
    "last_successful_step_identified": "Verify the last completed processing step.",
    "first_failed_step_identified": (
        "Verify the first failed, missing, or inconsistent processing step."
    ),
    "causal_component_and_condition_verified": (
        "Independently verify the responsible component and causal condition."
    ),
    "contradictions_resolved": "Resolve material contradictory evidence.",
    "evidence_references_valid": (
        "Replace missing, failed, blocked, irrelevant, or rejected evidence references."
    ),
    "controlled_fix_proposed": "Prepare a controlled change proposal tied to the confirmed cause.",
    "risk_assessed": "Assess change, data, operational, and regression risk.",
    "pre_change_checks_defined": "Define non-production and pre-change validation checks.",
    "post_fix_validation_defined": "Define evidence-backed proof-of-fix checks.",
    "rollback_defined": "Define a tested rollback plan.",
}


class FixReadinessAssessor:
    def assess(self, inputs: FixReadinessInputs) -> FixReadinessAssessment:
        refs = inputs.evidence_refs_by_criterion or {}
        confirmed_ids, candidate_exists = _accepted_hypotheses(
            inputs.root_cause_verification
        )
        causal_verified = bool(confirmed_ids)
        proposal = inputs.fix_proposal or ControlledFixProposal()
        values = {
            "affected_entity_resolved": inputs.affected_entity_resolved,
            "scope_defined": inputs.scope_defined,
            "expected_state_established": inputs.expected_state_established,
            "actual_state_verified": inputs.actual_state_verified,
            "relationships_traced": inputs.relationships_traced,
            "runtime_execution_verified": (
                inputs.runtime_execution_verified
                if inputs.runtime_execution_required
                else None
            ),
            "last_successful_step_identified": inputs.last_successful_step_identified,
            "first_failed_step_identified": inputs.first_failed_step_identified,
            "causal_component_and_condition_verified": causal_verified,
            "contradictions_resolved": inputs.contradictions_resolved,
            "evidence_references_valid": inputs.evidence_references_valid,
            "controlled_fix_proposed": bool(proposal.controlled and proposal.description.strip()),
            "risk_assessed": bool(proposal.risk_assessment.strip()),
            "pre_change_checks_defined": bool(proposal.pre_change_checks),
            "post_fix_validation_defined": bool(proposal.post_fix_validation),
            "rollback_defined": bool(proposal.rollback_plan),
        }
        criteria = tuple(
            _criterion(
                name,
                values[name],
                refs.get(name, ())
                or (
                    proposal.evidence_refs
                    if name in _FIX_CRITERIA
                    else ()
                ),
            )
            for name in (*_EVIDENCE_CRITERIA, *_FIX_CRITERIA)
        )
        missing = tuple(
            item.name for item in criteria if item.status is CriterionStatus.MISSING
        )
        scoreable = tuple(
            item for item in criteria if item.status is not CriterionStatus.NOT_REQUIRED
        )
        score = round(
            100
            * sum(item.status is CriterionStatus.SATISFIED for item in scoreable)
            / len(scoreable)
        )
        root_cause_prerequisites_met = causal_verified and all(
            values[name] in {True, None} for name in _EVIDENCE_CRITERIA
        )

        if inputs.failed_reason:
            state = FixReadinessState.FAILED
            reason = inputs.failed_reason
        elif inputs.blocked_reason:
            state = FixReadinessState.BLOCKED
            reason = inputs.blocked_reason
        elif not inputs.evidence_collected:
            state = FixReadinessState.TRIAGE_ONLY
            reason = "Deterministic evidence collection has not established investigation facts."
        elif not inputs.affected_entity_resolved:
            state = (
                FixReadinessState.EVIDENCE_COLLECTED
                if inputs.evidence_references_valid
                else FixReadinessState.INVESTIGATION_INCOMPLETE
            )
            reason = "No exact affected entity is resolved; fix readiness is capped."
        elif root_cause_prerequisites_met:
            if all(values[name] is True for name in _FIX_CRITERIA):
                state = FixReadinessState.PROOF_OF_FIX_READY
                reason = "Confirmed cause, controlled fix, validation, and rollback are ready."
            elif all(
                values[name] is True
                for name in (
                    "controlled_fix_proposed",
                    "risk_assessed",
                    "pre_change_checks_defined",
                )
            ):
                state = FixReadinessState.FIX_PROPOSAL_READY
                reason = "A controlled fix can be prepared against the confirmed cause."
            else:
                state = FixReadinessState.ROOT_CAUSE_CONFIRMED
                reason = "The causal chain is confirmed; fix controls remain incomplete."
        elif candidate_exists or causal_verified:
            state = FixReadinessState.ROOT_CAUSE_CANDIDATE
            reason = (
                "A supported causal conclusion exists, but one or more deterministic "
                "root-cause prerequisites remain incomplete."
            )
        elif any(values[name] for name in _EVIDENCE_CRITERIA):
            state = FixReadinessState.INVESTIGATION_INCOMPLETE
            reason = "Evidence exists, but required investigation prerequisites remain incomplete."
        else:
            state = FixReadinessState.EVIDENCE_COLLECTED
            reason = "Evidence was collected but has not yet satisfied readiness criteria."

        blockers = tuple(_NEXT_EVIDENCE[name] for name in missing)
        return FixReadinessAssessment(
            state=state,
            score=score,
            criteria=criteria,
            blockers=blockers,
            recommended_next_evidence=blockers,
            confirmed_hypothesis_ids=confirmed_ids,
            decision_reason=reason,
        )

    def persist(
        self,
        db: Session,
        *,
        investigation: InvestigationModel,
        assessment: FixReadinessAssessment,
    ) -> FixReadinessAssessmentModel:
        row = FixReadinessAssessmentModel(
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            investigation_id=investigation.id,
            state=assessment.state.value,
            score=assessment.score,
            criteria_json=json.dumps(
                [asdict(item) for item in assessment.criteria],
                default=_json_default,
                sort_keys=True,
            ),
            blockers_json=json.dumps(assessment.blockers),
            recommended_next_evidence_json=json.dumps(
                assessment.recommended_next_evidence
            ),
            confirmed_hypothesis_ids_json=json.dumps(
                assessment.confirmed_hypothesis_ids
            ),
            decision_reason=assessment.decision_reason,
        )
        db.add(row)
        db.flush()
        record_audit_event(
            db,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            user_id=investigation.created_by_id,
            action="FIX_READINESS_ASSESSED",
            resource_type="investigation",
            resource_id=investigation.id,
            metadata={
                "state": assessment.state.value,
                "score": assessment.score,
                "blocker_count": len(assessment.blockers),
                "confirmed_hypothesis_ids": assessment.confirmed_hypothesis_ids,
            },
        )
        return row


def _accepted_hypotheses(
    result: RootCauseVerificationResult | None,
) -> tuple[tuple[str, ...], bool]:
    if result is None:
        return (), False
    confirmed = tuple(
        item.hypothesis.hypothesis_id
        for item in result.verifications
        if item.status is HypothesisStatus.CONFIRMED and item.visible_in_report
    )
    candidate = any(
        item.status is HypothesisStatus.PARTIALLY_SUPPORTED
        for item in result.verifications
    )
    return confirmed, candidate


def _criterion(
    name: str,
    value: bool | None,
    evidence_refs: tuple[str, ...],
) -> ReadinessCriterion:
    if value is None:
        return ReadinessCriterion(
            name=name,
            status=CriterionStatus.NOT_REQUIRED,
            reason="Not required for this investigation.",
        )
    return ReadinessCriterion(
        name=name,
        status=CriterionStatus.SATISFIED if value else CriterionStatus.MISSING,
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        reason=(
            "Deterministic prerequisite satisfied."
            if value
            else _NEXT_EVIDENCE[name]
        ),
    )


def _json_default(value):
    if isinstance(value, StrEnum):
        return value.value
    return str(value)
