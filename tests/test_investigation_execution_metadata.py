from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.routers.chat import _execution_metadata_section
from legacydb_copilot.workflow.langgraph.activation import (
    CallableOrchestrator,
    InvestigationOrchestratorRouter,
    OrchestrationContext,
    OrchestrationFailure,
    OrchestrationResult,
)


def _settings(mode: str = "LANGGRAPH") -> Settings:
    return replace(
        Settings(environment=Environment.TESTING),
        langgraph_enabled=True,
        investigation_orchestrator_mode=mode,
        llm_reasoning_model="gpt-5.1",
        llm_model="gpt-5.1",
        llm_provider="openai",
        llm_reasoning_effort="high",
    )


def _context() -> OrchestrationContext:
    return OrchestrationContext(
        environment="test",
        workspace_id="workspace",
        user_id="user",
        correlation_id="graph-execution-1",
    )


def _result(source: str) -> OrchestrationResult:
    return OrchestrationResult(payload={}, source=source)


def test_langgraph_execution_metadata_is_captured_by_the_authoritative_router() -> None:
    router = InvestigationOrchestratorRouter(
        settings=_settings(),
        langgraph=CallableOrchestrator(lambda _: _result("langgraph")),
    )

    metadata = router.run(_context()).execution_metadata

    assert metadata["workflow_engine"] == "LangGraph"
    assert metadata["execution_mode"] == "LANGGRAPH"
    assert metadata["graph_version"] == "langgraph-v1"
    assert metadata["graph_execution_id"] == "graph-execution-1"
    assert metadata["requested_model"] == "gpt-5.1"
    assert metadata["effective_model"] == "gpt-5.1"
    assert metadata["provider"] == "openai"
    assert metadata["reasoning_effort"] == "high"
    assert metadata["selected_by"] == "Automatic"
    assert metadata["fallback_used"] is False
    assert isinstance(metadata["execution_started_at"], datetime)
    assert isinstance(metadata["execution_ended_at"], datetime)


def test_langgraph_failure_is_propagated_without_legacy_fallback() -> None:
    def fail(_: OrchestrationContext) -> OrchestrationResult:
        raise OrchestrationFailure("unavailable", stage="graph_startup")

    router = InvestigationOrchestratorRouter(
        settings=_settings(),
        langgraph=CallableOrchestrator(fail),
    )

    with pytest.raises(OrchestrationFailure, match="unavailable"):
        router.run(_context())


def test_historical_investigations_receive_backward_compatible_defaults() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        investigation = InvestigationModel(
            organization_id="organization",
            workspace_id="workspace",
            created_by_id="user",
            environment_type="test",
            policy_name="test-policy",
            safety_profile="read-only",
            environment_source="test",
            environment_snapshot_json="{}",
            environment_telemetry_json="{}",
            user_question="Historical question",
        )
        db.add(investigation)
        db.commit()
        persisted = db.scalar(select(InvestigationModel))

    assert persisted is not None
    assert persisted.workflow_engine == "LangGraph"
    assert persisted.execution_mode == "LANGGRAPH"
    assert persisted.fallback_used is False
    assert persisted.graph_version == ""


def test_executive_report_metadata_defaults_to_langgraph() -> None:
    section = _execution_metadata_section({})

    assert section.title == "Execution Metadata"
    assert "Workflow Badge: LangGraph Verified" in section.items
    assert "Workflow Engine: LangGraph" in section.items
    assert "Execution Mode: LANGGRAPH" in section.items
