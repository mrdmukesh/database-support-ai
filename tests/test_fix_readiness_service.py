from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.report_composer_agent import _fix_readiness_section
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    FixReadinessAssessmentModel,
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.fix_readiness_service import (
    ControlledFixProposal,
    FixReadinessAssessor,
    FixReadinessInputs,
    FixReadinessState,
)
from legacydb_copilot.services.root_cause_hypothesis_service import (
    CausalLink,
    HypothesisOrigin,
    HypothesisStatus,
    HypothesisVerification,
    RootCauseHypothesis,
    RootCauseVerificationResult,
)


def verification(status: HypothesisStatus) -> RootCauseVerificationResult:
    link = CausalLink("verified", ("E-1",), True)
    hypothesis = RootCauseHypothesis(
        hypothesis_id=f"H-{status.value}",
        description="Verified payroll generation condition",
        origin=HypothesisOrigin.DETERMINISTIC,
        affected_entity=link,
        expected_state=link,
        actual_state=link,
        last_successful_step=link,
        first_failed_step=link,
        responsible_component=link,
        causal_condition=link,
        actual_state_is_incorrect=True,
    )
    item = HypothesisVerification(
        hypothesis=hypothesis,
        status=status,
        verification_matrix=(),
        valid_evidence_refs=("E-1",),
        missing_proof=(),
        contradictions=(),
        decision_reason=status.value,
        visible_in_report=status is HypothesisStatus.CONFIRMED,
    )
    return RootCauseVerificationResult(
        verifications=(item,),
        confirmed_hypothesis_ids=(
            (hypothesis.hypothesis_id,)
            if status is HypothesisStatus.CONFIRMED
            else ()
        ),
        rejected_hypothesis_ids=(
            (hypothesis.hypothesis_id,)
            if status is HypothesisStatus.REJECTED
            else ()
        ),
        evidence_package_hash="a" * 64,
    )


def complete_inputs(**overrides) -> FixReadinessInputs:
    values = {
        "affected_entity_resolved": True,
        "scope_defined": True,
        "expected_state_established": True,
        "actual_state_verified": True,
        "relationships_traced": True,
        "runtime_execution_required": True,
        "runtime_execution_verified": True,
        "last_successful_step_identified": True,
        "first_failed_step_identified": True,
        "contradictions_resolved": True,
        "evidence_references_valid": True,
        "root_cause_verification": verification(HypothesisStatus.CONFIRMED),
        "evidence_collected": True,
        "evidence_refs_by_criterion": {
            name: ("E-1",)
            for name in (
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
        },
    }
    values.update(overrides)
    return FixReadinessInputs(**values)


def proposal(*, proof_ready: bool = True) -> ControlledFixProposal:
    return ControlledFixProposal(
        description="Controlled correction of the confirmed payroll condition",
        risk_assessment="Medium; one payroll entity is in scope",
        pre_change_checks=("Verify entity and backup",),
        post_fix_validation=("Verify PayrollItem and downstream totals",)
        if proof_ready
        else (),
        rollback_plan=("Restore the captured entity state",) if proof_ready else (),
        evidence_refs=("E-1",),
        controlled=True,
    )


def test_score_cannot_override_missing_prerequisite() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(
            first_failed_step_identified=False,
            root_cause_verification=verification(HypothesisStatus.PARTIALLY_SUPPORTED),
        )
    )

    assert result.state is FixReadinessState.ROOT_CAUSE_CANDIDATE
    assert result.score > 50
    assert any("first failed" in item.lower() for item in result.blockers)


def test_confirmed_hypothesis_does_not_override_missing_trace_prerequisite() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(
            last_successful_step_identified=False,
            fix_proposal=proposal(),
        )
    )

    assert result.state is FixReadinessState.ROOT_CAUSE_CANDIDATE


def test_fix_proposal_requires_confirmed_root_cause() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(
            root_cause_verification=verification(HypothesisStatus.PARTIALLY_SUPPORTED),
            fix_proposal=proposal(),
        )
    )

    assert result.state is FixReadinessState.ROOT_CAUSE_CANDIDATE


def test_confirmed_cause_with_controlled_proposal_is_fix_ready() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(fix_proposal=proposal(proof_ready=False))
    )

    assert result.state is FixReadinessState.FIX_PROPOSAL_READY
    assert "post_fix_validation_defined" in result.criteria_by_name


def test_validation_and_rollback_make_proof_of_fix_ready() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(fix_proposal=proposal())
    )

    assert result.state is FixReadinessState.PROOF_OF_FIX_READY
    assert result.score == 100


def test_rejected_claim_cannot_satisfy_causal_criteria() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(
            root_cause_verification=verification(HypothesisStatus.REJECTED),
            fix_proposal=proposal(),
        )
    )

    assert result.state is FixReadinessState.INVESTIGATION_INCOMPLETE
    assert not result.confirmed_hypothesis_ids


def test_no_exact_entity_caps_readiness() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(affected_entity_resolved=False, fix_proposal=proposal())
    )

    assert result.state is FixReadinessState.EVIDENCE_COLLECTED


def test_runtime_can_be_explicitly_not_required() -> None:
    result = FixReadinessAssessor().assess(
        complete_inputs(
            runtime_execution_required=False,
            runtime_execution_verified=False,
        )
    )

    assert (
        result.criteria_by_name["runtime_execution_verified"].status.value
        == "NOT_REQUIRED"
    )
    assert result.state is FixReadinessState.ROOT_CAUSE_CONFIRMED


def test_blocked_and_failed_states_take_precedence() -> None:
    assessor = FixReadinessAssessor()

    blocked = assessor.assess(complete_inputs(blocked_reason="Logs unavailable"))
    failed = assessor.assess(complete_inputs(failed_reason="Internal failure"))

    assert blocked.state is FixReadinessState.BLOCKED
    assert failed.state is FixReadinessState.FAILED


def test_assessment_persistence_and_audit() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Readiness Test", slug="readiness-test")
        workspace = WorkspaceModel(
            organization=organization,
            name="DemoPayrollV2",
            slug="demo-payroll-v2-readiness",
        )
        user = UserModel(
            organization=organization,
            email="readiness@example.test",
            password_hash="x",
            full_name="Readiness Test",
        )
        db.add_all((organization, workspace, user))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Can a safe payroll correction be prepared?",
            environment_type="DEMO",
            policy_name="evaluation_readonly",
            safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
            environment_source="Registered connection metadata",
            environment_snapshot_json="{}",
            environment_telemetry_json="{}",
        )
        db.add(investigation)
        db.flush()
        assessor = FixReadinessAssessor()
        assessment = assessor.assess(complete_inputs(fix_proposal=proposal()))

        row = assessor.persist(db, investigation=investigation, assessment=assessment)
        db.commit()

        persisted = db.get(FixReadinessAssessmentModel, row.id)
        assert persisted is not None
        assert persisted.state == "PROOF_OF_FIX_READY"
        assert persisted.score == 100
        assert len(json.loads(persisted.criteria_json)) == 16


def test_report_section_and_backward_compatible_fallback() -> None:
    assessment = FixReadinessAssessor().assess(
        complete_inputs(fix_proposal=proposal())
    )
    section = _fix_readiness_section(
        SimpleNamespace(fix_readiness_assessment=assessment)
    )
    fallback = _fix_readiness_section(
        SimpleNamespace(
            root_cause_verification=verification(HypothesisStatus.CONFIRMED)
        )
    )

    assert "PROOF_OF_FIX_READY" in section.items[0]
    assert section.tables[0].rows
    assert "backward-compatible fallback" in fallback.items[0]
