from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import LLMInvocationAuditModel
from legacydb_copilot.services.llm_invocation_audit_service import (
    InvocationContext,
    LLMInvocationAuditService,
)
from legacydb_copilot.services.llm_provider_client import AuditedLLMProviderClient, ProviderRequest


def service() -> tuple[LLMInvocationAuditService, Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return LLMInvocationAuditService(session), session


def context() -> InvocationContext:
    return InvocationContext(
        investigation_id="inv-1", organization_id="org-1", workspace_id="ws-1",
        user_id="user-1", correlation_id="corr-1",
    )


def test_successful_call_is_completed_and_secrets_are_never_persisted() -> None:
    audit, db = service()
    raw = {
        "password": "super-secret",
        "Authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
        "email": "person@example.com",
    }
    row = audit.start_invocation(
        context=context(), provider="openai", model_name="gpt-test",
        system_prompt="password=super-secret", user_prompt="person@example.com",
        request_payload=raw, request_parameters={"temperature": 0.1, "max_output_tokens": 50},
        retry_attempt=1, prompt_template_name="root_cause_reasoning", prompt_template_version="v1",
    )
    audit.complete_invocation(
        row,
        {"id": "resp-123", "output_text": "token=abcdefghijklmnop", "usage": {"input_tokens": 10, "output_tokens": 4}},
        input_cost_per_million=2.0,
        output_cost_per_million=8.0,
    )
    db.flush()
    persisted = db.query(LLMInvocationAuditModel).one()
    serialized = json.dumps({column.name: getattr(persisted, column.name) for column in persisted.__table__.columns}, default=str)
    assert persisted.status == "completed"
    assert persisted.total_tokens == 14
    assert "super-secret" not in serialized
    assert "person@example.com" not in serialized
    assert "abcdefghijklmnopqrstuvwxyz" not in serialized
    assert persisted.request_payload_hash
    assert persisted.provider_request_id == "resp-123"
    assert float(persisted.estimated_cost) == pytest.approx(0.000052)


def test_timeout_and_rate_limit_are_classified_and_retries_are_linked() -> None:
    audit, db = service()
    logical = "logical-1"
    ctx = InvocationContext(**{**context().__dict__, "logical_request_id": logical})
    for attempt, exc in [(1, TimeoutError("timed out password=hidden")), (2, RuntimeError("429 rate limited"))]:
        row = audit.start_invocation(
            context=ctx, provider="openai", model_name="gpt-test", system_prompt="safe",
            user_prompt="safe", request_payload={}, request_parameters={}, retry_attempt=attempt,
        )
        audit.fail_invocation(row, exc, was_retried=attempt == 1)
    db.flush()
    rows = db.query(LLMInvocationAuditModel).order_by(LLMInvocationAuditModel.retry_attempt).all()
    assert [row.status for row in rows] == ["timeout", "rate_limited"]
    assert {row.logical_request_id for row in rows} == {logical}
    assert rows[0].was_retried is True
    assert "hidden" not in rows[0].error_message_sanitized


def test_list_is_chronological_paginated_and_tenant_scoped() -> None:
    audit, db = service()
    for org, investigation, stamp in [
        ("org-1", "inv-1", datetime(2026, 1, 2, tzinfo=UTC)),
        ("org-1", "inv-1", datetime(2026, 1, 1, tzinfo=UTC)),
        ("org-2", "inv-2", datetime(2026, 1, 3, tzinfo=UTC)),
    ]:
        db.add(LLMInvocationAuditModel(
            organization_id=org, workspace_id="ws", investigation_id=investigation,
            logical_request_id=investigation, agent_name="agent", stage_name="Root Cause Reasoning",
            provider="openai", model_name="gpt", request_payload_hash="a" * 64,
            started_at=stamp, status="completed",
        ))
    db.flush()
    rows, total = audit.search_invocations(
        organization_id="org-1", investigation_id="inv-1", page=1, page_size=1
    )
    assert total == 2
    assert rows[0].started_at.day == 1


def test_filter_combinations_apply_stage_model_status_failure_search_and_dates() -> None:
    audit, db = service()
    for index, values in enumerate([
        ("Root Cause Reasoning", "gpt-a", "failed", "needle", 1200, datetime(2026, 1, 2, tzinfo=UTC)),
        ("Metadata Discovery", "embed-a", "completed", "other", 20, datetime(2026, 1, 3, tzinfo=UTC)),
    ]):
        stage, model, status, prompt, duration, stamp = values
        db.add(LLMInvocationAuditModel(
            organization_id="org-1", workspace_id="ws-1", investigation_id="inv-1",
            logical_request_id=f"logical-{index}", agent_name=f"agent-{index}", stage_name=stage,
            provider="openai", model_name=model, request_payload_hash="a" * 64,
            user_prompt_sanitized=prompt, started_at=stamp, duration_ms=duration, status=status,
        ))
    db.flush()
    rows, total = audit.search_invocations(
        organization_id="org-1", investigation_id="inv-1", stage_name="Root Cause Reasoning",
        model="gpt-a", status="failed", failed_only=True, search="needle",
        started_after=datetime(2026, 1, 1, tzinfo=UTC),
        started_before=datetime(2026, 1, 2, 23, 59, tzinfo=UTC),
    )
    assert total == 1
    assert rows[0].duration_ms == 1200


def test_sql_result_values_are_replaced_with_structured_placeholders() -> None:
    audit, db = service()
    row = audit.start_invocation(
        context=context(), provider="openai", model_name="gpt-test", system_prompt="safe",
        user_prompt=json.dumps({"sample_rows": [{"patient": "Jane Doe", "diagnosis": "private"}]}),
        request_payload={"rows": [{"patient": "Jane Doe", "diagnosis": "private"}]},
        request_parameters={}, retry_attempt=1,
    )
    db.flush()
    serialized = f"{row.user_prompt_sanitized} {row.context_payload_sanitized}"
    assert "Jane Doe" not in serialized
    assert "private" not in serialized
    assert "[REDACTED_PII]" in serialized


def test_missing_investigation_context_does_not_fabricate_an_audit_row(monkeypatch) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"id":"resp","data":[]}'

    monkeypatch.setattr("legacydb_copilot.services.llm_provider_client.request.urlopen", lambda *_a, **_k: Response())
    audit, db = service()
    result = AuditedLLMProviderClient().invoke_json(ProviderRequest(
        provider="openai", model="embed", endpoint="https://provider/embeddings",
        api_key="secret", body={"input": "safe"},
    ))
    assert result["id"] == "resp"
    assert db.query(LLMInvocationAuditModel).count() == 0


def test_multiple_agents_share_one_investigation(monkeypatch) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self): return b'{"id":"resp","output_text":"ok","usage":{"input_tokens":2,"output_tokens":1}}'

    monkeypatch.setattr("legacydb_copilot.services.llm_provider_client.request.urlopen", lambda *_a, **_k: Response())
    audit, db = service()
    for agent, stage in [("context_discovery_agent", "Metadata Discovery"), ("reasoning_agent", "Root Cause Reasoning")]:
        ctx = InvocationContext(**{**context().__dict__, "agent_name": agent, "stage_name": stage, "logical_request_id": f"logical-{agent}"})
        AuditedLLMProviderClient(db=db, context=ctx).invoke_json(ProviderRequest(
            provider="openai", model="gpt", endpoint="https://provider/responses",
            api_key="secret", body={"input": "safe"},
        ))
    db.flush()
    rows = db.query(LLMInvocationAuditModel).all()
    assert len(rows) == 2
    assert {row.investigation_id for row in rows} == {"inv-1"}
    assert {row.agent_name for row in rows} == {"context_discovery_agent", "reasoning_agent"}
