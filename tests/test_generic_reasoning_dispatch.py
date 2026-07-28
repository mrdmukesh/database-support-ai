from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import EntityExtractionResult, ExtractedEntity
from legacydb_copilot.agents.hypothesis_agent import HypothesisReasoningResult, QuestionUnderstanding
from legacydb_copilot.agents.intent_agent import IntentResult, InvestigationIntent
from legacydb_copilot.agents.recommendation_agent import RecommendationResult
from legacydb_copilot.agents.report_composer_agent import compose_report
from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import LLMInvocationAuditModel, OrganizationModel, UserModel, WorkspaceModel
from legacydb_copilot.reports.dynamic_report_schema import DynamicInvestigationBundle
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult, run_evidence_gate, unreproduced_reasoning
from legacydb_copilot.services.llm_invocation_audit_service import InvocationContext
from legacydb_copilot.services.llm_reasoning_service import enhance_reasoning_with_llm
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata
from legacydb_copilot.services.reasoning_dispatch_service import (
    ReasoningMode,
    ReasoningPermission,
    dispatch_reasoning,
)


def _gate(
    *,
    verified: bool,
    reproduced: bool,
    reported_condition_exists: bool | None = None,
) -> EvidenceGateResult:
    return EvidenceGateResult(
        required=True,
        reproduced=reproduced,
        business_key_exists=verified,
        reported_condition_exists=(
            reproduced if reported_condition_exists is None else reported_condition_exists
        ),
        affected_rows_exist=verified,
        parent_child_relationship_exists=verified,
        confirmed_facts=["Verified deterministic evidence exists."] if verified else [],
        blocking_reasons=[] if verified else ["No verified deterministic evidence."],
        missing_evidence=[] if reproduced else ["Reported condition was not reproduced."],
        status_interpretation=[],
        verified_evidence=verified,
        reasoning_permission=(
            ReasoningPermission.ALLOW_REASONING if verified else ReasoningPermission.DENY_REASONING
        ),
    )


@pytest.mark.parametrize(
    "verified,reproduced,permission,mode",
    [
        (False, False, ReasoningPermission.DENY_REASONING, ReasoningMode.SKIP),
        (False, True, ReasoningPermission.DENY_REASONING, ReasoningMode.SKIP),
        (True, True, ReasoningPermission.ALLOW_REASONING, ReasoningMode.NORMAL_ROOT_CAUSE),
        (
            True,
            False,
            ReasoningPermission.ALLOW_REASONING,
            ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED,
        ),
    ],
)
def test_reasoning_decision_table_is_independent_of_domain_and_question_wording(
    verified: bool,
    reproduced: bool,
    permission: ReasoningPermission,
    mode: ReasoningMode,
) -> None:
    decision = dispatch_reasoning(_gate(verified=verified, reproduced=reproduced))
    assert decision.permission == permission
    assert decision.mode == mode


def test_verified_reported_condition_routes_to_root_cause_when_legacy_reproduced_flag_is_false() -> None:
    decision = dispatch_reasoning(
        _gate(verified=True, reproduced=False, reported_condition_exists=True)
    )

    assert decision.mode == ReasoningMode.NORMAL_ROOT_CAUSE
    assert decision.reproduction_status.value == "reproduced"
    assert decision.reason_code == "VERIFIED_EVIDENCE_REPRODUCED"


DOMAIN_CASES = [
    ("Banking", InvestigationIntent.PROCESS_FLOW_BREAK, "BNK-GENERIC-1"),
    ("Shipping", InvestigationIntent.PROCESS_FLOW_BREAK, "SHP-GENERIC-1"),
    ("Orders", InvestigationIntent.DUPLICATE_DATA, "ORD-GENERIC-1"),
    ("Payroll", InvestigationIntent.MISSING_DATA, "EMP-GENERIC-1"),
    ("Clinic", InvestigationIntent.PERFORMANCE_INVESTIGATION, "APT-GENERIC-1"),
]


@pytest.mark.parametrize("domain,intent,key", DOMAIN_CASES)
def test_verified_unreproduced_evidence_invokes_audited_summary_and_composes_report_for_every_domain(
    domain: str,
    intent: InvestigationIntent,
    key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question = f"Investigate the current {domain.casefold()} record and explain only what verified evidence shows."
    entities = EntityExtractionResult(
        entities=[ExtractedEntity("business_key", key)],
        suspected_issue="investigation",
        likely_module=domain.casefold(),
    )
    table = TableMetadata(
        name=f"domain_{domain.casefold()}_records",
        columns=["BusinessKey", "Status", "CorrelationId"],
        score=10,
    )
    metadata = MetadataSearchResult([table], [], [], "generic-test")
    evidence = [EvidenceResult(
        purpose="Verified primary entity row",
        sql=f"SELECT BusinessKey, Status, CorrelationId FROM {table.name} WHERE BusinessKey = '{key}'",
        rows=[{"BusinessKey": key, "Status": "Recorded", "CorrelationId": f"C-{domain}"}],
        evidence_id="SQL-1",
    )]
    gate = run_evidence_gate(
        question=question,
        intent=intent,
        entities=entities,
        metadata=metadata,
        evidence=evidence,
        evidence_focus=None,
        documents=[],
    )
    decision = dispatch_reasoning(gate)
    assert gate.verified_evidence is True
    assert gate.reproduced is False
    assert decision.permission == ReasoningPermission.ALLOW_REASONING
    assert decision.mode == ReasoningMode.EVIDENCE_SUMMARY_NOT_REPRODUCED

    provider_result = {
        "summary": f"Verified {domain} evidence was summarized; no reported issue was reproduced.",
        "likely_root_causes": [{"conclusion": "Invented cause", "evidence_refs": ["SQL-1"]}],
        "missing_evidence": ["A concrete failing condition was not verified."],
        "recommended_fix": [{"step": "Invented fix", "evidence_refs": ["SQL-1"]}],
        "test_cases": [],
        "proof_of_fix": [],
        "risks": [],
    }

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return json.dumps({
                "id": f"provider-{domain.casefold()}",
                "output_text": json.dumps(provider_result),
                "usage": {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40},
            }).encode()

    monkeypatch.setattr(
        "legacydb_copilot.services.llm_provider_client.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = OrganizationModel(name=f"{domain} Org", slug=f"{domain.casefold()}-org")
        db.add(org); db.flush()
        workspace = WorkspaceModel(organization_id=org.id, name=domain, slug=domain.casefold())
        user = UserModel(
            organization_id=org.id,
            email=f"{domain.casefold()}@example.test",
            password_hash="unused",
            role="organization_admin",
        )
        db.add_all([workspace, user]); db.flush()
        investigation_id = f"INV-{domain.upper()}-GENERIC"
        deterministic = unreproduced_reasoning(gate)
        trace: dict[str, object] = {}
        reasoning = enhance_reasoning_with_llm(
            question=question,
            intent=IntentResult(intent, 0.9, "generic domain test"),
            deterministic_reasoning=deterministic,
            evidence=evidence,
            correlated_evidence=[],
            procedure_analysis=[],
            documents=[],
            settings=Settings(
                environment=Environment.DEVELOPMENT,
                ai_reasoning_enabled=True,
                llm_enabled=True,
                openai_api_key="never-persist",
                llm_retry_attempts=1,
            ),
            debug_trace=trace,
            audit_db=db,
            audit_context=InvocationContext(
                organization_id=org.id,
                workspace_id=workspace.id,
                user_id=user.id,
                investigation_id=investigation_id,
                investigation_run_id=investigation_id,
                correlation_id=investigation_id,
            ),
            reasoning_mode=decision.mode,
        )
        audit = db.query(LLMInvocationAuditModel).one()
        assert audit.investigation_id == investigation_id
        assert audit.status == "completed"
        assert audit.prompt_tokens == 30
        assert "never-persist" not in str(audit.user_prompt_sanitized)

        bundle = DynamicInvestigationBundle(
            question=question,
            intent=IntentResult(intent, 0.9, "generic domain test"),
            entities=entities.entities,
            ranked_objects=[],
            metadata=metadata,
            evidence=evidence,
            correlated_evidence=[],
            procedure_analysis=[],
            hypothesis_reasoning=HypothesisReasoningResult(
                understanding=QuestionUnderstanding(
                    user_goal=question,
                    user_hypothesis="No defect is assumed.",
                    business_process=domain,
                    likely_objects=[table.name],
                    required_evidence=["Verified SQL rows"],
                ),
                hypotheses=[],
                evaluations=[],
                ranked_root_causes=[],
                event_chain=["Verified entity row collected."],
                process_graph=[],
            ),
            documents=[],
            reasoning=reasoning,
            recommendation=RecommendationResult(
                immediate_fix=["Collect further evidence before proposing a change."],
                permanent_fix=[],
                future_improvement=[],
                estimated_effort="Not applicable",
                risk="No change proposed",
                business_impact="No unsupported impact inferred",
                monitoring=[],
                modernization=[],
            ),
            confidence=0.35,
            evidence_gate=gate,
            ai_reasoning_status={
                "ai_assisted_reasoning": "Enabled",
                "reason": "Constrained evidence summary",
                "evidence_package_sent": "Yes",
                "llm_evidence_validation": "Passed",
                "evidence_citations": "Passed",
                "pii_masking": "Applied",
                "pii_masking_scope": "Sensitive values masked",
            },
            ai_debug_trace=trace,
            investigation_policy={
                "name": "test_readonly",
                "environment_type": "TEST",
                "safety_profile": "NON_PRODUCTION_DEEP_READ_ONLY",
                "environment_source": "Registered connection metadata",
                "allow_read_only_procedure_execution": True,
                "data_modification_permitted": False,
                "policy_version": "v1",
                "max_rows": 1000,
                "mask_sensitive_data": False,
                "query_timeout_seconds": 30,
            },
        )
        report = compose_report(
            bundle=bundle,
            workspace_name=domain,
            database_name="Generic test database",
            generated_by="test",
            investigation_id=investigation_id,
        )

    assert trace["ai_reasoning_invoked"] is True
    assert reasoning.response_type == "evidence_summary_not_reproduced"
    assert "Invented cause" not in str(reasoning)
    assert "Invented fix" not in str(reasoning)
    assert "Invented cause" not in str(report)
    assert "Invented fix" not in str(report)
    assert report.cover.investigation_id == investigation_id
    policy_section = next(
        section
        for section in report.sections
        if section.title == "Investigation Environment and Policy"
    )
    assert "Environment: TEST" in policy_section.items
    assert "Environment source: Registered connection metadata" in policy_section.items
    assert "Safety profile: NON_PRODUCTION_DEEP_READ_ONLY" in policy_section.items
    assert "Procedure execution permitted: Yes, read-only only" in policy_section.items
    assert "Data modification permitted: No" in policy_section.items
    assert all(section.title != "Rollback" for section in report.sections)
    assert "Production safeguards may have limited evidence collection" not in str(report)
    assert "reported condition was not reproduced from verified evidence" in str(report).casefold()


def test_unsupported_investigation_does_not_invoke_provider_or_create_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = pytest.fail
    monkeypatch.setattr(
        "legacydb_copilot.services.llm_provider_client.request.urlopen",
        lambda *_args, **_kwargs: provider("Provider must not be called"),
    )
    gate = _gate(verified=False, reproduced=False)
    decision = dispatch_reasoning(gate)
    assert decision.mode == ReasoningMode.SKIP
    assert decision.permission == ReasoningPermission.DENY_REASONING
