from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.report_composer_agent import _executive_root_cause_items
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    OrganizationModel,
    RootCauseHypothesisVerificationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.execution_path_tracing_service import (
    ExecutionObservation,
    ExecutionPathTracingService,
    ExecutionSourceType,
    ExpectedPathStep,
)
from legacydb_copilot.services.root_cause_hypothesis_service import (
    CausalLink,
    HypothesisContradiction,
    HypothesisOrigin,
    HypothesisStatus,
    RootCauseHypothesis,
    RootCauseHypothesisVerifier,
    build_hypothesis_from_execution_trace,
)

LINKS = {
    "affected_entity": ("Employee EMP-1001", "EV-ENTITY"),
    "expected_state": ("PayrollItem should exist", "EV-EXPECTED"),
    "actual_state": ("PayrollItem is absent", "EV-ACTUAL"),
    "last_successful_step": ("Employee marked Ready", "EV-LAST"),
    "first_failed_step": ("PayrollItem creation missing", "EV-FIRST"),
    "responsible_component": ("Payroll generation worker", "EV-COMPONENT"),
    "causal_condition": ("Eligibility guard excluded the employee", "EV-CAUSE"),
}


def evidence(
    evidence_id: str,
    *,
    semantics: str = "positive_rows",
    rows=None,
) -> EvidenceResult:
    return EvidenceResult(
        purpose=evidence_id,
        sql=f"SELECT '{evidence_id}'",
        rows=[{"value": evidence_id}] if rows is None else rows,
        evidence_id=evidence_id,
        execution_status="succeeded",
        evidence_semantics=semantics,
        evidence_relevance="relevant",
        supports_claim=f"Verified {evidence_id}",
    )


def evidence_package() -> tuple[EvidenceResult, ...]:
    return tuple(
        evidence(
            ref,
            semantics="verified_absence" if name == "actual_state" else "positive_rows",
            rows=[] if name == "actual_state" else None,
        )
        for name, (_, ref) in LINKS.items()
    )


def hypothesis(
    *,
    origin: HypothesisOrigin = HypothesisOrigin.DETERMINISTIC,
    overrides: dict[str, CausalLink] | None = None,
    contradictions=(),
) -> RootCauseHypothesis:
    values = {
        name: CausalLink(value, (ref,), True)
        for name, (value, ref) in LINKS.items()
    }
    values.update(overrides or {})
    return RootCauseHypothesis(
        hypothesis_id="H-1",
        description="Eligibility guard prevented PayrollItem creation.",
        origin=origin,
        actual_state_is_incorrect=True,
        contradictions=contradictions,
        **values,
    )


def test_fully_supported_cause_is_confirmed() -> None:
    result = RootCauseHypothesisVerifier().verify(
        (hypothesis(),),
        evidence_package(),
    )

    verification = result.verifications[0]
    assert verification.status is HypothesisStatus.CONFIRMED
    assert verification.visible_in_report is True
    assert result.root_cause_confirmed is True
    assert all(link.verified for link in verification.verification_matrix)


def test_candidate_missing_one_causal_link_is_partially_supported() -> None:
    candidate = hypothesis(
        overrides={
            "causal_condition": CausalLink(
                "Eligibility guard may have excluded the employee",
                (),
                False,
            )
        }
    )

    verification = RootCauseHypothesisVerifier().verify(
        (candidate,),
        evidence_package(),
    ).verifications[0]

    assert verification.status is HypothesisStatus.PARTIALLY_SUPPORTED
    assert "causal_condition" in verification.missing_proof
    assert verification.visible_in_report is False


def test_unverified_candidate_remains_proposed() -> None:
    links = {
        name: CausalLink(value, (), False)
        for name, (value, _ref) in LINKS.items()
    }
    candidate = RootCauseHypothesis(
        hypothesis_id="H-PROPOSED",
        description="A candidate cause requiring evidence.",
        origin=HypothesisOrigin.DETERMINISTIC,
        actual_state_is_incorrect=False,
        **links,
    )

    verification = RootCauseHypothesisVerifier().verify(
        (candidate,),
        evidence_package(),
    ).verifications[0]

    assert verification.status is HypothesisStatus.PROPOSED
    assert verification.visible_in_report is False


def test_rejected_unsupported_ai_claim_never_enters_visible_report() -> None:
    candidate = hypothesis(
        origin=HypothesisOrigin.LLM,
        overrides={
            "causal_condition": CausalLink(
                "An invented worker timeout caused the issue",
                ("EV-NOT-REAL",),
                True,
            )
        },
    )
    result = RootCauseHypothesisVerifier().verify((candidate,), evidence_package())
    verification = result.verifications[0]
    bundle = SimpleNamespace(
        root_cause_verification=result,
        ai_debug_trace={},
        reasoning=SimpleNamespace(likely_root_causes=[]),
        hypothesis_reasoning=SimpleNamespace(ranked_root_causes=[]),
        evidence_gate=None,
    )

    assert verification.status is HypothesisStatus.REJECTED
    assert result.visible_hypotheses == ()
    assert _executive_root_cause_items(bundle) == [
        "Root cause not established from verified evidence."
    ]
    assert "invented worker timeout" not in " ".join(
        _executive_root_cause_items(bundle)
    ).casefold()


def test_material_contradiction_blocks_confirmation() -> None:
    candidate = hypothesis(
        contradictions=(
            HypothesisContradiction(
                "A successful PayrollItem creation event exists for the same scope.",
                ("EV-FIRST",),
                material=True,
                resolved=False,
            ),
        )
    )

    verification = RootCauseHypothesisVerifier().verify(
        (candidate,),
        evidence_package(),
    ).verifications[0]

    assert verification.status is HypothesisStatus.BLOCKED
    assert "contradictory" in verification.decision_reason.casefold()


def test_metadata_only_dependency_does_not_verify_responsible_component() -> None:
    package = tuple(
        evidence(
            item.evidence_id,
            semantics=(
                "procedure_definition"
                if item.evidence_id == "EV-COMPONENT"
                else item.evidence_semantics
            ),
            rows=item.rows,
        )
        for item in evidence_package()
    )

    verification = RootCauseHypothesisVerifier().verify(
        (hypothesis(),),
        package,
    ).verifications[0]

    assert verification.status is HypothesisStatus.PARTIALLY_SUPPORTED
    assert "runtime evidence for responsible component" in verification.missing_proof


def test_verified_absence_alone_does_not_prove_causation() -> None:
    package = tuple(
        evidence(
            item.evidence_id,
            semantics=(
                "verified_absence"
                if item.evidence_id == "EV-CAUSE"
                else item.evidence_semantics
            ),
            rows=[] if item.evidence_id == "EV-CAUSE" else item.rows,
        )
        for item in evidence_package()
    )

    verification = RootCauseHypothesisVerifier().verify(
        (hypothesis(),),
        package,
    ).verifications[0]

    assert verification.status is HypothesisStatus.PARTIALLY_SUPPORTED
    assert "positive causal evidence beyond verified absence" in verification.missing_proof


def test_no_affected_entity_blocks_hypothesis() -> None:
    candidate = hypothesis(
        overrides={"affected_entity": CausalLink("", (), False)}
    )

    verification = RootCauseHypothesisVerifier().verify(
        (candidate,),
        evidence_package(),
    ).verifications[0]

    assert verification.status is HypothesisStatus.BLOCKED
    assert "not resolved" in verification.decision_reason


def test_hypothesis_uses_verified_ag06_execution_path_links() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="EMP-1001",
        expected_steps=(
            ExpectedPathStep("ready", "Employee Ready", 1, "Ready"),
            ExpectedPathStep("create", "Create PayrollItem", 2, "Completed"),
        ),
        observations=(
            ExecutionObservation(
                "ready",
                ExecutionSourceType.ENTITY_RECORD,
                "Ready",
                ("EV-LAST",),
                data_state_verified=True,
            ),
            ExecutionObservation(
                "create",
                ExecutionSourceType.EXCEPTION,
                "Failed",
                ("EV-FIRST", "EV-COMPONENT"),
                component="PayrollWorker",
                runtime_verified=True,
            ),
        ),
    )
    candidate = build_hypothesis_from_execution_trace(
        hypothesis_id="H-TRACE",
        description="Eligibility guard prevented PayrollItem creation.",
        origin=HypothesisOrigin.DETERMINISTIC,
        trace=trace,
        affected_entity_evidence_refs=("EV-ENTITY",),
        expected_state=CausalLink("PayrollItem should exist", ("EV-EXPECTED",), True),
        actual_state=CausalLink("PayrollItem absent", ("EV-ACTUAL",), True),
        causal_condition=CausalLink(
            "Eligibility guard excluded employee",
            ("EV-CAUSE",),
            True,
        ),
        actual_state_is_incorrect=True,
    )

    verification = RootCauseHypothesisVerifier().verify(
        (candidate,),
        evidence_package(),
    ).verifications[0]

    assert candidate.last_successful_step.value == "Employee Ready"
    assert candidate.first_failed_step.value == "Create PayrollItem"
    assert candidate.responsible_component.value == "PayrollWorker"
    assert verification.status is HypothesisStatus.CONFIRMED


def test_full_verification_matrix_and_audit_decision_are_persisted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Hypothesis Test", slug="hypothesis-test")
        workspace = WorkspaceModel(
            organization=organization,
            name="DemoPayrollV2",
            slug="demo-payroll-v2",
        )
        user = UserModel(
            organization=organization,
            email="hypothesis@example.test",
            password_hash="x",
            full_name="Hypothesis Test",
        )
        db.add_all((organization, workspace, user))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Why is PayrollItem missing?",
            environment_type="DEMO",
            policy_name="evaluation_readonly",
            safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
            environment_source="Registered connection metadata",
            environment_snapshot_json="{}",
            environment_telemetry_json="{}",
        )
        db.add(investigation)
        db.flush()
        verifier = RootCauseHypothesisVerifier()
        result = verifier.verify((hypothesis(),), evidence_package())

        rows = verifier.persist(db, investigation=investigation, result=result)
        db.commit()

        persisted = db.get(RootCauseHypothesisVerificationModel, rows[0].id)
        assert persisted is not None
        assert persisted.status == "CONFIRMED"
        assert persisted.visible_in_report is True
        assert len(json.loads(persisted.verification_matrix_json)) == 7
        assert len(json.loads(persisted.valid_evidence_refs_json)) == 7
