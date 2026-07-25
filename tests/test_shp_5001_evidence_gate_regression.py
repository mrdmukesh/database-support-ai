from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import InvestigationIntent, IntentResult
from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    LLMInvocationAuditModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.routers.chat import _expand_related_id_evidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate, unreproduced_reasoning
from legacydb_copilot.services.llm_invocation_audit_service import InvocationContext
from legacydb_copilot.services.llm_reasoning_service import enhance_reasoning_with_llm
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult, TableMetadata


QUESTION = (
    "Investigate shipment SHP-5001 and determine the root cause of the shipment processing issue. "
    "Trace and correlate all related records across shipment details, warehouse processing, inventory "
    "allocation, transportation events, delivery status, customer information, billing, and operational "
    "workflow. Reconstruct the complete timeline, identify any delays, inconsistencies, failed processing "
    "steps, or missing downstream actions, and explain the operational impact. Use only verified database "
    "evidence."
)


def test_shp_5001_cross_table_evidence_uses_constrained_ai_summary_and_real_audit(
    monkeypatch,
) -> None:
    entities = extract_entities(QUESTION)
    assert any(entity.value == "SHP-5001" for entity in entities.entities)

    ranked = MetadataSearchResult(
        [TableMetadata("eval.shipments", ["ShipmentsId", "BookingsId", "BusinessKey", "Status"], 10)],
        [], [], "shipping-v1",
    )
    active = MetadataSearchResult(
        [
            *ranked.tables,
            TableMetadata(
                "eval.shipment_milestones",
                ["ShipmentMilestonesId", "ShipmentsId", "Status"],
                8,
            ),
            TableMetadata(
                "eval.bills_of_lading",
                ["BillsOfLadingId", "ShipmentsId", "Status"],
                7,
            ),
        ],
        [], [], "shipping-v1",
    )

    class ShippingConnector:
        def execute_read_only_query(self, sql: str, limit: int = 25):
            if "shipment_milestones" in sql:
                return [{"ShipmentMilestonesId": 7001, "ShipmentsId": 5001, "Status": "Recorded"}]
            if "bills_of_lading" in sql:
                return [{"BillsOfLadingId": 8001, "ShipmentsId": 5001, "Status": "Issued"}]
            return [{"ShipmentsId": 5001, "BookingsId": 3001, "BusinessKey": "SHP-5001", "Status": "InTransit"}]

    evidence = [EvidenceResult(
        "Prove requested entity exists in eval.shipments",
        "SELECT ShipmentsId, BookingsId, BusinessKey, Status FROM eval.shipments "
        "WHERE BusinessKey = 'SHP-5001'",
        [{"ShipmentsId": 5001, "BookingsId": 3001, "BusinessKey": "SHP-5001", "Status": "InTransit"}],
        evidence_id="SQL-1",
    )]
    evidence.extend(
        _expand_related_id_evidence(
            ShippingConnector(), ranked, evidence, active_metadata=active
        )
    )
    purposes = {item.purpose for item in evidence}
    assert "Inspect correlated rows by ShipmentsId in eval.shipment_milestones" in purposes
    assert "Inspect correlated rows by ShipmentsId in eval.bills_of_lading" in purposes
    assert all("duplicate" not in purpose.casefold() for purpose in purposes)

    gate = run_evidence_gate(
        question=QUESTION,
        intent=InvestigationIntent.PROCESS_FLOW_BREAK,
        entities=entities,
        metadata=active,
        evidence=evidence,
        evidence_focus=None,
        documents=[],
    )
    assert gate.reproduced is False
    assert gate.failed_rule == "EG-REPORTED-CONDITION"
    assert gate.summary_mode_eligible is True
    assert gate.returned_row_count >= 3

    response_payload = {
        "summary": "Verified shipment and related records were summarized; no defect was reproduced.",
        "likely_root_causes": [
            {"conclusion": "Unsupported carrier failure", "evidence_refs": ["SQL-1"]}
        ],
        "missing_evidence": ["No specific delay or failed transition was verified."],
        "recommended_fix": [{"step": "Replace the carrier", "evidence_refs": ["SQL-1"]}],
        "test_cases": [],
        "proof_of_fix": [],
        "risks": [],
    }

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return json.dumps({
                "id": "provider-shp-5001",
                "output_text": json.dumps(response_payload),
                "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
            }).encode()

    monkeypatch.setattr(
        "legacydb_copilot.services.llm_provider_client.request.urlopen",
        lambda *_args, **_kwargs: Response(),
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = OrganizationModel(name="Shipping", slug="shipping")
        db.add(org); db.flush()
        workspace = WorkspaceModel(organization_id=org.id, name="Eval Shipping", slug="eval-shipping")
        user = UserModel(
            organization_id=org.id,
            email="shipping@example.test",
            password_hash="not-used",
            role="organization_admin",
        )
        db.add_all([workspace, user]); db.flush()
        context = InvocationContext(
            organization_id=org.id,
            workspace_id=workspace.id,
            user_id=user.id,
            investigation_id="INV-SHP-5001-REGRESSION",
            investigation_run_id="INV-SHP-5001-REGRESSION",
            correlation_id="INV-SHP-5001-REGRESSION",
        )
        deterministic = unreproduced_reasoning(gate)
        trace: dict[str, object] = {}
        result = enhance_reasoning_with_llm(
            question=QUESTION,
            intent=IntentResult(InvestigationIntent.PROCESS_FLOW_BREAK, 0.9, "trace"),
            deterministic_reasoning=deterministic,
            evidence=evidence,
            correlated_evidence=[],
            procedure_analysis=[],
            documents=[],
            settings=Settings(
                environment=Environment.DEVELOPMENT,
                ai_reasoning_enabled=True,
                llm_enabled=True,
                openai_api_key="must-never-be-persisted",
                llm_retry_attempts=1,
            ),
            debug_trace=trace,
            audit_db=db,
            audit_context=context,
        )

        audits = db.query(LLMInvocationAuditModel).all()
        assert len(audits) == 1
        assert audits[0].investigation_id == "INV-SHP-5001-REGRESSION"
        assert audits[0].status == "completed"
        assert audits[0].prompt_tokens == 120
        assert audits[0].completion_tokens == 40
        assert audits[0].duration_ms is not None
        assert audits[0].provider_request_id == "provider-shp-5001"
        assert "must-never-be-persisted" not in str(audits[0].user_prompt_sanitized)

    assert trace["ai_reasoning_invoked"] is True
    assert result.response_type == "evidence_summary_not_reproduced"
    assert result.likely_root_causes == deterministic.likely_root_causes
    assert result.recommended_fix == deterministic.recommended_fix
    assert "Unsupported carrier failure" not in str(result)
    assert "Replace the carrier" not in str(result)
