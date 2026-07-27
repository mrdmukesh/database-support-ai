from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationAgenticStepModel,
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.routers.investigation_states import (
    cancel_investigation,
    investigation_progress,
)
from legacydb_copilot.services.investigation_state_machine import (
    InvestigationStateService,
)


def test_progress_contract_is_sanitized_and_cancellation_is_terminal() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Progress Test", slug="progress-test")
        workspace = WorkspaceModel(
            organization=organization,
            name="DemoPayrollV2",
            slug="progress-payroll",
        )
        user = UserModel(
            organization=organization,
            email="progress@example.test",
            password_hash="x",
            full_name="Progress Test",
        )
        db.add_all((organization, workspace, user))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            connection_id="CONNECTION-1",
            created_by_id=user.id,
            user_question="Why is PayrollItem missing?",
            extracted_entities_json=json.dumps(
                [{"entity_type": "PAYROLL_ITEM", "value": "PAY-42", "status": "exact"}]
            ),
        )
        db.add(investigation)
        db.flush()
        InvestigationStateService(db).initialize(investigation)
        db.add(
            InvestigationAgenticStepModel(
                organization_id=organization.id,
                workspace_id=workspace.id,
                investigation_id=investigation.id,
                iteration_number=1,
                state="STATE_UPDATE",
                evidence_request_json=json.dumps(
                    {
                        "request_type": "STATUS_HISTORY",
                        "connection_string": "must-not-leak",
                    }
                ),
                evidence_json=json.dumps(
                    [
                        {
                            "evidence_id": "E-1",
                            "purpose": "Missing payroll item",
                            "execution_status": "succeeded",
                            "evidence_semantics": "verified_absence",
                            "row_count": 0,
                            "supports_claim": "No item exists.",
                            "sql": "SELECT secret",
                        }
                    ]
                ),
                gap_analysis_json=json.dumps(
                    {
                        "gaps": [
                            {"question": "Did the job run?", "status": "QUERY_FAILED"},
                            {"question": "Which path applies?", "status": "CONTRADICTED"},
                        ],
                        "answered_questions": ["AFFECTED_ENTITY"],
                    }
                ),
                budget_json=json.dumps(
                    {
                        "iterations": 1,
                        "sql_queries": 1,
                        "total_rows": 0,
                        "execution_seconds": 0.2,
                        "llm_calls": 0,
                    }
                ),
                outcome="failed",
                reason="Runtime history query failed.",
                duration_ms=200,
            )
        )
        db.flush()

        progress = investigation_progress(investigation.id, db, user)

        assert progress.agentic is True
        assert progress.can_cancel is True
        assert progress.question_counts == {
            "open": 0,
            "answered": 1,
            "partial": 1,
            "blocked": 1,
        }
        assert len(progress.failed_actions) == 1
        assert len(progress.verified_absence) == 1
        serialized = progress.model_dump_json()
        assert "must-not-leak" not in serialized
        assert "SELECT secret" not in serialized

        cancelled = cancel_investigation(investigation.id, db, user)

        assert cancelled.current_state == "CANCELLED"
        after = investigation_progress(investigation.id, db, user)
        assert after.terminal is True
        assert after.can_cancel is False
        assert "authorized user" in after.stop_reason
