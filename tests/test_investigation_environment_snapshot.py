from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)


def test_environment_snapshot_cannot_change_after_investigation_begins() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    snapshot = json.dumps(
        {
            "selected_connection_id": "CONN",
            "selected_database_name": "DemoPayrollV2",
            "workspace_id": "WS",
            "environment_type": "TEST",
            "safety_profile": "NON_PRODUCTION_DEEP_READ_ONLY",
            "environment_source": "Registered connection metadata",
        }
    )
    with Session(engine) as db:
        db.add(OrganizationModel(id="ORG", name="Org", slug="org"))
        db.add(WorkspaceModel(id="WS", organization_id="ORG", name="Demo", slug="demo"))
        db.add(
            UserModel(
                id="USER",
                organization_id="ORG",
                email="user@example.com",
                password_hash="x",
                full_name="User",
                role="dba",
            )
        )
        investigation = InvestigationModel(
            id="INV",
            organization_id="ORG",
            workspace_id="WS",
            connection_id="CONN",
            connection_name="Test_Payrool",
            selected_database_name="DemoPayrollV2",
            environment_type="TEST",
            policy_name="test_readonly",
            safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
            environment_source="Registered connection metadata",
            environment_snapshot_json=snapshot,
            environment_telemetry_json="{}",
            created_by_id="USER",
            user_question="Investigate payroll",
        )
        db.add(investigation)
        db.commit()

        investigation.environment_type = "PRODUCTION"
        with pytest.raises(ValueError, match="snapshot is immutable"):
            db.commit()
