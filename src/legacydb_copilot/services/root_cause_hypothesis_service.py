from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from legacydb_copilot.db.models import (
    InvestigationModel,
    RootCauseHypothesisVerificationModel,
)
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.execution_path_tracing_service import (
    ExecutionPathTrace,
    TraceVerificationLabel,
)


class HypothesisOrigin(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CausalLink:
    value: str
    evidence_refs: tuple[str, ...] = ()
    independently_verified: bool = False


@dataclass(frozen=True)
class HypothesisContradiction:
    description: str
    evidence_refs: tuple[str, ...]
    material: bool = True
    resolved: bool = False


@dataclass(frozen=True)
class RootCauseHypothesis:
    hypothesis_id: str
    description: str
    origin: HypothesisOrigin
    affected_entity: CausalLink
    expected_state: CausalLink
    actual_state: CausalLink
    last_successful_step: CausalLink
    first_failed_step: CausalLink
    responsible_component: CausalLink
    causal_condition: CausalLink
    actual_state_is_incorrect: bool
    supporting_evidence: tuple[str, ...] = ()
    missing_proof: tuple[str, ...] = ()
    contradictions: tuple[HypothesisContradiction, ...] = ()

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip():
            raise ValueError("hypothesis_id is required")
        if not self.description.strip():
            raise ValueError("description is required")


@dataclass(frozen=True)
class CausalLinkVerification:
    link_name: str
    value: str
    verified: bool
    valid_evidence_refs: tuple[str, ...]
    invalid_evidence_refs: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class HypothesisVerification:
    hypothesis: RootCauseHypothesis
    status: HypothesisStatus
    verification_matrix: tuple[CausalLinkVerification, ...]
    valid_evidence_refs: tuple[str, ...]
    missing_proof: tuple[str, ...]
    contradictions: tuple[HypothesisContradiction, ...]
    decision_reason: str
    visible_in_report: bool


@dataclass(frozen=True)
class RootCauseVerificationResult:
    verifications: tuple[HypothesisVerification, ...]
    confirmed_hypothesis_ids: tuple[str, ...]
    rejected_hypothesis_ids: tuple[str, ...]
    evidence_package_hash: str

    @property
    def root_cause_confirmed(self) -> bool:
        return bool(self.confirmed_hypothesis_ids)

    @property
    def visible_hypotheses(self) -> tuple[HypothesisVerification, ...]:
        return tuple(item for item in self.verifications if item.visible_in_report)


_LINK_NAMES = (
    "affected_entity",
    "expected_state",
    "actual_state",
    "last_successful_step",
    "first_failed_step",
    "responsible_component",
    "causal_condition",
)


class RootCauseHypothesisVerifier:
    def verify(
        self,
        hypotheses: Iterable[RootCauseHypothesis],
        evidence: Iterable[EvidenceResult],
    ) -> RootCauseVerificationResult:
        evidence_items = tuple(evidence)
        evidence_by_id = {item.evidence_id: item for item in evidence_items}
        verifications = tuple(
            self._verify_one(hypothesis, evidence_by_id)
            for hypothesis in hypotheses
        )
        return RootCauseVerificationResult(
            verifications=verifications,
            confirmed_hypothesis_ids=tuple(
                item.hypothesis.hypothesis_id
                for item in verifications
                if item.status is HypothesisStatus.CONFIRMED
            ),
            rejected_hypothesis_ids=tuple(
                item.hypothesis.hypothesis_id
                for item in verifications
                if item.status is HypothesisStatus.REJECTED
            ),
            evidence_package_hash=_evidence_hash(evidence_items),
        )

    def persist(
        self,
        db: Session,
        *,
        investigation: InvestigationModel,
        result: RootCauseVerificationResult,
    ) -> tuple[RootCauseHypothesisVerificationModel, ...]:
        rows = []
        for verification in result.verifications:
            row = RootCauseHypothesisVerificationModel(
                organization_id=investigation.organization_id,
                workspace_id=investigation.workspace_id,
                investigation_id=investigation.id,
                hypothesis_id=verification.hypothesis.hypothesis_id,
                origin=verification.hypothesis.origin.value,
                status=verification.status.value,
                hypothesis_json=json.dumps(
                    asdict(verification.hypothesis),
                    default=_json_default,
                    sort_keys=True,
                ),
                verification_matrix_json=json.dumps(
                    [asdict(item) for item in verification.verification_matrix],
                    sort_keys=True,
                ),
                valid_evidence_refs_json=json.dumps(verification.valid_evidence_refs),
                missing_proof_json=json.dumps(verification.missing_proof),
                contradictions_json=json.dumps(
                    [asdict(item) for item in verification.contradictions],
                    sort_keys=True,
                ),
                evidence_package_hash=result.evidence_package_hash,
                decision_reason=verification.decision_reason,
                visible_in_report=verification.visible_in_report,
            )
            db.add(row)
            rows.append(row)
        db.flush()
        record_audit_event(
            db,
            organization_id=investigation.organization_id,
            workspace_id=investigation.workspace_id,
            user_id=investigation.created_by_id,
            action="ROOT_CAUSE_HYPOTHESES_VERIFIED",
            resource_type="investigation",
            resource_id=investigation.id,
            metadata={
                "hypothesis_count": len(result.verifications),
                "confirmed_hypothesis_ids": result.confirmed_hypothesis_ids,
                "rejected_hypothesis_ids": result.rejected_hypothesis_ids,
                "evidence_package_hash": result.evidence_package_hash,
            },
        )
        return tuple(rows)

    def _verify_one(
        self,
        hypothesis: RootCauseHypothesis,
        evidence_by_id: dict[str, EvidenceResult],
    ) -> HypothesisVerification:
        matrix = tuple(
            _verify_link(
                link_name,
                getattr(hypothesis, link_name),
                evidence_by_id,
            )
            for link_name in _LINK_NAMES
        )
        matrix_by_name = {item.link_name: item for item in matrix}
        missing = list(hypothesis.missing_proof)
        missing.extend(
            item.link_name
            for item in matrix
            if not item.verified
        )
        if not hypothesis.actual_state_is_incorrect:
            missing.append("verified_incorrect_actual_state")
        unresolved_contradictions = tuple(
            item
            for item in hypothesis.contradictions
            if item.material and not item.resolved
        )
        invalid_refs = tuple(
            dict.fromkeys(
                ref
                for item in matrix
                for ref in item.invalid_evidence_refs
            )
        )
        all_valid_refs = tuple(
            dict.fromkeys(
                ref
                for item in matrix
                for ref in item.valid_evidence_refs
            )
        )
        verified_count = sum(item.verified for item in matrix)
        entity_missing = not hypothesis.affected_entity.value.strip()
        causal_evidence = tuple(
            evidence_by_id[ref]
            for ref in matrix_by_name["causal_condition"].valid_evidence_refs
        )
        absence_only_causation = bool(causal_evidence) and all(
            item.evidence_semantics == "verified_absence"
            for item in causal_evidence
        )
        metadata_only_component = _metadata_only(
            matrix_by_name["responsible_component"].valid_evidence_refs,
            evidence_by_id,
        )
        metadata_only_causal = _metadata_only(
            matrix_by_name["causal_condition"].valid_evidence_refs,
            evidence_by_id,
        )
        if absence_only_causation:
            missing.append("positive causal evidence beyond verified absence")
        if metadata_only_component:
            missing.append("runtime evidence for responsible component")
        if metadata_only_causal:
            missing.append("runtime evidence for causal condition")

        if invalid_refs:
            status = HypothesisStatus.REJECTED
            reason = "One or more claimed evidence references are invalid or unverified."
        elif entity_missing:
            status = HypothesisStatus.BLOCKED
            reason = "Affected entity or investigation scope is not resolved."
        elif unresolved_contradictions:
            status = HypothesisStatus.BLOCKED
            reason = "Material contradictory evidence remains unresolved."
        elif (
            verified_count == len(_LINK_NAMES)
            and hypothesis.actual_state_is_incorrect
            and not absence_only_causation
            and not metadata_only_component
            and not metadata_only_causal
            and not missing
        ):
            status = HypothesisStatus.CONFIRMED
            reason = "Every required causal link is independently verified."
        elif verified_count:
            status = HypothesisStatus.PARTIALLY_SUPPORTED
            reason = "Some required causal links are verified, but material proof is missing."
        else:
            status = HypothesisStatus.PROPOSED
            reason = "The hypothesis has no independently verified causal link yet."
        if (
            hypothesis.origin is HypothesisOrigin.LLM
            and not matrix_by_name["causal_condition"].verified
        ):
            status = HypothesisStatus.REJECTED
            reason = "The AI-proposed causal claim lacks independently verified causal evidence."

        return HypothesisVerification(
            hypothesis=hypothesis,
            status=status,
            verification_matrix=matrix,
            valid_evidence_refs=all_valid_refs,
            missing_proof=tuple(dict.fromkeys(missing)),
            contradictions=hypothesis.contradictions,
            decision_reason=reason,
            visible_in_report=status is HypothesisStatus.CONFIRMED,
        )


def build_hypothesis_from_execution_trace(
    *,
    hypothesis_id: str,
    description: str,
    origin: HypothesisOrigin,
    trace: ExecutionPathTrace,
    affected_entity_evidence_refs: tuple[str, ...],
    expected_state: CausalLink,
    actual_state: CausalLink,
    causal_condition: CausalLink,
    actual_state_is_incorrect: bool,
) -> RootCauseHypothesis:
    """Build AG-07 causal links from AG-06 without upgrading metadata to runtime proof."""
    nodes = {item.step_id: item for item in trace.nodes}
    last = nodes.get(trace.last_successful_step)
    first = nodes.get(trace.first_failed_or_missing_step)
    contradictions = tuple(
        HypothesisContradiction(
            description=node.reason,
            evidence_refs=node.evidence_refs,
            material=True,
            resolved=False,
        )
        for node in trace.nodes
        if node.verification_label is TraceVerificationLabel.CONTRADICTORY
    )
    first_verified = bool(
        first
        and first.verification_label
        in {
            TraceVerificationLabel.RUNTIME_VERIFIED,
            TraceVerificationLabel.DATA_STATE_VERIFIED,
        }
    )
    return RootCauseHypothesis(
        hypothesis_id=hypothesis_id,
        description=description,
        origin=origin,
        affected_entity=CausalLink(
            trace.affected_entity,
            affected_entity_evidence_refs,
            bool(trace.affected_entity and affected_entity_evidence_refs),
        ),
        expected_state=expected_state,
        actual_state=actual_state,
        last_successful_step=CausalLink(
            last.name if last else "",
            last.evidence_refs if last else (),
            bool(last),
        ),
        first_failed_step=CausalLink(
            first.name if first else "",
            first.evidence_refs if first else (),
            first_verified,
        ),
        responsible_component=CausalLink(
            trace.responsible_component,
            first.evidence_refs if first and trace.responsible_component else (),
            bool(trace.responsible_component and first_verified),
        ),
        causal_condition=causal_condition,
        actual_state_is_incorrect=actual_state_is_incorrect,
        supporting_evidence=tuple(
            dict.fromkeys(
                ref
                for node in trace.nodes
                for ref in node.evidence_refs
            )
        ),
        missing_proof=(
            (trace.remaining_gap,)
            if trace.remaining_gap and not causal_condition.independently_verified
            else ()
        ),
        contradictions=contradictions,
    )


def _verify_link(
    link_name: str,
    link: CausalLink,
    evidence_by_id: dict[str, EvidenceResult],
) -> CausalLinkVerification:
    refs = tuple(dict.fromkeys(ref for ref in link.evidence_refs if ref))
    valid: list[str] = []
    invalid: list[str] = []
    for ref in refs:
        item = evidence_by_id.get(ref)
        if (
            item is None
            or item.execution_status != "succeeded"
            or bool(item.error)
            or item.evidence_relevance == "irrelevant"
        ):
            invalid.append(ref)
        else:
            valid.append(ref)
    verified = bool(
        link.value.strip()
        and link.independently_verified
        and valid
        and not invalid
    )
    if verified:
        reason = "Value and evidence references were independently verified."
    elif not link.value.strip():
        reason = "Required value is missing."
    elif not link.independently_verified:
        reason = "The causal link has not been independently verified."
    elif not refs:
        reason = "No evidence reference supports the causal link."
    else:
        reason = "Evidence references are missing, failed, blocked, or irrelevant."
    return CausalLinkVerification(
        link_name=link_name,
        value=link.value,
        verified=verified,
        valid_evidence_refs=tuple(valid),
        invalid_evidence_refs=tuple(invalid),
        reason=reason,
    )


def _metadata_only(
    refs: tuple[str, ...],
    evidence_by_id: dict[str, EvidenceResult],
) -> bool:
    items = tuple(evidence_by_id[ref] for ref in refs)
    return bool(items) and all(
        item.evidence_semantics in {"metadata", "procedure_definition"}
        for item in items
    )


def _evidence_hash(evidence: tuple[EvidenceResult, ...]) -> str:
    payload = [
        {
            "evidence_id": item.evidence_id,
            "status": item.execution_status,
            "semantics": item.evidence_semantics,
            "row_count": item.row_count,
            "supports_claim": item.supports_claim,
        }
        for item in evidence
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _json_default(value):
    if isinstance(value, StrEnum):
        return value.value
    return str(value)
