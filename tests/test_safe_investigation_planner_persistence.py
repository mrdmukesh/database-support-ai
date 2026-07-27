import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    InvestigationPlannerSelectionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.safe_investigation_planner import (
    EntityScope,
    EnvironmentPolicy,
    EvidenceRequest,
    EvidenceRequestType,
    InvestigationBudget,
    SafeInvestigationPlanner,
)


def test_selection_reason_and_information_gain_are_persisted() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Test", slug="test")
        user = UserModel(
            organization=organization,
            email="planner@example.test",
            password_hash="x",
            full_name="Planner",
        )
        workspace = WorkspaceModel(organization=organization, name="Demo", slug="demo")
        db.add_all((organization, user, workspace))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Why is order 42 stuck?",
        )
        db.add(investigation)
        db.flush()
        planner = SafeInvestigationPlanner()
        decision = planner.select_next(
            candidates=(
                EvidenceRequest(
                    request_type=EvidenceRequestType.ENTITY_LOOKUP,
                    unresolved_question="AFFECTED_ENTITY",
                    entity_scope=EntityScope.EXACT_KEY,
                    entity_type="Order",
                    entity_key="42",
                    expected_information_gain=0.9,
                ),
            ),
            budget=InvestigationBudget(0, 5, 0, 3),
            policy=EnvironmentPolicy("evaluation", "evaluation_readonly"),
        )

        row = planner.persist(db, investigation=investigation, decision=decision)
        db.commit()

        persisted = db.get(InvestigationPlannerSelectionModel, row.id)
        assert persisted is not None
        assert float(persisted.expected_information_gain) == 0.9
        assert "AFFECTED_ENTITY" in persisted.selection_reason
        payload = json.loads(persisted.evidence_request_json)
        assert payload["request_type"] == "ENTITY_LOOKUP"
        assert "sql" not in payload
