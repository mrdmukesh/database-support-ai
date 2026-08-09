from __future__ import annotations

import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from legacydb_copilot.api import create_fastapi_app
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.db import models


def _make_client():
    app = create_fastapi_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Ensure SQLite enforces FKs for realistic behavior
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db_session():
        db: Session = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app), SessionFactory


def test_cleanup_removes_related_rows_and_preserves_users():
    client, SessionFactory = _make_client()

    # create org and admin via API
    org = client.post("/organizations", json={"name": "INT", "slug": "int"}).json()
    client.post(
        "/auth/signup",
        json={
            "organization_id": org["id"],
            "email": "admin-int@example.com",
            "password": "StrongPass123!",
            "full_name": "AdminInt",
            "role": "organization_admin",
            "consents": ["terms_of_service", "privacy_policy", "document_processing", "ai_verification_required"],
            "ip_address": "127.0.0.1",
        },
    )
    login = client.post("/auth/login", json={"email": "admin-int@example.com", "password": "StrongPass123!"}).json()
    headers = {"Authorization": f"{login['token_type']} {login['access_token']}"}
    # determine created admin user id
    users_list = client.get(f"/admin/users?organization_id={org['id']}", headers=headers).json()
    admin_user = next((u for u in users_list if u['email'] == 'admin-int@example.com'), users_list[0])
    admin_id = admin_user['id']

    # create workspace via API
    ws = client.post("/workspaces", json={"organization_id": org["id"], "name": "W", "slug": "w"}, headers=headers).json()

    # insert a realistic graph using a DB session
    sess: Session = SessionFactory()
    try:
        # create DB connection
        dc = models.DatabaseConnectionModel(organization_id=org["id"], workspace_id=ws["id"], engine="sqlite", name="C", host="h", database_name="d", secret_ref="secret://x", environment_type="test")
        sess.add(dc)
        sess.flush()

        # create investigation and child records
        inv = models.InvestigationModel(organization_id=org["id"], workspace_id=ws["id"], connection_id=dc.id, connection_name=dc.name, selected_database_name=dc.database_name, environment_type="test", policy_name="p", safety_profile="s", environment_source="s", environment_snapshot_json="{}", environment_telemetry_json="{}", user_question="why?", created_by_id=admin_id)
        sess.add(inv)
        sess.flush()

        # evidence (document)
        doc = models.DocumentModel(organization_id=org["id"], workspace_id=ws["id"], owner_id=admin_id, title="e", current_version=1)
        sess.add(doc)
        sess.flush()

        # execution trace, agentic step, planner selection, feedback, verification check, llm audit
        et = models.ExecutionPathTraceModel(organization_id=org["id"], workspace_id=ws["id"], investigation_id=inv.id, affected_entity="e", status="ok")
        as1 = models.InvestigationAgenticStepModel(organization_id=org["id"], workspace_id=ws["id"], investigation_id=inv.id, iteration_number=1, state="done", action_fingerprint="a", outcome="ok")
        ps = models.InvestigationPlannerSelectionModel(organization_id=org["id"], workspace_id=ws["id"], investigation_id=inv.id, status="s", action_fingerprint="af", expected_information_gain=0.1)
        fb = models.InvestigationFeedbackModel(organization_id=org["id"], workspace_id=ws["id"], investigation_id=inv.id, submitted_by_id=admin_id, rating="good")
        vc = models.VerificationCheckModel(organization_id=org["id"], workspace_id=ws["id"], investigation_id=inv.id, claim="c", verification_sql="select 1")
        from datetime import datetime
        import uuid
        la = models.LLMInvocationAuditModel(
            organization_id=org["id"],
            workspace_id=ws["id"],
            investigation_id=inv.id,
            started_at=datetime.utcnow(),
            agent_name="a",
            stage_name="s",
            provider="p",
            model_name="m",
            request_payload_hash="h",
            response_text_sanitized="r",
            status="completed",
            logical_request_id=str(uuid.uuid4()),
        )
        sess.add_all([et, as1, ps, fb, vc, la])
        sess.commit()
    finally:
        sess.close()

    # enable environment guard
    os.environ["ALLOW_TEST_DATA_CLEANUP"] = "true"

    # run cleanup
    resp = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA", "keep_default_workspace": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["physical_databases_deleted"] == 0

    # verify no orphan rows remain by checking counts directly via DB session
    from sqlalchemy import func
    check_sess: Session = SessionFactory()
    try:
        conn_count = check_sess.query(func.count(models.DatabaseConnectionModel.id)).filter(models.DatabaseConnectionModel.organization_id == org["id"]).scalar()
        inv_count = check_sess.query(func.count(models.InvestigationModel.id)).filter(models.InvestigationModel.organization_id == org["id"]).scalar()
        doc_count = check_sess.query(func.count(models.DocumentModel.id)).filter(models.DocumentModel.organization_id == org["id"]).scalar()
        trace_count = check_sess.query(func.count(models.ExecutionPathTraceModel.id)).filter(models.ExecutionPathTraceModel.organization_id == org["id"]).scalar()
        agentic_count = check_sess.query(func.count(models.InvestigationAgenticStepModel.id)).filter(models.InvestigationAgenticStepModel.organization_id == org["id"]).scalar()
        planner_count = check_sess.query(func.count(models.InvestigationPlannerSelectionModel.id)).filter(models.InvestigationPlannerSelectionModel.organization_id == org["id"]).scalar()
        feedback_count = check_sess.query(func.count(models.InvestigationFeedbackModel.id)).filter(models.InvestigationFeedbackModel.organization_id == org["id"]).scalar()
        verification_count = check_sess.query(func.count(models.VerificationCheckModel.id)).filter(models.VerificationCheckModel.organization_id == org["id"]).scalar()
        llm_count = check_sess.query(func.count(models.LLMInvocationAuditModel.id)).filter(models.LLMInvocationAuditModel.organization_id == org["id"]).scalar()
        assert conn_count == 0
        assert inv_count == 0
        assert doc_count == 0
        assert trace_count == 0
        assert agentic_count == 0
        assert planner_count == 0
        assert feedback_count == 0
        assert verification_count == 0
        assert llm_count == 0
    finally:
        check_sess.close()

    # users remain
    users = client.get(f"/admin/users?organization_id={org['id']}", headers=headers).json()
    assert any(u['email'] == 'admin-int@example.com' for u in users)

    # run cleanup second time to assert idempotency
    resp2 = client.post(f"/admin/test-data-cleanup/execute?organization_id={org['id']}", json={"confirmation": "DELETE TEST APP DATA", "keep_default_workspace": True}, headers=headers)
    assert resp2.status_code == 200
